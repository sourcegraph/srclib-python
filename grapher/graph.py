import os
import sys
import json
import argparse
import logging
from collections import namedtuple
import jedi

from grapher.helpers import LineColToOffConverter

SOURCE_FILE_BATCH = 10


Def = namedtuple('Def', ['Path', 'Kind', 'Name', 'File', 'DefStart', 'DefEnd', 'Exported', 'Docstring', 'Data'])
Ref = namedtuple('Ref', ['DefPath', 'DefFile', 'Def', 'File', 'Start', 'End', "ToBuiltin"])


class Grapher(object):
    def __init__(self, source_dir, source_files, log=None):
        """
        Create a new grapher.
        """
        self.log = log or logging.getLogger(__name__)
        self.files = source_files

        # Set working directory to be source directory
        os.chdir(source_dir)

    def process(self, pretty):
        defs, refs = [], []

        for fp in self.files:
            self.log.info('processing file: {}'.format(fp))

            with open(fp) as f:
                source = f.read()

            linecoler = LineColToOffConverter(source)

            try:
                jedi_names = jedi.names(source=source, path=fp, all_scopes=True, references=True)
            except Exception as e:
                self.log.error("failed to parse {}: {}".format(fp, str(e)))
                continue

            jedi_defs, jedi_refs = [], []
            for jedi_name in jedi_names:
                if jedi_name.is_definition():
                    jedi_defs.append(jedi_name)
                else:
                    jedi_refs.append(jedi_name)

            unique_def_paths = set()
            for jedi_def in jedi_defs:
                sg_def = self.jedi_def_to_def(jedi_def, fp, linecoler)
                if sg_def.Path not in unique_def_paths:
                    defs.append(sg_def)
                    unique_def_paths.add(sg_def.Path)

            unique_ref_paths = set()
            for jedi_ref in jedi_refs:
                # noinspection PyBroadException
                try:
                    ref_defs = jedi_ref.goto_assignments()
                except Exception:
                    self.log.error("error getting definitions for reference {}".format(str(jedi_ref)[0:50]))
                    continue

                if len(ref_defs) == 0:
                    continue

                sg_def = self.jedi_def_to_def_key(ref_defs[0])
                if sg_def.Path not in unique_ref_paths:
                    ref_start = linecoler.convert((jedi_ref.line, jedi_ref.column))
                    ref_end = ref_start + len(jedi_ref.name)
                    refs.append(Ref(
                        DefPath=sg_def.Path,
                        DefFile=sg_def.File,
                        Def=False,
                        File=fp,
                        Start=ref_start,
                        End=ref_end,
                        # ToBuiltin=ref_defs[0].in_builtin_module(),
                        ToBuiltin="sg_def.Kind={}, ref.Kind={}".format(sg_def.Kind, jedi_ref.type),
                    ))
                    unique_ref_paths.add(sg_def.Path)
        self.log.error("\n".join([d.Path for d in defs if d.Path.startswith("user/User")]))
        return json.dumps({
            # Using `__dict__` as a hacky way to get dictionary from namedtuple.
            # Works on Python 2.7+
            'Defs': [d.__dict__ for d in defs],
            'Refs': [r.__dict__ for r in refs],
        }, indent=2 if pretty else None)

    def jedi_def_to_def(self, d, source_file, lc):
        # TODO: Add back this if needed:
        # If def_ is a name, then the location of the definition is the last name part
        start = lc.convert((d.line, d.column))
        end = start + len(d.name)

        return Def(
            Path=self.full_name(d).replace('.', '/'),
            Kind=d.type,
            Name=d.name,
            File=source_file,
            DefStart=start,
            DefEnd=end,
            # TODO: not all vars are exported
            Exported=True,
            Docstring=d.docstring(),
            Data=None,
        )

    def jedi_def_to_def_key(self, d):
        return Def(
            Path=self.full_name(d).replace('.', '/'),
            Kind=d.type,
            Name=d.name,
            File=d.module_path,
            DefStart=None,
            DefEnd=None,
            Exported=True,  # TODO: not all vars are exported
            Docstring=d.docstring(),
            Data=None,
        )

    @staticmethod
    def full_name(d):
        if d.in_builtin_module():
            return d.name
        if d.type == "statement" or d.type == "param":
            name = "{}.{}".format(d.full_name, d.name)
        else:
            name = d.full_name

        # module_path = os.path.relpath(d.module_path)
        # if not d.is_definition():
        module_path = Grapher.abs_module_path_to_relative_module_path(d.module_path)

        if os.path.basename(module_path) == '__init__.py':
            parent_module = os.path.dirname(os.path.dirname(module_path))
        else:
            parent_module = os.path.dirname(module_path)

        return "{}.{}".format(parent_module, name)

    @staticmethod
    def abs_module_path_to_relative_module_path(module_path):
        rel_path = os.path.relpath(module_path)
        if not rel_path.startswith('..'):
            return rel_path

        components = module_path.split(os.sep)
        pi1 = pi2 = -1
        for i, component in enumerate(components):
            if component in ['site-packages', 'dist-packages']:
                pi1 = i
                break
            # Bad fallback.
            if pi2 == -1 and component.startswith('python'):
                pi2 = i

        pi = pi1 if pi1 != -1 else pi2
        if pi != -1:
            return os.path.join(*components[pi + 1:])

        raise RuntimeError("could not convert absolute module path {} to relative module path".forma(module_path))


