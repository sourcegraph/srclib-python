import os
import sys
import json
import string
import argparse as ap
from os import path
from glob import glob
from collections import namedtuple

import jedi

global verbose_, quiet_

def log(msg):
    if verbose_:
        sys.stderr.write(msg + '\n')

def error(msg):
    if not quiet_:
        sys.stderr.write(msg + '\n')

def graph(dir_, pretty=False, verbose=False, quiet=False, nSourceFilesTrunc=None):
    global verbose_, quiet_
    verbose_, quiet_ = verbose, quiet
    os.chdir(dir_)          # set working directory to be source directory

    source_files = get_source_files('.')
    if nSourceFilesTrunc is not None:
        source_files = source_files[:nSourceFilesTrunc]

    modules_and_files = [(filename_to_module_name(f), f) for f in source_files]
    jedi.api.preload_module([mf[0] for mf in modules_and_files])

    defs = [d for d in get_defs(source_files)]
    refs = [r for r in get_refs(source_files)]

    for module, filename in modules_and_files:
        defs.append(Def(
            Path=module.replace('.', '/'),
            Kind='module',
            Name=string.split(module, '.')[-1],
            File=filename,
            DefStart=0,
            DefEnd=0,
            Exported=True,
            Docstring='',           # TODO: extract module/package-level doc
            Data=None,
        ))

    # De-duplicate definitions (local variables may be defined in more than one
    # place). Could do something smarter here, but for now, just take the first
    # definition that appears.
    unique_defs = []
    unique_def_paths = set([])
    for def_ in defs:
        if not def_.Path in unique_def_paths:
            unique_defs.append(def_)
            unique_def_paths.add(def_.Path)

    # Self-references, dedup
    unique_refs = []
    unique_ref_keys = set([])
    for def_ in unique_defs:
        ref = Ref(
            DefPath=def_.Path,
            DefFile=path.abspath(def_.File),
            Def=True,
            File=def_.File,
            Start=def_.DefStart,
            End=def_.DefEnd,
            ToBuiltin=False,
        )
        ref_key = (ref.DefPath, ref.DefFile, ref.File, ref.Start, ref.End)
        if ref_key not in unique_ref_keys:
            unique_ref_keys.add(ref_key)
            unique_refs.append(ref)
    for ref in refs:
        ref_key = (ref.DefPath, ref.DefFile, ref.File, ref.Start, ref.End)
        if ref_key not in unique_ref_keys:
            unique_ref_keys.add(ref_key)
            unique_refs.append(ref)

    json_indent = 2 if pretty else None
    print json.dumps({
        'Defs': [d.__dict__ for d in unique_defs],
        'Refs': [r.__dict__ for r in unique_refs],
    }, indent=json_indent)

def get_source_files(dir_):
    source_files = []
    for dirpath, dirnames, filenames in os.walk(dir_):
        rel_dirpath = os.path.relpath(dirpath, dir_)
        for filename in filenames:
            if os.path.splitext(filename)[1] == '.py':
                source_files.append(os.path.join(rel_dirpath, filename))
    return source_files

def get_defs(source_files):
    for i, source_file in enumerate(source_files):
        log('getting defs for source file (%d/%d) %s' % (i, len(source_files), source_file))
        try:
            source = None
            with open(source_file) as sf:
                source = unicode(sf.read())
            linecoler = LineColToOffConverter(source)

            defs = jedi.api.defined_names(source, path=source_file)
            for def_ in defs:
                for d in get_defs_(def_, source_file, linecoler):
                    yield d
        except Exception as e:
            error('failed to get defs for source file %s: %s' % (source_file, str(e)))

def get_defs_(def_, source_file, linecoler):
    # ignore import definitions because these just redefine things imported from elsewhere
    if def_.type == 'import':
        return
    
    def__, err = jedi_def_to_def(def_, source_file, linecoler)
    if err is None:
        yield def__
    else:
        error(err)

    if def_.type not in ['function', 'class', 'module']:
        return

    subdefs = def_.defined_names()
    for subdef in subdefs:
        for d in get_defs_(subdef, source_file, linecoler):
            yield d

