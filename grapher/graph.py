import sys
import json
import logging
import pip
import os.path

from subprocess import call

from .structures import *
from .file_grapher import FileGrapher, FileGrapherException
from . import builtin

def getModulePathPrefixToDep(u: Unit) -> Dict[str, UnitKey]:
    if not u.Data:
        return {}

    prefixToDep = {}
    for req in u.Data.Reqs:
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

    # setuptools special case
    prefixToDep['setuptools'] = SETUPTOOLS_UNIT_KEY

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

    u = fromJSONable(json.load(fp), Unit) # type: Unit
    graphunit(logger, args, u)

def graphunit(logger, args, u: Unit) -> None:
    if u.key() == BUILTIN_UNIT_KEY:
        builtindefs = [b.to_def() for b in builtin.find_modules(u.Dir)]
        json.dump(toJSONable({
            'Defs': builtindefs,
            'Refs': [d.defref() for d in builtindefs],
            'Docs': [],
        }), sys.stdout, sort_keys=True)
        return

    if u.Dir is None or u.Dir == '':
        raise Exception('target directory must not be empty')

    if u.Type == UNIT_PIP:
        setupfile = os.path.join('.', u.Dir, 'setup.py')
        if os.path.lexists(setupfile):
            pip.main(['install', '-q', '--upgrade', os.path.join('.', u.Dir)])

    if u.Data and u.Data.ReqFiles:
        for reqfile in u.Data.ReqFiles:
            if os.path.lexists(reqfile):
                pip.main(['install', '-q', '-r', reqfile])

    prefixToDep = getModulePathPrefixToDep(u)

    defs = {} # type: Dict[str, Def]
    refs = {} # type: Dict[str, Ref]
    docs = {} # type: Dict[str, Doc]

    total = len(u.Files)
    for i, f in enumerate(u.Files, start=1):
        logger.info('processing file: {} ({}/{})'.format(f, i, total))
        try:
            fg = FileGrapher(u.Dir, f, u.Name, u.Type, prefixToDep, sys.path, logger)
            defs_, refs_, docs_ = fg.graph()
        except FileGrapherException as e:
            logger.error('failed to graph {}: {}'.format(f, str(e)))
            continue
        except Exception as e:
            logger.error('failed to graph {} due to unanticipated error: {}'.format(f, str(e)))
            continue
        # Note: This uses last version of def/ref, but since file order is random anyway,
        #       it should be OK.
        defs.update(defs_)
        refs.update(refs_)
        docs.update(docs_)

    json.dump(toJSONable({
        'Defs': [e for e in defs.values()],
        'Refs': [e for e in refs.values()],
        'Docs': [e for e in docs.values()],
    }), sys.stdout, sort_keys=True)
