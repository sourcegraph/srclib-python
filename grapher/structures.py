import json
import os

from copy import copy
from typing import List, Dict, Tuple, NamedTuple, Union, Any

from .util import normalize

# TODO(beyang): START HERE: fix JSON marshaling / unmarshaling issue

class Data:
    def __init__(self,
                 Reqs: List[Dict[str, Any]] = [],
                 ReqFiles: List[str] = [],
    ) -> None:
        self.Reqs = Reqs # type: List[Dict]
        self.ReqFiles = ReqFiles # type: List[str]

class UnitKey:
    def __init__(self,
                 Name: str,
                 Type: str,
                 Repo: str = "",
                 CommitID: str = "",
                 Version: str = "",
    ) -> None:
        self.Name = Name
        self.Type = Type
        self.Repo = Repo
        self.CommitID = CommitID
        self.Version = Version

    def __eq__(self, other) -> bool:
        return self.__dict__ == other.__dict__

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
            Data: Data = None, # List of raw requirements
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

    def key(self) -> UnitKey:
        return UnitKey(
            Name=self.Name,
            Type=self.Type,
            Repo=self.Repo,
            CommitID=self.CommitID,
            Version=self.Version,
        )

class DefFormatData:
    def __init__(
            self,
            Name: str,
            Keyword: str,
            Type: str,
            Kind: str,
            Separator: str,
    ) -> None:
        self.Name = Name
        self.Keyword = Keyword
        self.Type = Type
        self.Kind = Kind
        self.Separator = Separator

DefKey = NamedTuple('DefKey', [
    ('Repo', str),
    ('Unit', str),
    ('UnitType', str),
    ('Path', str),
])

class Ref:
    def __init__(
            self,
            DefRepo: str,
            DefUnit: str,
            DefUnitType: str,
            DefPath: str,
            Def: bool,
            Unit: str,
            UnitType: str,
            File: str,
            Start: int,
            End: int,
            ToBuiltin: bool,
    ) -> None:
        self.DefRepo = DefRepo
        self.DefUnit = DefUnit
        self.DefUnitType = DefUnitType
        self.DefPath = DefPath
        self.Def = Def
        self.Unit = Unit
        self.UnitType = UnitType
        self.File = File
        self.Start = Start
        self.End = End
        self.ToBuiltin = ToBuiltin

class Def:
    def __init__(
            self,
            Repo: str,
            Unit: str,
            UnitType: str,
            Path: str,
            Kind: str,
            Name: str,
            File: str,
            DefStart: int,
            DefEnd: int,
            Exported: bool,
            Data: DefFormatData,
            Builtin: bool = False,
    ) -> None:
        self.Repo = Repo
        self.Unit = Unit
        self.UnitType = UnitType
        self.Path = Path
        self.Kind = Kind
        self.Name = Name
        self.File = File
        self.DefStart = DefStart
        self.DefEnd = DefEnd
        self.Exported = Exported
        self.Data = Data
        self.Builtin = Builtin

    def defref(self) -> Ref:
        return Ref(
            DefRepo=self.Repo,
            DefUnit=self.Unit,
            DefUnitType=self.UnitType,
            DefPath=self.Path,
            Def=True,
            Unit=self.Unit,
            UnitType=self.UnitType,
            File=self.File,
            Start=self.DefStart,
            End=self.DefEnd,
            ToBuiltin=self.Builtin,
        )

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
UNIT_TEST = "PythonTestPackage"
REPO_UNRESOLVED = "?"
STDLIB_UNIT_KEY = UnitKey(
    Name = 'Python',
    Type = UNIT_PIP,
    Repo = 'github.com/python/cpython',
    CommitID = '',
    Version='',
)
BUILTIN_UNIT_KEY = UnitKey(
    Name = '__builtin__',
    Type = UNIT_PIP,
    Repo = 'github.com/python/cpython',
    CommitID = '',
    Version = '',
)
TEST_UNIT_KEY = UnitKey(
    Name = '__test__',
    Type = UNIT_TEST,
    Repo = '',
    CommitID = '',
    Version = '',
)