def jedi_def_to_def(def_, source_file, linecoler):
    full_name, err = full_name_of_def(def_)
    if err is not None:
        return None, err

    start_pos = linecoler.convert(def_.start_pos)
    return Def(
        Path=full_name.replace('.', '/'),
        Kind=def_.type,
        Name=def_.name,
        File=source_file,
        DefStart=start_pos,
        DefEnd=start_pos+len(def_.name),
        Exported=True,          # TODO: not all vars are exported
        Docstring=def_.docstring(),
        Data=None,
    ), None

def get_refs(source_files):
    for i, source_file in enumerate(source_files):
        log('getting refs for source file (%d/%d) %s' % (i, len(source_files), source_file))
        try:
            parserContext = ParserContext(source_file)
            linecoler = LineColToOffConverter(parserContext.source)
            for name_part, def_ in parserContext.refs():
                try:
                    full_name, err = full_name_of_def(def_, from_ref=True)
                    if err is not None or full_name == '':
                        raise Exception(err)
                    start = linecoler.convert(name_part.start_pos)
                    end = linecoler.convert(name_part.end_pos)
                    yield Ref(
                        DefPath=full_name.replace('.', '/'),
                        DefFile=def_.module_path,
                        Def=False,
                        File=source_file,
                        Start=start,
                        End=end,
                        ToBuiltin=def_.in_builtin_module(),
                    )
                except Exception as e:
                    error('failed to get ref (%s) in source file %s: %s' % (str((name_part, def_)), source_file, str(e)))
        except Exception as e:
            error('failed to get refs for source file %s: %s' % (source_file, str(e)))

def full_name_of_def(def_, from_ref=False):
    # TODO: This function
    # - currently fails for tuple assignments (e.g., 'x, y = 1, 3')
    # - doesn't distinguish between m(module).n(submodule) and m(module).n(contained-variable)

    if def_.in_builtin_module():
        return def_.full_name, None

    full_name = ('%s.%s' % (def_.full_name, def_.name)) if def_.type in set(['statement', 'param']) else def_.full_name

    module_path = def_.module_path
    if from_ref:
        module_path, err = abs_module_path_to_relative_module_path(module_path)
        if err is not None:
            return None, err

    supermodule = supermodule_path(module_path).replace('/', '.')

    # definition definitions' full_name property contains only the promixal module, so we need to add back the parent
    # module components. Luckily, the module_path is relative in this case.
    return path.join(supermodule, full_name), None

def supermodule_path(module_path):
    if path.basename(module_path) == '__init__.py':
        return path.dirname(path.dirname(module_path))
    return path.dirname(module_path)

def abs_module_path_to_relative_module_path(module_path):
    relpath = path.relpath(module_path) # relative from pwd (which is set in main)
    if not relpath.startswith('..'):
        return relpath, None
    components = module_path.split(os.sep)
    pIdx = -1
    for i, cmpt in enumerate(components):
        if cmpt in ['site-packages', 'dist-packages']:
            pIdx = i
            break
    if pIdx != -1:
        return path.join(*components[i+1:]), None

    for i, cmpt in enumerate(components):
        if cmpt.startswith('python'):
            pIdx = i
            break
    if pIdx != -1:
        return path.join(*components[i+1:]), None
    return None, ("could not convert absolute module path %s to relative module path" % module_path)
        

Def = namedtuple('Def', ['Path', 'Kind', 'Name', 'File', 'DefStart', 'DefEnd', 'Exported', 'Docstring', 'Data'])
Ref = namedtuple('Ref', ['DefPath', 'DefFile', 'Def', 'File', 'Start', 'End', "ToBuiltin"])

