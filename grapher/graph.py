import os
import sys
import json
import argparse as ap
from os import path
from glob import glob
from collections import namedtuple

import jedi

global verbose, quiet

def log(msg):
    if verbose:
        sys.stderr.write(msg + '\n')

def error(msg):
    if not quiet:
        sys.stderr.write(msg + '\n')

def main():
    argser = ap.ArgumentParser(description='graph.py is a command that dumps all Python definitions and references found in code rooted at a directory')
    argser.add_argument('dir', help='path to root directory of code')
    argser.add_argument('--pretty', help='pretty print JSON output', action='store_true', default=False)
    argser.add_argument('--verbose', help='verbose', action='store_true', default=False)
    argser.add_argument('--quiet', help='quiet', action='store_true', default=False)

    args = argser.parse_args()
    global verbose, quiet
    verbose, quiet = args.verbose, args.quiet
    os.chdir(args.dir)          # set working directory to be source directory

    source_files = glob('**/*.py')
    source_files.extend(glob('*.py'))

    modules = [filename_to_module_name(f) for f in source_files]
    jedi.api.preload_module(modules)

    defs = [d for d in get_defs(source_files)]
    refs = [r for r in get_refs(source_files)]

    json_indent = 2 if args.pretty else None
    print json.dumps({
        'Defs': [d.__dict__ for d in defs],
        'Refs': [r.__dict__ for r in refs],
    }, indent=json_indent)

def get_defs(source_files):
    for source_file in source_files:
        log('getting defs for source file %s' % source_file)
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
    for source_file in source_files:
        log('getting refs for source file %s' % source_file)
        try:
            parserContext = ParserContext(source_file)
            linecoler = LineColToOffConverter(parserContext.source)
            for name_part, def_ in parserContext.refs():
                try:
                    full_name, err = full_name_of_def(def_, from_ref=True)
                    if err is not None:
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

        for token in stmt._token_list:
            if not isinstance(token, jedi.parser.representation.Name):
                continue
            for name_part in token.names:
                # TODO: we call goto_definitions instead of goto_assignments,
                # because otherwise the reference will not follow imports (and
                # thus generates bogus definitions whose paths conflict with
                # those of actual definitions). However, goto_assignments *also*
                # follows assignment statements, and so will mark instances of a
                # type as a reference to the type. This is isn't really what we
                # want. But for now, it's fine. We should really just extend
                # Jedi to have a goto_definitions that follows imports, but not
                # statements
                defs = jedi.api.Script(
                    path=self.source_file,
                    line=name_part.start_pos[0],
                    column=name_part.start_pos[1],
                ).goto_definitions()
                for def_ in defs:
                    yield (name_part, def_)

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
    main()
