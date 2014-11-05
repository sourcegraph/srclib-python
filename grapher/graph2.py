import os
import sys
import json
import string
import argparse as ap
import subprocess
from os import path
from glob import glob
from collections import namedtuple

import jedi

global verbose_, quiet_
SOURCE_FILE_BATCH = 10

def log(msg):
    if verbose_:
        sys.stderr.write(msg + '\n')

def error(msg):
    if not quiet_:
        sys.stderr.write(msg + '\n')

def graph_wrapper(dir_, pretty=False, verbose=False, quiet=False, nSourceFilesTrunc=None):
    global verbose_, quiet_
    verbose_, quiet_ = verbose, quiet
    os.chdir(dir_)          # set working directory to be source directory

    source_files = get_source_files('.')
    if nSourceFilesTrunc is not None:
        source_files = source_files[:nSourceFilesTrunc]

    graph(dir_, source_files, pretty=pretty, verbose=verbose, quiet=quiet)

def graph(dir_, source_files, pretty=False, verbose=False, quiet=False):
    global verbose_, quiet_
    verbose_, quiet_ = verbose, quiet
    os.chdir(dir_)          # set working directory to be source directory

    defs, refs = [], []
    for source_file in source_files:
        sys.stderr.write('processing source_file: %s\n' % source_file)

        with open(source_file) as sf:
            source_ = sf.read()
        source = jedi.common.source_to_unicode(source_, 'utf-8')
        linecoler = LineColToOffConverter(source)

        jedi_names = None
        try:
            jedi_names = jedi.names(source=source, path=source_file, all_scopes=True,
                                    definitions=True, references=True)
        except Exception as e:
            error('error parsing %s: %s' % (source_file, str(e)))
            continue

        jedi_defs, jedi_refs = [], []
        for jedi_name in jedi_names:
            if jedi_name.is_definition():
                jedi_defs.append(jedi_name)
            else:
                jedi_refs.append(jedi_name)

        for jedi_def in jedi_defs:
            sg_def, err = jedi_def_to_def(jedi_def, source_file, linecoler)
            if err is None:
                defs.append(sg_def)
            else:
                error(err)

        # for jedi_ref in jedi_refs:
        #     try:
        #         ref_defs = jedi_ref.goto_assignments()
        #     except Exception:
        #         error('error getting definitions for reference %s' % str(jedi_ref)[0:50])
        #         continue
        #     if len(ref_defs) == 0:
        #         continue

        #     sg_def, err = jedi_def_to_def_key(ref_defs[0])
        #     if err != None:
        #         error(err)
        #         continue

        #     ref_start = linecoler.convert(jedi_ref.start_pos)
        #     ref_end = ref_start + len(jedi_ref.name)

        #     refs.append(Ref(
        #         DefPath=sg_def.Path,
        #         DefFile=sg_def.File,
        #         Def=False,
        #         File=source_file,
        #         Start=ref_start,
        #         End=ref_end,
        #         ToBuiltin=ref_defs[0].in_builtin_module(),
        #     ))

    print json.dumps({
        'Defs': [d.__dict__ for d in defs],
        'Refs': [r.__dict__ for r in refs],
    }, indent=2)

def get_source_files(dir_):
    source_files = []
    for dirpath, dirnames, filenames in os.walk(dir_):
        rel_dirpath = os.path.relpath(dirpath, dir_)
        for filename in filenames:
            if os.path.splitext(filename)[1] == '.py':
                source_files.append(os.path.normpath(os.path.join(rel_dirpath, filename)))
    return source_files









def jedi_def_to_def_key(def_):
    try:
        full_name, err = full_name_of_def(def_)
        if err is not None:
            return None, err
    except Exception as e:
        return None, str(e)

    return Def(
        Path=full_name.replace('.', '/'),
        Kind=def_.type,
        Name=def_.name,
        File=def_.module_path,
        DefStart=None,
        DefEnd=None,
        Exported=True,          # TODO: not all vars are exported
        Docstring=None,
        Data=None,
    ), None

def jedi_def_to_def(def_, source_file, linecoler):
    try:
        full_name, err = full_name_of_def(def_)
        if err is not None:
            return None, err
    except Exception as e:
        return None, str(e)

    # If def_ is a name, then the location of the definition is the last name part
    if isinstance(def_._definition, jedi.parser.representation.Name):
        last_name = def_._definition.names[-1]
        start = linecoler.convert(last_name.start_pos)
        end = start + len(last_name._string)
    else:
        start = linecoler.convert(def_.start_pos)
        end = start + len(def_.name)

    return Def(
        Path=full_name.replace('.', '/'),
        Kind=def_.type,
        Name=def_.name,
        File=def_.module_path,
        DefStart=start,
        DefEnd=end,
        Exported=True,          # TODO: not all vars are exported
        Docstring=def_.docstring(),
        Data=None,
    ), None

def full_name_of_def(def_, from_ref=False):
    # TODO: This function
    # - currently fails for tuple assignments (e.g., 'x, y = 1, 3')
    # - doesn't distinguish between m(module).n(submodule) and m(module).n(contained-variable)

    if def_.in_builtin_module():
        return def_.name, None

    if def_.type == 'statement':
        full_name = ('%s.%s' % (def_.full_name, def_.name))

        # # kludge for self.* definitions
        # if def_.parent().type == 'function' and def_._definition.names[0]._string == u'self':
        #     parent = def_.parent()
        #     while parent.type != 'class':
        #         parent = parent.parent()
        #     full_name = ('%s.%s' % (parent.full_name, def_.name))
        # else:
        #     full_name = ('%s.%s' % (def_.full_name, def_.name))
    elif def_.type == 'param':
        full_name = ('%s.%s' % (def_.full_name, def_.name))
    else:
        full_name = def_.full_name

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
    argser.add_argument('--dir', help='path to root directory of code')
    argser.add_argument('--files', help='path code files', nargs='+')
    argser.add_argument('--pretty', help='pretty print JSON output', action='store_true', default=False)
    argser.add_argument('--verbose', help='verbose', action='store_true', default=False)
    argser.add_argument('--quiet', help='quiet', action='store_true', default=False)
    argser.add_argument('--maxfiles', help='maximum number of files to process', default=None, type=int)
    args = argser.parse_args()

    if args.files is not None and len(args.files) > 0:
        graph(args.dir, args.files, pretty=args.pretty, verbose=args.verbose, quiet=args.quiet)
    elif args.dir is not None and args.dir != '':
        graph_wrapper(args.dir, pretty=args.pretty, verbose=args.verbose, quiet=args.quiet, nSourceFilesTrunc=args.maxfiles)
    else:
        error('target directory must not be empty')
        os.exit(1)
