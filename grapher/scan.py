import sys
import os
import os.path
import json

from . import pydepwrap
from . import django
from . import builtin
from .structures import *
from .util import normalize


def stdlibUnits(diry: str) -> Tuple[List[Unit], bool]:
    if not os.path.lexists(os.path.join(diry, "Lib")):
        return None, False
    if not os.path.lexists(os.path.join(diry, "Include")):
        return None, False
    if not os.path.lexists(os.path.join(diry, "Modules")):
        return None, False

    # HACK(performance): filter out test files in standard lib
    files = [f for f in get_source_files(diry) if (
        (f.startswith('Lib/')) and ('/test/' not in f) and ('_test' not in f) and ('test_' not in f)
    )]

    return [Unit(
        Name = STDLIB_UNIT_KEY.Name,
        Type = STDLIB_UNIT_KEY.Type,
        Repo = STDLIB_UNIT_KEY.Repo,
        CommitID = STDLIB_UNIT_KEY.CommitID,
        Version = STDLIB_UNIT_KEY.Version,
        Files = sorted(files),
        Dir = 'Lib',
        Dependencies = [],
    ), Unit(
        Name = BUILTIN_UNIT_KEY.Name,
        Type = BUILTIN_UNIT_KEY.Type,
        Repo = BUILTIN_UNIT_KEY.Repo,
        CommitID = BUILTIN_UNIT_KEY.CommitID,
        Version = BUILTIN_UNIT_KEY.Version,
        Files = builtin.get_c_source_files('Modules'),
        Dir = 'Modules',
        Dependencies = [],
    )], True

def find_pip_pkgs(rootdir: str) -> List:
    setup_dirs = pydepwrap.setup_dirs(rootdir)
    setup_infos = []
    for setup_dir in setup_dirs:
        setup_dict = pydepwrap.setup_info_dir(setup_dir)
        setup_infos.append(
            setup_dict_to_json_serializable_dict(setup_dict, rootdir=os.path.relpath(setup_dir, rootdir)))
    return setup_infos

def source_files_for_pip_unit(unit_dir: str) -> List[str]:
    metadata = pydepwrap.setup_info_dir(unit_dir)
    packages, modules = [], [] # type: List[str], List[str]
    if 'packages' in metadata and metadata['packages'] is not None:
        packages.extend(metadata['packages'])
    if 'modules' in metadata and metadata['modules'] is not None:
        modules.extend(metadata['modules'])
    if 'py_modules' in metadata and metadata['py_modules'] is not None:
        modules.extend(metadata['py_modules'])

    included_tests = False
    tests_candidates = ["test", "tests"]
    files = []
    for module in modules:
        files.append('{}.py'.format(normalize(module)))
    for pkg in packages:
        pkg_path = pkg.replace('.', '/')

        if not included_tests:
            included_tests = pkg_path.split('/')[0] in tests_candidates

        pkg_files = get_source_files(pkg_path)
        for pkg_file in pkg_files:
            files.append(normalize(os.path.join(pkg_path, pkg_file)))

    # Make good guess for test files when they are not linked.
    if not included_tests:
        for cand in tests_candidates:
            pkg_files = get_source_files(cand)
            for pkg_file in pkg_files:
                files.append(normalize(os.path.join(cand, pkg_file)))

    files.append('setup.py')
    files = list(set(files))
    return files

# pkgToUnit transforms a Pip package struct into a source unit.
def pkgToUnit(pkg: Dict) -> Unit:
    pkgdir = pkg['rootdir']
    files = source_files_for_pip_unit(pkgdir)
    pkgreqs = pydepwrap.requirements(pkgdir, True)
    deps = []
    for pkgreq in pkgreqs:
        dep = pkgToUnitKey(pkgreq)
        if dep is not None:
            deps.append(dep)
    return Unit(
        Name = pkg['project_name'],
        Type = UNIT_PIP,
        Repo = "",       # empty Repo signals it is from this repository
        CommitID = "",
        Files = sorted(files),
        Dir = normalize(pkgdir),
        Dependencies = deps,      # unresolved dependencies
        Data = Data(
            Reqs = [req for req in pkgreqs if checkReq(req)],
            ReqFiles = [normalize(os.path.join(pkgdir, "requirements.txt"))],
        )
    )

def scan(diry: str) -> None:
    # special case for standard library
    stdunits, isStdlib = stdlibUnits(diry)
    if isStdlib:
        json.dump(toJSONable(stdunits), sys.stdout, sort_keys=True)
        return

    units = [] # type: List[Unit]
    for pkg in find_pip_pkgs(diry):
        units.append(pkgToUnit(pkg))
    for proj in django.find_units("."):
        units.append(proj)

    # add setuptools as a dependency for all non-stdlib units
    for u in units:
        u.Dependencies.append(SETUPTOOLS_UNIT_KEY)

    json.dump(toJSONable(units), sys.stdout, sort_keys=True)


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