class ParserContext(object):
    def __init__(self, source_file):
        self.source_file = source_file
        with open(source_file) as sf:
            self.source = unicode(sf.read())
            self.parser = jedi.parser.Parser(self.source, source_file)

    def refs(self):
        for r in self.scope_refs(self.parser.module):
            yield r

    def scope_refs(self, scope):
        for import_ in scope.imports:
            for r in self.import_refs(import_):
                yield r
        for stmt in scope.statements:
            for r in self.stmt_refs(stmt):
                yield r
        for ret in scope.returns:
            for r in self.stmt_refs(ret):
                yield r
        for subscope in scope.subscopes:
            for r in self.scope_refs(subscope):
                yield r

    def import_refs(self, import_):
        for name in import_.get_all_import_names():
            for name_part in name.names:
                defs = jedi.api.Script(
                    path=self.source_file,
                    line=name_part.start_pos[0],
                    column=name_part.start_pos[1],
                ).goto_assignments()
                for def_ in defs:
                    yield (name_part, def_)

    def stmt_refs(self, stmt):
        if isinstance(stmt, jedi.parser.representation.KeywordStatement):
            return
        if isinstance(stmt, jedi.parser.representation.Flow):
            return
        if stmt is None:
            return

        for token in stmt._token_list:
            if not isinstance(token, jedi.parser.representation.Name):
                continue
            for name_part in token.names:
                # Note: we call goto_definitions instead of goto_assignments,
                # because otherwise the reference will not follow imports (and
                # also generates bogus local definitions whose paths conflict
                # with those of actual definitions). This uses a modified
                # goto_definitions (resolve_variables_to_types option) that
                # *DOES NOT* follow assignment statements to resolve variables
                # to types (because that's not what we want).
                defs = jedi.api.Script(
                    path=self.source_file,
                    line=name_part.start_pos[0],
                    column=name_part.start_pos[1],
                    resolve_variables_to_types=False,
                ).goto_definitions()

                # Note(beyang): For now, only yield the first definition.
                # Otherwise, multiple references to multiple definitions will
                # yield dup references. In the future, might want to do
                # something smarter here.
                i = 0
                for def_ in defs:
                    if i > 0: break
                    yield (name_part, def_)
                    i += 1

def resolve_import_paths(scopes):
    for s in scopes.copy():
        if isinstance(s, jedi.evaluate.imports.ImportWrapper):
            scopes.remove(s)
            scopes.update(resolve_import_paths(set(s.follow())))
    return scopes

def filename_to_module_name(filename):
    if path.basename(filename) == '__init__.py':
        return path.dirname(filename).replace('/', '.')
    return path.splitext(filename)[0].replace('/', '.')

class LineColToOffConverter(object):
    def __init__(self, source):
        source_lines = source.split('\n')
        cumulative_off = [0]
        for line in source_lines:
            cumulative_off.append(cumulative_off[-1] + len(line) + 1)
        self._cumulative_off = cumulative_off

    # Converts from (line, col) position to byte offset. line is 1-indexed, col is 0-indexed
    def convert(self, linecol):
        line, col = linecol[0] - 1, linecol[1]         # convert line to 0-indexed
        if line >= len(self._cumulative_off):
            return None, 'requested line out of bounds %d > %d' % (line+1, len(self._cumulative_off)-1)
        return self._cumulative_off[line] + col

if __name__ == '__main__':
    argser = ap.ArgumentParser(description='graph.py is a command that dumps all Python definitions and references found in code rooted at a directory')
    argser.add_argument('dir', help='path to root directory of code')
    argser.add_argument('--pretty', help='pretty print JSON output', action='store_true', default=False)
    argser.add_argument('--verbose', help='verbose', action='store_true', default=False)
    argser.add_argument('--quiet', help='quiet', action='store_true', default=False)
    args = argser.parse_args()
    if args.dir == '':
        error('target directory must not be empty')
        os.exit(1)
    graph(args.dir, pretty=args.pretty, verbose=args.verbose, quiet=args.quiet)
