from collections import namedtuple
import os
import re

import jedi

from .structures import *
from .util import normalize

def _debug_print_tree(node, indent=0, func=repr):
    """ Print visual representation of Jedi AST. """
    ret = "\t" * indent + func(node) + "\n"

    children = getattr(node, "children", None)
    if children:
        for child in children:
            ret += _debug_print_tree(child, indent=indent+1, func=func)
    return ret


class FileGrapherException(Exception):
    """ Something went wrong while graphing the file. """

class FileGrapher(object):
    """
    FileGrapher is used to extract definitions and references from single Python source file.
    """
    _exported_regex = re.compile('\_[a-zA-Z0-9]')

    def __init__(self, base_dir, source_file, unit, unit_type, modulePathPrefixToDep, syspath, log):
        """
        Create a new grapher.
        """
        self._base_dir = base_dir
        self._abs_base_dir = os.path.abspath(base_dir)
        self._file = source_file
        self._unit = unit
        self._unit_type = unit_type
        self._modulePathPrefixToDep = modulePathPrefixToDep
        self._syspath = list(reversed(sorted(syspath)))
        self._virtual_env = os.getenv('VIRTUAL_ENV')
        self._log = log
        self._source = None
        self._defs = {}
        self._refs = {}
        self._docs = {}
        self._load()

        self._stdlibpaths = []
        for p in syspath:
            if not p.endswith('site-packages'):
                self._stdlibpaths.append(p)

    def graph(self):
        # Add module/package defs.
        basic_module_path = normalize(os.path.relpath(self._file, self._base_dir))
        name = os.path.basename(basic_module_path)
        module_keyword = 'module'
        if basic_module_path.startswith('./'):
            basic_module_path = basic_module_path[2:]
        if os.path.basename(self._file) == '__init__.py':
            dot_path = normalize(os.path.dirname(basic_module_path)).replace('/', '.')
            module_keyword= 'package'
            name = dot_path.split('.')[-1]
        else:
            dot_path = normalize(os.path.splitext(basic_module_path)[0]).replace('/', '.')
        module_path = '{}/{}.{}'.format(basic_module_path, dot_path, dot_path.split('.')[-1])
        self._add_def(Def(
            Repo="",
            Unit=self._unit,
            UnitType=self._unit_type,
            Path=module_path,
            Kind='module',
            Name=name,
            File=normalize(self._file),
            DefStart=0,
            DefEnd=0,
            Exported=True,
            Data=DefFormatData(
                Name=dot_path,
                Keyword=module_keyword,
                Type='',
                Kind=module_keyword,
                Separator='',
            ),
        ))
        # TODO(beyang): extract module/package-level doc.

        # Get occurrences of names via Jedi.
        try:
            jedi_names = jedi.names(source=self._source, path=self._file, all_scopes=True, references=True)
        except Exception as e:
            raise FileGrapherException('failed to parse {}: {}'.format(self._file, str(e)))

        jedi_defs, jedi_refs = [], []
        for jedi_name in jedi_names:
            # Imports should be refs.
            if jedi_name.is_definition() and jedi_name.type != 'import':
                jedi_defs.append(jedi_name)
            else:
                jedi_refs.append(jedi_name)

        # Defs and docs.
        for jedi_def in jedi_defs:
            self._log.debug(
                'processing def: %s | %s | %s',
                jedi_def.desc_with_module,
                jedi_def.name,
                jedi_def.type,
            )
            try:
                def_, doc = self._jedi_def_to_def(jedi_def)
                self._add_def(def_)
                if doc is not None and doc.Data is not None and len(doc.Data) > 0:
                    self._add_doc(doc)
            except Exception as e:
                self._log.error(
                    u'failed to process def `%s`: %s',
                    jedi_def.name,
                    e,
                )
                continue

        # Refs.
        for jedi_ref in jedi_refs:
            self._log.debug(
                'processing ref: %s | %s | %s',
                jedi_ref.desc_with_module,
                jedi_ref.name,
                jedi_ref.type,
            )

            ref_def = self._find_def_for_ref(jedi_ref)
            # We found nothing.
            if ref_def is None:
                continue

            try:
                sg_def = self._jedi_def_to_def_key(ref_def)
            except Exception as e:
                self._log.error(
                    u'failed to process def to def-key `%s`: %s',
                    ref_def.name,
                    e,
                )
                continue

            ref_start = self._to_offset(jedi_ref.line, jedi_ref.column)
            ref_end = ref_start + len(jedi_ref.name)

            self._add_ref(Ref(
                DefRepo=sg_def.Repo,
                DefUnit=sg_def.Unit,
                DefUnitType=sg_def.UnitType,
                DefPath=sg_def.Path,
                Unit=self._unit,
                UnitType=self._unit_type,
                Def=False,
                File=normalize(self._file),
                Start=ref_start,
                End=ref_end,
                ToBuiltin=ref_def.in_builtin_module(),
            ))

        return self._defs, self._refs, self._docs

    def _find_def_for_ref(self, jedi_ref, max_depth=100):
        """ Attempt to lookup definition for the reference. If lookup fails return None. """
        ref_def = jedi_ref
        # If def is import, then follow it.
        depth = 0
        while (not ref_def.is_definition() or ref_def.type == "import") and depth < max_depth:
            depth += 1
            # noinspection PyBroadException
            try:
                ref_defs = ref_def.goto_assignments()
            except:
                self._log.error(u'jedi error getting definitions for reference {}'.format(jedi_ref))
                break

            if len(ref_defs) == 0:
                break

            ref_def = ref_defs[0]
        else:
            self._log.debug(
                'ref def search (precondition failed) | %s | %s | %s',
                ref_def.is_definition(),
                ref_def.type,
                ref_def.name
            )

        if ref_def.type == "import":
            # We didn't find anything.
            self._log.debug('ref def not found')
            return None

        return ref_def

    def _load(self):
        """ Load file in memory. """
        with open(self._file) as f:
            self._source = f.read()

        source_lines = self._source.splitlines(True)
        self._cumulative_off = [0]
        for line in source_lines:
            self._cumulative_off.append(self._cumulative_off[-1] + len(line))

    def _jedi_def_is_ivar(self, df) -> bool:
        try:
            return (df.parent().type == 'function' and
                    df.parent().parent().type in ['class', 'instance'] and
                    df.description.startswith('self.'))
        except:
            return False

    def _jedi_def_ivar_classname(self, df) -> str:
        return '.'.join(df.full_name.split('.')[:-1])

    # _jedi_def_to_name_and_type returns the display name and type of
    # a Jedi definition. For statements, it displays the set of
    # inferred possible values as the type.
    def _jedi_def_to_name_and_type(self, df) -> Tuple[str, str]:
        if df.type == 'function':
            typ_str = '('+', '.join([self._jedi_def_to_name_and_type(p)[0] for p in df.params])+')'
            if df.parent().type == 'class':
                return df.parent().name+'.'+df.name, typ_str
            else:
                return df.name, typ_str
        elif df.type == 'class': # class ${classname}(${superclass}[, ${superclass}]...)
            # best-effort extract name of superclass(es)
            try:
                return "{}({})".format(df.name, df._definition.base.get_super_arglist().get_code()), ''
            except Exception:
                return df.name, ''
        elif df.type == 'statement':
            parent = ''
            if df.parent().type == 'class':
                parent = df.parent().name+'.'
            elif self._jedi_def_is_ivar(df):
                parent = "("+df.parent().parent().name+') self.'

            def_types = set([])
            for df_ in df.goto_assignments():
                idx = df_.description.index('=')
                if idx != -1:
                    def_types.add(df_.description[idx+1:].strip())
                else:
                    def_types.add('?')

            if len(def_types) == 0:
                return parent + df.name, ''
            elif len(def_types) == 1:
                return parent + df.name, '= '+list(def_types)[0]
            else:
                return parent + df.name, '= {'+', '.join(sorted(def_types))+'}'
        elif df.type == 'param':
            return df.name, ''
        else:
            self._log.debug('could not format unrecognized Jedi definition type {}'.format(df.type))
            return df.name, ''

    def _jedi_def_to_format_data(self, df) -> DefFormatData:
        name, typ = self._jedi_def_to_name_and_type(df)
        keyword, sep = '', ''
        if df.type == 'function':
            keyword = 'def'
        elif df.type == 'class':
            keyword = 'class'
            sep = ' '
        elif df.type == 'statement':
            keyword = ''
            sep = ' '
        elif df.type == 'param':
            pass
        else:
            self._log.debug('could not format unrecognized Jedi definition type {}'.format(df.type))

        return DefFormatData(
            Name = name,
            Type = typ,
            Keyword = keyword,
            Kind = df.type,
            Separator = sep,
        )

    def _jedi_def_to_def(self, d):
        dk = self._jedi_def_to_def_key(d)
        start = self._to_offset(d.line, d.column)
        end = start + len(d.name)
        def_ = Def(
            Repo=dk.Repo,
            Unit=dk.Unit,
            UnitType=dk.UnitType,
            Path=dk.Path,
            Kind=d.type,
            Name=d.name,
            File=normalize(self._file),
            DefStart=start,
            DefEnd=end,
            Exported=self._is_exported(d.name),
            Data=self._jedi_def_to_format_data(d),
        )

        doc = None
        docstring = d.docstring(raw=True)
        if docstring is not None:
            doc = Doc(
                Unit=def_.Unit,
                UnitType=def_.UnitType,
                Path=def_.Path,
                Format='plaintext',
                Data=docstring,
                File=def_.File,
            )

        return def_, doc

    def _jedi_def_to_def_key(self, d):
        path, dep = self._full_name_and_dep(d)
        if dep is not None:
            repo, unit, unit_type = dep.Repo, dep.Name, dep.Type
        else:
            repo, unit, unit_type = "", self._unit, self._unit_type
        return DefKey(
            Repo=repo,
            Unit=unit,
            UnitType=unit_type,
            Path=path,
        )

    # _rel_module_path returns (relative_module_path, is_internal)
    # TODO(beyang): replace startswith with os.path.commonpath (Python 3 function)
    def _rel_module_path(self, module_path):
        if module_path.startswith(self._abs_base_dir):
            return normalize(os.path.relpath(module_path, self._abs_base_dir)), True # internal

        for p in self._syspath:
            if p == '':
                continue
            if module_path.startswith(p):
                return normalize(os.path.relpath(module_path, p)), False # external

        if self._virtual_env is not None and module_path.startswith(self._virtual_env):
            module_path = normalize(os.path.relpath(module_path, self._virtual_env))
            return module_path.split('/site-packages/', 1)[1], False

        return None, False

    def _module_to_dep(self, m):
        # Check explicit pip dependencies
        for pkg, dep in self._modulePathPrefixToDep.items():
            if m.startswith(pkg):
                return dep, None
        for stdlibpath in self._stdlibpaths:
            if os.path.lexists(os.path.join(stdlibpath, m)):
                # Standard lib module
                return UnitKey(Repo=STDLIB_UNIT_KEY.Repo,
                               Type=STDLIB_UNIT_KEY.Type,
                               Name=STDLIB_UNIT_KEY.Name,
                               CommitID=STDLIB_UNIT_KEY.CommitID,
                               Version=STDLIB_UNIT_KEY.Version), None
        return None, ('could not find dep module for module %s, candidates were %s' % (m, repr(self._modulePathPrefixToDep.keys())))

    def _full_name_and_dep(self, d):
        if d.in_builtin_module():
            return d.full_name, UnitKey(Repo=STDLIB_UNIT_KEY.Repo, Type=UNIT_PIP, Name="__builtin__", CommitID="", Version="")

        if d.module_path is None:
            raise Exception('no module path for definition %s' % repr(d))

        # This detects `self` and `cls` parameters makes them to point to the class:
        # To trigger this parameters must be for a method (a class function).
        if d.type == 'param' and (d.name == 'self' or d.name == 'cls') and d.parent().parent().type == 'class':
            d = d.parent().parent()

        module_path, is_internal = self._rel_module_path(d.module_path)
        if module_path is None:
            raise Exception('could not find name for module path %s' % d.module_path)

        if self._jedi_def_is_ivar(d):
            classname = self._jedi_def_ivar_classname(d)
            path = '{}/{}.{}'.format(module_path, classname, d.name)
        else:
            path = '{}/{}.{}'.format(module_path, d.full_name, d.name)

        dep = None
        if not is_internal:
            dep, err = self._module_to_dep(module_path)
            if err is not None:
                raise Exception(err)

        return path, dep

    @staticmethod
    def _get_module_parent_from_module_path(module_path):
        if os.path.basename(module_path) == '__init__.py':
            parent_module =  os.path.dirname(os.path.dirname(module_path))
        else:
            parent_module = os.path.dirname(module_path)
        return parent_module.replace(os.sep, '.')

    def _abs_module_path_to_relative_module_path(self, module_path):
        rel_path = module_path
        try:    
            rel_path = os.path.relpath(module_path, self._base_dir)
            if not rel_path.startswith('..'):
                return rel_path
        except ValueError:
            # (alexsaveliev) virtualenv may use python from the different location.
            # This situation may cause "path is on drive C:, start on drive D:"
            pass

        components = module_path.split(os.sep)
        pi1 = pi2 = -1
        prev_component = None
        prev_index = -1
        for i, component in enumerate(components):
            if component in ['site-packages', 'dist-packages']:
                pi1 = i
                break
            # Fallback.
            # Windows case .env/lib/file.py, Unix case .env/lib/python.../file.py
            if pi2 == -1 and component == 'lib' and prev_component == '.env':
                pi2 = i
            elif pi2 == prev_index and component.startswith('python'):
                pi2 = i
            elif pi2 == -1 and prev_component is not None and prev_component.lower().startswith('python') and component.lower() == 'lib':
                pi2 = i
            prev_component = component
            prev_index = i

        pi = pi1 if pi1 != -1 else pi2
        if pi != -1:
            return os.path.join(*components[pi + 1:])

        raise FileGrapherException('could not convert absolute module path {} '
                                   'to relative module path'.format(module_path))

    def _is_exported(self, name):
        """ Checks if keyword is public or non-public.

        There are no private methods/variables in Python, however:

        There is a convention to prefix private methods/variables with
        underscore. And that's what we're going to use.

        https://www.python.org/dev/peps/pep-0008/#id40
        """
        return self._exported_regex.match(name) is None

    def _add_def(self, d):
        """ Add a definition, also adds a self-reference. """
        self._log.debug('adding def: %s | %s | %s', d.Name, d.Path, d.Kind)
        if d.Path not in self._defs:
            self._defs[d.Path] = d
        # Add self-reference.
        self._add_ref(Ref(
            DefRepo=d.Repo,
            DefUnit=d.Unit,
            DefUnitType=d.UnitType,
            DefPath=d.Path,
            Unit=self._unit,
            UnitType=self._unit_type,
            Def=True,
            File=d.File,
            Start=d.DefStart,
            End=d.DefEnd,
            ToBuiltin=False,
        ))

    def _add_ref(self, r):
        """ Add a reference. """
        self._log.debug('adding ref: %s', r.DefPath)
        key = (r.DefPath, r.File, r.Start, r.End)
        if key not in self._refs:
            self._refs[key] = r

    def _add_doc(self, d):
        """ Add a docstring. """
        key = DefKey(Repo="", Unit=d.Unit, UnitType=d.UnitType, Path=d.Path)
        if key in self._docs:
            raise Exception("Attempt to add duplicate doc for {}", key)
        self._docs[key] = d

    def _to_offset(self, line, column):
        """
        Converts from (line, col) position to byte offset.
        Line is 1-indexed, column is 0-indexed.
        """
        line -= 1
        if line >= len(self._cumulative_off):
            raise FileGrapherException('requested line out of bounds {} > {}'.format(
                line + 1,
                len(self._cumulative_off) - 1)
            )
        return self._cumulative_off[line] + column
