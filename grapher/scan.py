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

# Directory name for test files in common practice.
TEST_DIR = "tests"

def source_files_for_pip_unit(metadata: Dict) -> Tuple[List[str], List[str]]:
    packages, modules = [], [] # type: List[str], List[str]
    if 'packages' in metadata and metadata['packages'] is not None:
        packages.extend(metadata['packages'])
    if 'modules' in metadata and metadata['modules'] is not None:
        modules.extend(metadata['modules'])
    if 'py_modules' in metadata and metadata['py_modules'] is not None:
        modules.extend(metadata['py_modules'])

    # Indicate whether this unit is in root direcotry of repository.
    unit_dir = metadata['rootdir']
    is_root_dir = unit_dir == "."
    included_tests = False
    files = []
    for module in modules:
        if not is_root_dir:
            module = os.path.join(unit_dir, module)
        files.append('{}.py'.format(normalize(module)))
    for pkg in packages:
        pkg_path = pkg.replace('.', '/')

        if not included_tests:
            included_tests = pkg_path.split('/')[0] == TEST_DIR

        if not is_root_dir:
            pkg_path = os.path.join(unit_dir, pkg_path)
        pkg_files = get_source_files(pkg_path)
        for pkg_file in pkg_files:
            files.append(normalize(os.path.join(pkg_path, pkg_file)))

    # Make good guess for test files when they are not linked.
    test_files = []
    if not included_tests:
        test_dir = TEST_DIR
        if not is_root_dir:
            test_dir = os.path.join(unit_dir, TEST_DIR)

        pkg_files = get_source_files(test_dir)
        for pkg_file in pkg_files:
            test_files.append(normalize(os.path.join(test_dir, pkg_file)))

    if is_root_dir:
        files.append('setup.py')
    else:
        files.append(os.path.join(unit_dir, 'setup.py'))
    files = list(set(files))
    test_files = list(set(test_files))
    return files, test_files

# filesToModules transforms from source files to list of modules.
# Because setup.py file only defines modules and packages the library wants to expose, 
# but test files are using ones that are not defined in the setup.py as well.
def filesToModules(rootdir: str, files: List[str]) -> List[str]:
    modules = []
    for file in files:
        # Convert file path to Python module name format .
        file = os.path.splitext(file)[0].replace('/', '.')
        # Remove directory prefix if setup.py is not in root directory.
        if rootdir != ".":
            file = file[len(rootdir)+1:]
        modules.append(file)
    modules = sorted(modules)
    return modules

# pkgToUnits transforms a Pip package struct into a list of source units,
# including main unit and possible test unit.
def pkgToUnits(pkg: Dict) -> List[Unit]:
    pkgdir = pkg['rootdir']
    files, test_files = source_files_for_pip_unit(pkg)
    pkgreqs = pydepwrap.requirements(pkgdir, True)
    deps = []
    for pkgreq in pkgreqs:
        dep = pkgToUnitKey(pkgreq)
        if dep is not None:
            deps.append(dep)

    unit = Unit(
        Name = pkg['project_name'] if pkg['project_name'] is not None else pkgdir,
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
    if len(test_files) == 0:
        return [unit]

    test_dir = TEST_DIR
    if pkgdir != ".":
        test_dir = os.path.join(pkgdir, TEST_DIR)
    return [unit, Unit(
        Name = unit.Name,
        Type = TEST_UNIT_KEY.Type,
        Repo = "",
        CommitID = "",
        Files = sorted(test_files),
        Dir = test_dir,
        Dependencies = [UnitKey(
            Name = unit.Name,
            Type = unit.Type,
            Repo = unit.Repo,
            CommitID = unit.CommitID,
            Version = unit.Version,
        )],
        Data = Data(
            Reqs = [{
                "project_name": unit.Name,
                "repo_url": "",
                "packages": pkg['packages'] if pkg['packages'] is not None else None,
                "modules": filesToModules(pkgdir, files),
            }]
        )
    )]

def scan(diry: str) -> None:
    # special case for standard library
    stdunits, isStdlib = stdlibUnits(diry)
    if isStdlib:
        json.dump(toJSONable(stdunits), sys.stdout, sort_keys=True)
        return

    units = [] # type: List[Unit]
    for pkg in find_pip_pkgs(diry):
        units.extend(pkgToUnits(pkg))
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
    modules = []
    if 'py_modules' in d and d['py_modules'] is not None:
        modules.extend(d['py_modules'])
    if 'modules' in d and d['modules'] is not None:
        modules.extend(d['modules'])
    if len(modules) == 0:
        modules = None
    return {
        'rootdir': kw['rootdir'] if 'rootdir' in kw else None,
        'project_name': d['name'] if 'name' in d else None,
        'version': d['version'] if 'version' in d else None,
        'repo_url': d['url'] if 'url' in d else None,
        'packages': d['packages'] if 'packages' in d else None,
        'modules': modules,
        'scripts': d['scripts'] if 'scripts' in d else None,
        'author': d['author'] if 'author' in d else None,
        'description': d['description'] if 'description' in d else None,
    }
