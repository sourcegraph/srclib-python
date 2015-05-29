import os
import sys
import json
import argparse
import logging

from file_grapher import FileGrapher, FileGrapherException


def get_source_files(source_dir):
    """ Get list of all Python source files in a directory. """
    result = []
    op = os.path
    for path, _, filenames in os.walk(source_dir):
        rel_dir = op.relpath(path, source_dir)
        result.extend([op.normpath(op.join(rel_dir, f)) for f in filenames if op.splitext(f)[1] == '.py'])
    return result


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(description='graph.py is a command that dumps all Python definitions and '
                                                     'references found in code rooted at a directory')
    arg_parser.add_argument('--dir', help='path to root directory of code')
    arg_parser.add_argument('--files', help='path code files', nargs='+')
    arg_parser.add_argument('--pretty', help='pretty print JSON output', action='store_true', default=False)
    arg_parser.add_argument('--verbose', help='verbose', action='store_true', default=False)
    arg_parser.add_argument('--debug', help='debug', action='store_true', default=False)
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

    if args.debug:
        logger.setLevel(logging.DEBUG)

    if args.verbose:
        logger.setLevel(logging.INFO)

    if args.quiet:
        logger.setLevel(logging.CRITICAL)

    files = []
    if args.files is not None and len(args.files) > 0:
        files = args.files
    elif args.dir is not None and args.dir != '':
        files = get_source_files(args.dir)
    else:
        logger.error('target directory must not be empty')
        sys.exit(1)

    defs = {}
    refs = {}
    total = len(files)
    for i, f in enumerate(files, start=1):
        logger.info('processing file: {} ({}/{})'.format(f, i, total))
        fg = FileGrapher(args.dir, f, logger)
        try:
            d, r = fg.graph()
        except FileGrapherException as e:
            logger.error('failed to graph {}: {}'.format(f, str(e)))
            continue
        # Note: This uses last version of def/ref, but since file order is random anyway,
        #       it should be OK.
        defs.update(d)
        refs.update(r)

    print(json.dumps({
        # Using `__dict__` as a hacky way to get dictionary from namedtuple.
        # Works on Python 2.7+
        'Defs': [d.__dict__ for d in defs.values()],
        'Refs': [r.__dict__ for r in refs.values()],
    }, indent=2 if args.pretty else None))
