import json
import os

from copy import copy
from typing import List, Dict, Tuple, NamedTuple, Any

class UnitKey:
    def __init__(
            self,
            Name: str,
            Type: str,
            Repo: str,
            CommitID: str,
            Version: str,
    ) -> None:
        self.Name = Name
        self.Type = Type
        self.Repo = Repo
        self.CommitID = CommitID
        self.Version = Version

    # def __repr__(self):
    #     return json.dumps(self.__dict__)

class Unit:
    def __init__(
            self,
            Name: str,
            Type: str,
            Files: List[str],
            Dir: str,
            Dependencies: List[UnitKey] = None,
            Repo: str = "",
            CommitID: str = "",
            Version: str = "",
            Data: List[Any] = None, # List of raw requirements
    ) -> None:
        self.Name = Name
        self.Type = Type
        self.Repo = Repo
        self.CommitID = CommitID
        self.Version = Version
        self.Files = Files
        self.Dir = Dir
        self.Dependencies = Dependencies if Dependencies is not None else []
        self.Data = Data

    def todict(self):
        d = copy(self.__dict__)
        for i in range(len(d['Dependencies'])):
            d['Dependencies'][i] = copy(d['Dependencies'][i].__dict__)
        return d

DefKey = NamedTuple('DefKey', [
    ('Repo', str),
    ('Unit', str),
    ('UnitType', str),
    ('Path', str),
])

Def = NamedTuple('Def', [
    ('Repo', str),
    ('Unit', str),
    ('UnitType', str),
    ('Path', str),
    ('Kind', str),
    ('Name', str),
    ('File', str),
    ('DefStart', int),
    ('DefEnd', int),
    ('Exported', str),
    ('Data', Any),
])

Ref = NamedTuple('Ref', [
    ('DefRepo', str),
    ('DefUnit', str),
    ('DefUnitType', str),
    ('DefPath', str),
    ('Def', str),
    ('Unit', str),
    ('UnitType', str),
    ('File', str),
    ('Start', int),
    ('End', int),
    ('ToBuiltin', bool),
])

Doc = NamedTuple('Doc', [
    ('Unit', str),
    ('UnitType', str),
    ('Path', str),
    ('Format', str),
    ('Data', str),
    ('File', str),
])

UNIT_PIP = "PipPackage"
UNIT_DJANGO = "DjangoApp"
REPO_UNRESOLVED = "?"
STDLIB_UNIT_KEY = UnitKey(
    Name = 'Python',
    Type = UNIT_PIP,
    Repo = 'github.com/python/cpython',
    CommitID = '',
    Version='',
)

"""
Helper functions
"""

def get_source_files(diry: str) -> List[str]:
    """ Get list of all Python source files in a directory. """
    files = [] # type: List[str]
    for path, _, filenames in os.walk(diry):
        rel_dir = os.path.relpath(path, diry)
        files.extend([os.path.normpath(os.path.join(rel_dir, f)) for f in filenames if os.path.splitext(f)[1] == '.py'])
    if diry != "" and diry != ".":
        for i in range(len(files)):
            if files[i].startswith('./'):
                files[i] = files[i][2:]
    return files

def pkgToUnitKey(pkg: Dict) -> UnitKey:
    return UnitKey(
        Name = pkg['project_name'],
        Type = UNIT_PIP,
        Repo = REPO_UNRESOLVED,
        Version = "",
        CommitID = "",
    )
