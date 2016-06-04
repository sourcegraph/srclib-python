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

def setup_dirs(rootdir: str) -> List[str]:
    return pydep.setup_py.setup_dirs(rootdir)


def setup_info_dir(setup_dir: str) -> Any:
    info, err = pydep.setup_py.setup_info_dir(setup_dir)
    if err is not None:
        raise Exception(err)
    return info

def requirements_from_requirements_txt(diry: str) -> List[Dict]:
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
    return [r.to_dict() for r in reqs]