def get_source_files(source_dir):
    """ Get list of all Python source files in a directory. """
    files = []
    op = os.path
    for path, _, filenames in os.walk(source_dir):
        rel_dir = op.relpath(path, source_dir)
        files.extend([op.normpath(op.join(rel_dir, f)) for f in filenames if op.splitext(f)[1] == ".py"])
    return files


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(description='graph.py is a command that dumps all Python definitions and '
                                                     'references found in code rooted at a directory')
    arg_parser.add_argument('--dir', help='path to root directory of code')
    arg_parser.add_argument('--files', help='path code files', nargs='+')
    arg_parser.add_argument('--pretty', help='pretty print JSON output', action='store_true', default=False)
    arg_parser.add_argument('--verbose', help='verbose', action='store_true', default=False)
    arg_parser.add_argument('--quiet', help='quiet', action='store_true', default=False)
    arg_parser.add_argument('--maxfiles', help='maximum number of files to process', default=None, type=int)
    args = arg_parser.parse_args()

    # Setup logging.
    logger = logging.getLogger(__name__)
    # Will output to stderr.
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    # By default only report errors.
    logger.setLevel(logging.ERROR)

    if args.verbose:
        logger.setLevel(logging.INFO)

    if args.quiet:
        logger.setLevel(logging.CRITICAL)

    if args.files is not None and len(args.files) > 0:
        grapher = Grapher(args.dir, args.files, logger)
        print(grapher.process(args.pretty))
    elif args.dir is not None and args.dir != '':
        pass
        # # Set working directory to be source directory
        # os.chdir(source_dir)
        # source_files = get_source_files('.')
        #
        # if first_n_files is not None:
        # source_files = source_files[:first_n_files]
        #
        # all_data = {'Defs': [], 'Refs': []}
        # for i in range(0, len(source_files), SOURCE_FILE_BATCH):
        #     log.info('processing source files %d to %d of %d' % (i, i + SOURCE_FILE_BATCH, len(source_files)))
        #     batch = source_files[i:i + SOURCE_FILE_BATCH]
        #
        #     cmd_args = [sys.executable, "-m", "grapher.graph", "--dir", "."]
        #     if verbose:
        #         cmd_args.append('--verbose')
        #     if quiet:
        #         cmd_args.append('--quiet')
        #     if pretty:
        #         cmd_args.append('--pretty')
        #     cmd_args.append('--files')
        #     cmd_args.extend(batch)
        #     p = subprocess.Popen(cmd_args, stdout=subprocess.PIPE, env=os.environ.copy())
        #     out, err = p.communicate()
        #     if err is not None:
        #         sys.stderr.write(err)
        #
        #     data = json.loads(out)
        #     all_data['Defs'].extend(data['Defs'])
        #     all_data['Refs'].extend(data['Refs'])
        #
        # print(json.dumps(all_data, indent=2 if pretty else None))
        #
    else:
        logger.error('target directory must not be empty')
        sys.exit(1)
