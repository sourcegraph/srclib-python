import sys
import json
import logging
import pip
import os.path

from typing import Dict
from subprocess import call

from .structures import *
from .file_grapher import FileGrapher, FileGrapherException


def getModulePathPrefixToDep(u: Unit) -> Dict[str, UnitKey]:
    if not u.Data:
        return {}

    prefixToDep = {}
    for req in u.Data:
        if req['repo_url']:
            repo, unit, unit_type = req['repo_url'], req['project_name'], UNIT_PIP
        else:
            repo, unit, unit_type = REPO_UNRESOLVED, req['project_name'], UNIT_PIP

        if req['packages'] is not None:
            for pkg in req['packages']:
                prefixToDep[pkg.replace('.', '/')] = UnitKey(Repo=repo, Name=unit, Type=unit_type, CommitID="", Version="")
        if req['modules'] is not None:
            for mod in req['modules']:
                prefixToDep[mod] = UnitKey(Repo=repo, Name=unit, Type=unit_type, CommitID="", Version="")
    return prefixToDep

def graph(args, fp) -> None:
    # Setup logging to stderr
    logger = logging.getLogger(__name__)
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
    if args.debug:
        logger.setLevel(logging.DEBUG)
    elif args.verbose:
        logger.setLevel(logging.INFO)
    elif args.quiet:
        logger.setLevel(logging.CRITICAL)

    u = Unit(**json.load(fp)) # type: Unit
    graphunit(logger, args, u)

def graphunit(logger, args, u: Unit) -> None:
    if u.Dir is None or u.Dir == '':
        raise Exception('target directory must not be empty')

    setupfile = os.path.join('.', u.Dir, 'setup.py')
    if os.path.lexists(setupfile):
        pip.main(['install', '-q', '--upgrade', os.path.join('.', u.Dir)])
    requirementsfile = os.path.join(u.Dir, 'requirements.txt')
    if os.path.lexists(requirementsfile):
        pip.main(['install', '-q', '-r', os.path.join('.', u.Dir, 'requirements.txt')])

    prefixToDep = getModulePathPrefixToDep(u)

    defs = {} # type: Dict[str, Def]
    refs = {} # type: Dict[str, Ref]
    total = len(u.Files)
    for i, f in enumerate(u.Files, start=1):
        logger.info('processing file: {} ({}/{})'.format(f, i, total))
        try:
            fg = FileGrapher(u.Dir, f, u.Name, u.Type, prefixToDep, sys.path, logger)
            d, r = fg.graph()
        except FileGrapherException as e:
            logger.error('failed to graph {}: {}'.format(f, str(e)))
            continue
        except Exception as e:
            logger.error('failed to graph {} due to unanticipated error: {}'.format(f, str(e)))
        # Note: This uses last version of def/ref, but since file order is random anyway,
        #       it should be OK.
        defs.update(d)
        refs.update(r)

    json.dump({
        'Defs': [d._asdict() for d in defs.values()], # type: ignore (NamedTuple._asdict)
        'Refs': [r._asdict() for r in refs.values()], # type: ignore (NamedTuple._asdict)
    }, sys.stdout, sort_keys=True)
