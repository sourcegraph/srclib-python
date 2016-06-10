from .structures import *
from .util import normalize

from . import pydepwrap

import logging
log = logging.getLogger('srclib-python.grapher.django')


# find_units finds all Django application source units rooted at a directory.
#
# - diry is the root directoy at which to start the search. If this
#   directory also contains a requirements.txt file, its dependencies
#   will be included in all found source units.
# - max_depth is the maximum recursion depth to search for units.
def find_units(diry: str, max_depth: int = 5) -> List[Unit]:
    units = find_units_(diry, max_depth = max_depth)

    global_requirements = None # type: List[Dict]
    if os.path.isfile(os.path.join(diry, "requirements.txt")):
        global_requirements = pydepwrap.requirements_from_requirements_txt(diry)

    for unit in units:
        unit.Files = sorted(get_source_files(unit.Dir))
        for i in range(len(unit.Files)):
            f = normalize(os.path.join(unit.Dir, unit.Files[i]))
            if f.startswith('./'):
                f = f[2:]
            unit.Files[i] = f

        reqs = [] # type: List[Dict]
        reqfiles = [] # type: List[str]
        if global_requirements is not None:
            reqs.extend(global_requirements)
            reqfiles.append(normalize(os.path.join(diry, "requirements.txt")))
        try:
            reqs_ = pydepwrap.requirements_from_requirements_txt(unit.Dir)
            reqs.extend(reqs_)
            reqfiles.append(normalize(os.path.join(diry, "requirements.txt")))
        except Exception as e:
            pass

        # Sort package and module lists for stable ordering
        for req in reqs:
            if 'packages' in req and isinstance(req['packages'], list):
                req['packages'] = sorted(req['packages'])
            if 'modules' in req and isinstance(req['modules'], list):
                req['modules'] = sorted(req['modules'])
            if 'py_modules' in req and isinstance(req['py_modules'], list):
                req['py_modules'] = sorted(req['py_modules'])

        deps = [] # type: List[UnitKey]
        for r in reqs:
            dep = pkgToUnitKey(r)
            if dep is not None:
                deps.append(dep)
        unit.Dependencies = deps
        unit.Data = Data(Reqs=[req for req in reqs if checkReq(req)], ReqFiles=reqfiles)

    return units

# find_units_ is a recursive helper that generates the list of proto-units.
def find_units_(diry: str, max_depth: int = 5) -> List[Unit]:
    if os.path.basename(diry) == "testdata":
        return []               # don't descend into testdata/ directory

    if max_depth < 0: return []

    if os.path.isfile(os.path.join(diry, "manage.py")):
        return [Unit(
            Name = os.path.basename(os.path.abspath(diry)),
            Type = UNIT_DJANGO,
            Dir = normalize(diry),
            Files = None,
            Dependencies = None,
            Repo = None,
            CommitID = None,
            Version = None,
            Data = None,
        )]

    units = []
    for entry in os.scandir(diry): # type: ignore (os.scandir exists)
        if entry.is_dir():
            units.extend(find_units_(entry.path, max_depth = max_depth - 1))
    return units
