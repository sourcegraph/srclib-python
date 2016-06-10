import glob # type: ignore (ignore strange redefinition of glob mypy error)
import os
import os.path
import re
import sys

from .structures import *
from .util import normalize

module_def_pattern = re.compile(r'static struct PyModuleDef ([A-Za-z0-9_]+)module\s')

class Builtin:
    def __init__(
            self,
            path: str,
            start: int,
            end: int,
            filename: str,
    ) -> None:
        self.path = path
        self.start = start
        self.end = end
        self.filename = normalize(filename)

    def __repr__(self) -> str:
        return 'Builtin{}'.format(self.__dict__)

    def to_def(self) -> Def:
        name = os.path.basename(self.path)
        return Def(
            Repo=BUILTIN_UNIT_KEY.Repo,
            Unit=BUILTIN_UNIT_KEY.Name,
            UnitType=BUILTIN_UNIT_KEY.Type,
            Path=self.path,
            Kind='', # TODO(beyang)
            Name=name,
            File=self.filename,
            DefStart=self.start,
            DefEnd=self.end,
            Exported=(not name.startswith('_')),
            Data=DefFormatData(
                Name=name,
                Keyword='',
                Type='',
                Kind='',
                Separator='',
            ),
            Builtin=True,
        )

def get_c_source_files(diry: str) -> List[str]:
    return glob.glob(os.path.join(diry, '**', '*.c'), recursive=True) # type: ignore (recursive=True)

def find_modules(modules_dir) -> List[Builtin]:
    builtins = [] # type: List[Builtin]
    cfiles = get_c_source_files(modules_dir)

    for i, cfile in enumerate(cfiles):
        sys.stderr.write('processing file {}: {}/{}\n'.format(cfile, i, len(cfiles)))

        modules = []
        with open(cfile) as f:
            text = f.read()
        matches = module_def_pattern.finditer(text)
        for match in matches:
            if match.group(1) == 'xx': # false positives
                continue
            modules.append(Builtin(
                path = match.group(1),
                start = match.start(1),
                end = match.end(1),
                filename = cfile,
            ))
        builtins.extend(modules)
        for module in modules:
            def_pattern = r'"({}(?:\.[A-Za-z0-9_]+)+)"'.format(module.path)
            for match in re.compile(def_pattern).finditer(text):
                path = match.group(1)
                if path.endswith('.c') or path.endswith('.h') or path == 'xx': # false positives
                    continue
                builtins.append(Builtin(
                    path = path,
                    start = match.start(1),
                    end = match.end(1),
                    filename = cfile,
                ))
    return builtins