# SETUPTOOLS_UNIT_KEY is the unit key for the setuptools source unit. This
# package is treated specially as it is always available (like the standard lib)
# even when it is not explicitly specified as a requirement. Unlike the standard
# lib, the setuptools repository builds successfully. However, it needs to be
# included as a requirement for all third-party Python libraries.
SETUPTOOLS_UNIT_KEY = UnitKey(
    Name = 'setuptools',
    Type = UNIT_PIP,
    Repo = 'github.com/pypa/setuptools',
    CommitID = '',
    Version=''
)


"""
Helper functions
"""

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
    return files

def pkgToUnitKey(pkg: Dict) -> UnitKey:
    if not checkReq(pkg):
        return None
    return UnitKey(
        Name = pkg['project_name'],
        Type = UNIT_PIP,
        Repo = REPO_UNRESOLVED,
        Version = "",
        CommitID = "",
    )

def fromJSONable(j: Any, dst_t: Union[type, List, Dict]) -> Any:
    if j is None:
        return None
    elif str(dst_t) == 'typing.Any':
        return copy(j)
    elif str(dst_t).startswith('typing.List['):
        if type(j) is not list:
            raise Exception('attempting to unmarshal non-list {} into list'.format(j))
        return [fromJSONable(e, dst_t.__parameters__[0]) for e in j] # type: ignore (List.__parameters_ exists)
    elif dst_t is list:
        if type(j) is not list:
            raise Exception('attempting to unmarshal non-list into list')
        return copy(j)
    elif str(dst_t).startswith('typing.Dict['):
        if type(j) is not dict:
            raise Exception('attempting to unmarshal non-dict into dict')
        if dst_t.__parameters__[0] is not str: # type: ignore (Dict.__parameters_ exists)
            raise Exception('attempting to unmarshal into a dict with non-str keys')
        value_t = dst_t.__parameters__[1] # type: ignore (Dict.__parameters_ exists)
        return {k: fromJSONable(v, value_t) for k, v in j.items()}
    elif dst_t is dict:
        if type(j) is not dict:
            raise Exception('attempting to unmarshal non-dict into dict')
        return copy(j)
    elif dst_t is str:
        if type(j) is not str:
            raise Exception('attempting to umarshal non-str into str')
        return j
    elif dst_t is int or dst_t is float:
        if type(j) is not int and type(j) is not float:
            raise Exception('attempting to unmarshal non-number into number')
        return j
    else: # dst_t is a Class
        if not isinstance(dst_t, type):
            raise Exception("couldn't find a constructor for type {}".format(dst_t))
        if not isinstance(j, dict):
            raise Exception("couldn't recognize JSON j (type {}) as serializable into type {}".format(type(j), dst_t))
        params = copy(dst_t.__init__.__annotations__) # type: ignore (SomeClass.__init__ exists)
        if 'return' in params:
            del params['return']
        jk = set([e for e in j.keys()])
        pk = set([e for e in params.keys()])
        if not jk.issubset(pk):
            raise Exception('attempting to unmarshal from JSON object into class {}: {} is not a subset of {}'.format(dst_t, jk, pk))
        d = {k: fromJSONable(v, params[k]) for k, v in j.items()}
        return dst_t(**d)

def toJSONable(c: Any) -> Union[Dict, List, str, int]:
    if isinstance(c, int):
        return c
    elif isinstance(c, str):
        return c
    elif isinstance(c, list):
        return [toJSONable(e) for e in c]
    elif c is None:
        return c
    elif isinstance(c, dict):
        for k in c:
            if not isinstance(k, str):
                raise Exception("cannot serialize dictionary with key {} (type wasn't str)".format(k))
        return {k: toJSONable(v) for k, v in c.items()}
    else:
        fields = [f for f in dir(c) if not f.startswith('_')]
        if len(fields) == 0:
            return None
        return {f: toJSONable(c.__getattribute__(f)) for f in fields if not ismethod(c.__getattribute__(f))}

def ismethod(m: Any) -> bool:
    return hasattr(m, '__call__') and hasattr(m, '__self__')

def checkReq(req: Dict) -> bool:
    return req['project_name'] is not None
