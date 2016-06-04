"""Shim to call pydep methods that have to run with a specific Python version

NOTE: The Python 2 implementations do not work, because of a change to the pip.req module in Python 2.7.11

"""

import subprocess
import sys
import os
import os.path
import json

import pydep.setup_py
import pydep.req

from typing import Any, List, Dict

python2 = os.getenv("PYTHON2")
if python2 is None:
    sys.stdout.write("PYTHON2 environment variable must be set\n")
    sys.exit(1)

def setup_dirs(pyversion: int, rootdir: str) -> List[str]:
    if pyversion == 3:
        return pydep.setup_py.setup_dirs(rootdir)

    cmd = \
"""
import pydep.setup_py
import json
import sys

setup_dirs = pydep.setup_py.setup_dirs("{}")
json.dump(setup_dirs, sys.stdout)
""".format(rootdir)
    p = subprocess.run([python2, "-c", cmd], check=True, stdout=subprocess.PIPE) # type: ignore (subprocess.run added in 3.5)
    return json.loads(p.stdout.decode("utf-8"))

def setup_info_dir(pyversion: int, setup_dir: str) -> Any:
    if pyversion == 3:
        info, err = pydep.setup_py.setup_info_dir(setup_dir)
        if err is not None:
            raise Exception(err)
        return info

    cmd = \
"""
import pydep.setup_py
import json
import sys

setup_info_and_err = pydep.setup_py.setup_info_dir("{}")
json.dump(setup_info_and_err, sys.stdout)
""".format(setup_dir)
    p = subprocess.run([python2, "-c", cmd], check=True, stdout=subprocess.PIPE) # type: ignore (subprocess.run added in 3.5)
    res = json.loads(p.stdout.decode("utf-8"))
    info, err = res[0], res[1]
    if err is not None:
        raise Exception(err)
    return info

def requirements_from_requirements_txt(pyversion: int, diry: str) -> List[Dict]:
    if pyversion == 3:
        reqs, err = pydep.req.requirements_from_requirements_txt(diry)
        if err is not None:
            raise Exception(err)
        for r in reqs:
            try:
                r.resolve()
            except:
                sys.stderr.write('failed to resolve requirement {}\n'.format(r))
        return [r.to_dict() for r in reqs]

    cmd = \
"""
import pydep.req
import json
import sys

reqs, err = pydep.req.requirements_from_requirements_txt("{}")
if err is not None:
    raise Exception(err)
for r in reqs:
    try:
        r.resolve()
    except:
        sys.stderr.write("failed to resolve requirement " + str(r) + "\\n")
json.dump([r.to_dict() for r in reqs], sys.stdout)
""".format(diry)
    p = subprocess.run([python2, "-c", cmd], check=True, stdout=subprocess.PIPE) # type: ignore (subprocess.run added in 3.5)
    reqs = json.loads(p.stdout.decode("utf-8"))
    return reqs
