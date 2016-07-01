"""Convenience wrappers around pydep methods

"""

import subprocess
import sys
import os
import os.path
import json

import pydep.setup_py
import pydep.req

from typing import Any, List, Dict
from operator import itemgetter

def setup_dirs(rootdir: str) -> List[str]:
    return pydep.setup_py.setup_dirs(rootdir)

# pydep_in_python2 uses Python2 to run pydep and returns parsed JSON object.
def pydep_in_python2(cmd: str, dir: str) -> Any:
    rootdir = os.environ.get('SRCLIBPY_ROOTDIR')
    pydep = os.path.join(rootdir, ".env", "bin", "pydep-run.py")
    python = os.path.join(rootdir, ".env", "bin", "python2.7")
    process = subprocess.Popen([python, pydep, cmd, dir], stdout=subprocess.PIPE)
    out, err = process.communicate()
    if err is not None:
        raise Exception(err)
    data = json.loads(out.decode('utf-8'))
    return data

def setup_info_dir(setup_dir: str) -> Any:
    try:
        info, err = pydep.setup_py.setup_info_dir(setup_dir)
        if err is not None:
            raise Exception(err)
        return info
    except SyntaxError as e:
        return pydep_in_python2("info", setup_dir)
    else:
        raise

def requirements_from_requirements_txt(diry: str) -> List[Dict[str, Any]]:
    reqs, err = pydep.req.requirements_from_requirements_txt(diry)
    if err is not None:
        raise Exception(err)
    for r in reqs:
        if r.to_dict()['project_name'] == 'wsgiref':
            # Kludge: wsgiref's setup.py messes with sys.stdout, so should not be resolved
            continue
        try:
            r.resolve()
        except:
            sys.stderr.write('failed to resolve requirement {}\n'.format(r))
    return sorted([r.to_dict() for r in reqs], key=itemgetter('key'))

def requirements(pkgdir: str, resolve: bool) -> List[Dict[str, Any]]:
    try:
        pkgreqs, err = pydep.req.requirements(pkgdir, resolve)
        if err is not None:
            raise Exception(err)
        return sorted(pkgreqs, key=itemgetter('key'))
    except SyntaxError as e:
        pkgreqs = pydep_in_python2("dep", pkgdir)
        return sorted(pkgreqs, key=itemgetter('key'))
    else:
        raise
