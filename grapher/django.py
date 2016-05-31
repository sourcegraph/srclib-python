import pydep

from .structures import *

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
        gr, err = pydep.req.requirements_from_requirements_txt(diry)
        if err is None:
            for e in gr: e.resolve()
            global_requirements = [x.to_dict() for x in gr]
        else:
            log.info('could not get top-level requirements: {}'.format(err))

    for unit in units:
        unit.Files = sorted(get_source_files(unit.Dir))
        for i in range(len(unit.Files)):
            f = os.path.join(unit.Dir, unit.Files[i])
            if f.startswith('./'):
                f = f[2:]
            unit.Files[i] = f

        reqs = [] # type: List[Dict]
        reqfiles = [] # type: List[str]
        if global_requirements is not None:
            reqs.extend(global_requirements)
            reqfiles.append(os.path.join(diry, "requirements.txt"))
        reqs_, err = pydep.req.requirements_from_requirements_txt(unit.Dir)
        if err is None:
            for rq in reqs_: rq.resolve()
            reqs.extend([x.to_dict() for x in reqs_])
            reqfiles.append(os.path.join(diry, "requirements.txt"))

        # Sort package and module lists for stable ordering
        for req in reqs:
            if 'packages' in req:
                req['packages'] = sorted(req['packages'])
            if 'modules' in req:
                req['modules'] = sorted(req['modules'])
            if 'py_modules' in req:
                req['py_modules'] = sorted(req['py_modules'])

        deps = [] # type: List[UnitKey]
        for r in reqs:
            deps.append(pkgToUnitKey(r))
        unit.Dependencies = deps
        unit.Data = Data(Reqs=reqs, ReqFiles=reqfiles)

    return units

# find_units_ is a recursive helper that generates the list of proto-units.
def find_units_(diry: str, max_depth: int = 5) -> List[Unit]:
    if max_depth < 0: return []

    if os.path.isfile(os.path.join(diry, "manage.py")):
        return [Unit(
            Name = os.path.basename(os.path.abspath(diry)),
            Type = UNIT_DJANGO,
            Dir = diry,
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
