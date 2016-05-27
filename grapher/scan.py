import sys
import os
import os.path
import json

import pydep.setup_py
import pydep.req

from typing import Tuple, Dict
from .structures import *
from .util import normalize


def stdlibUnit(diry: str) -> Tuple[Unit, bool]:
    if not os.path.lexists(os.path.join(diry, "Lib")):
        return None, False
    if not os.path.lexists(os.path.join(diry, "Include")):
        return None, False
    if not os.path.lexists(os.path.join(diry, "Modules")):
        return None, False

    # HACK(performance): filter out test files in standard lib
    files = [f for f in get_source_files(diry) if (('/test/' not in f) and ('_test' not in f) and ('test_' not in f))]

    return Unit(
        Name = 'Python',
        Type = UNIT_PIP,
        Repo = 'github.com/python/cpython',
        CommitID = '',
        Files = sorted(files),
        Dir = 'Lib',
        Dependencies = [],
    ), True

def findpkgs(rootdir: str) -> List:
    setup_dirs = pydep.setup_py.setup_dirs(rootdir)
    setup_infos = []
    for setup_dir in setup_dirs:
        # HACK: filter out unwanted setup.py's. Should do this inside pydep.
        rel_setup_dir = os.path.relpath(rootdir, setup_dir)
        ignore = False
        for comp in rel_setup_dir.split(os.sep):
            if (comp != "." and comp.startswith(".")) or comp == "testdata":
                ignore = True
                break
        if ignore:
            continue

        setup_dict, err = pydep.setup_py.setup_info_dir(setup_dir)
        if err is not None:
            raise Exception('failed due to error: {}'.format(err))
        setup_infos.append(
            setup_dict_to_json_serializable_dict(setup_dict, rootdir=os.path.relpath(setup_dir, rootdir)))
    return setup_infos

def get_source_files(diry: str) -> List[str]:
    """ Get list of all Python source files in a directory. """
    files = [] # type: List[str]
    for path, _, filenames in os.walk(diry):
        rel_dir = os.path.relpath(path, diry)
        files.extend([normalize(os.path.normpath(os.path.join(rel_dir, f))) for f in filenames if os.path.splitext(f)[1] == '.py'])
    if diry != "" and diry != ".":
        for i in range(len(files)):
            if files[i].startswith('./'):
                files[i] = files[i][2:]
            files[i] = normalize(files[i])
    return files

def source_files_for_unit(unit_dir: str) -> List[str]:
    metadata, err = pydep.setup_py.setup_info_dir(unit_dir)
    if err is not None:
        raise Exception(err)
    packages, modules = [], [] # type: List[str], List[str]
    if 'packages' in metadata and metadata['packages'] is not None:
        packages.extend(metadata['packages'])
    if 'modules' in metadata and metadata['modules'] is not None:
        modules.extend(metadata['modules'])
    if 'py_modules' in metadata and metadata['py_modules'] is not None:
        modules.extend(metadata['py_modules'])

    files = []
    for module in modules:
        files.append('{}.py'.format(normalize(module)))
    for pkg in packages:
        pkg_files = get_source_files(pkg.replace('.', '/'))
        for pkg_file in pkg_files:
            files.append(normalize(os.path.join(pkg.replace('.', '/'), pkg_file)))
    files.append('setup.py')
    files = list(set(files))
    return files

def pkgToUnitKey(pkg: Dict) -> UnitKey:
    return UnitKey(
        Name = pkg['project_name'],
        Type = UNIT_PIP,
        Repo = REPO_UNRESOLVED,
        Version = "",
        CommitID = "",
    )

# pkgToUnit transforms a Pip package struct into a source unit.
def pkgToUnit(pkg: Dict) -> Unit:
    pkgdir = pkg['rootdir']
    files = source_files_for_unit(pkgdir)
    pkgreqs, err = pydep.req.requirements(pkgdir, True)
    if err is not None:
        raise Exception(err)
    deps = []
    for pkgreq in pkgreqs:
        deps.append(pkgToUnitKey(pkgreq))
    return Unit(
        Name = pkg['project_name'],
        Type = UNIT_PIP,
        Repo = "",       # empty Repo signals it is from this repository
        CommitID = "",
        Files = sorted(files),
        Dir = pkgdir,
        Dependencies = deps,      # don't resolve dependencies
        Data = pkgreqs,
    )

def reqToUnit(req):
    pass

def scan(diry: str) -> None:
    # special case for standard library
    stdunit, isStdlib = stdlibUnit(diry)
    if isStdlib:
        json.dump([stdunit.todict()], sys.stdout, sort_keys=True)
        return

    pkgs = findpkgs(diry)
    units = []
    for pkg in pkgs:
        units.append(pkgToUnit(pkg).todict())
    json.dump(units, sys.stdout, sort_keys=True)


#
# Helpers
#

# setup_dict_to_json_serializable_dict is copy-pasted from pydep-run.py
def setup_dict_to_json_serializable_dict(d, **kw):
    return {
        'rootdir': kw['rootdir'] if 'rootdir' in kw else None,
        'project_name': d['name'] if 'name' in d else None,
        'version': d['version'] if 'version' in d else None,
        'repo_url': d['url'] if 'url' in d else None,
        'packages': d['packages'] if 'packages' in d else None,
        'modules': d['py_modules'] if 'py_modules' in d else None,
        'scripts': d['scripts'] if 'scripts' in d else None,
        'author': d['author'] if 'author' in d else None,
        'description': d['description'] if 'description' in d else None,
    }
