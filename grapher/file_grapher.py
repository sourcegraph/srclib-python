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

REPO_STDLIB = "github.com/python/cpython"

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
        self._log = log
        self._source = None
        self._defs = {}
        self._refs = {}
        self._load()

        self._stdlibpaths = []
        for p in syspath:
            if not p.endswith('site-packages'):
                self._stdlibpaths.append(p)

    def graph(self):
        # Add module/package defs.
        module = os.path.splitext(self._file)[0]
        if os.path.basename(self._file) == '__init__.py':
            module = os.path.normpath(os.path.dirname(self._file))

        self._add_def(Def(
            Repo="",
            Unit=self._unit,
            UnitType=self._unit_type,
            Path=module,
            Kind='module',
            Name=module.split('/')[-1],
            File=normalize(self._file),
            DefStart=0,
            DefEnd=0,
            Exported=True,
            Data=None,
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

        # Defs.
        for jedi_def in jedi_defs:
            self._log.debug(
                'Processing def: %s | %s | %s',
                jedi_def.desc_with_module,
                jedi_def.name,
                jedi_def.type,
            )
            try:
                def_, doc = self._jedi_def_to_def(jedi_def)
                self._add_def(def_)
                if doc is not None:
                    self._add_doc(doc)
            except Exception as e:
                self._log.error(
                    u'Failed to process def `%s`: %s',
                    jedi_def.name,
                    e,
                )
                continue

        # Refs.
        for jedi_ref in jedi_refs:
            self._log.debug(
                'Processing ref: %s | %s | %s',
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
                    u'Failed to process def to def-key `%s`: %s',
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

        return self._defs, self._refs

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
                'Ref def search (precondition failed) | %s | %s | %s',
                ref_def.is_definition(),
                ref_def.type,
                ref_def.name
            )

        if ref_def.type == "import":
            # We didn't find anything.
            self._log.debug('Ref def not found')
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

    def _jedi_def_to_def(self, d):
        # TODO(MaikuMori): Add back this if needed:
        # If def is a name, then the location of the definition is the last name part
        start = self._to_offset(d.line, d.column)
        end = start + len(d.name)
        path, dep = self._full_name_and_dep(d)
        if dep is not None:
            repo, unit, unit_type = dep.Repo, dep.Name, dep.Type
        else:
            repo, unit, unit_type = "", self._unit, self._unit_type
        def_ = Def(
            Repo=repo,
            Unit=unit,
            UnitType=unit_type,
            Path=path,
            Kind=d.type,
            Name=d.name,
            File=normalize(self._file),
            DefStart=start,
            DefEnd=end,
            Exported=self._is_exported(d.name),
            Data=None,
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
        for p in self._syspath:
            if p == '':
                continue
            if module_path.startswith(p):
                return normalize(os.path.relpath(module_path, p)), False # external

        if module_path.startswith(self._abs_base_dir):
            return normalize(os.path.relpath(module_path, self._abs_base_dir)), True # internal

        return None, False

    def _module_to_dep(self, m):
        # Check explicit pip dependencies
        for pkg, dep in self._modulePathPrefixToDep.items():
            if m.startswith(pkg):
                return dep, None
        # Fall back to heuristics
        if m.startswith('setuptools'):
            return UnitKey(Repo=REPO_STDLIB, Type=UNIT_PIP, Name='setuptools', CommitID='', Version=''), None
        for stdlibpath in self._stdlibpaths:
            if os.path.lexists(os.path.join(stdlibpath, m)):
                # Standard lib module
                return UnitKey(Repo=REPO_STDLIB, Type=UNIT_PIP, Name=m, CommitID='', Version=''), None
        return None, ('could not find dep module for module %s, candidates were %s' % (m, repr(self._modulePathPrefixToDep.keys())))

    def _full_name_and_dep(self, d):
        if d.in_builtin_module():
            return d.full_name, UnitKey(Repo=REPO_STDLIB, Type=UNIT_PIP, Name="__builtin__", CommitID="", Version="")

        if d.module_path is None:
            raise Exception('no module path for definition %s' % repr(d))

        # This detects `self` and `cls` parameters makes them to point to the class:
        # To trigger this parameters must be for a method (a class function).
        if d.type == 'param' and (d.name == 'self' or d.name == 'cls') and d.parent().parent().type == 'class':
            # import pdb; pdb.set_trace();
            d = d.parent().parent()

        module_path, is_internal = self._rel_module_path(d.module_path)
        if module_path is None:
            raise Exception('could not find name for module path %s' % d.module_path)

        dep = None
        if not is_internal:
            dep, err = self._module_to_dep(module_path)
            if err is not None:
                raise Exception(err)

        return '{}/{}.{}'.format(module_path, d.full_name, d.name), dep

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
        self._log.debug('Adding def: %s | %s | %s', d.Name, d.Path, d.Kind)
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
        self._log.debug('Adding ref: %s', r.DefPath)
        key = (r.DefPath, r.File, r.Start, r.End)
        if key not in self._refs:
            self._refs[key] = r

    def _add_doc(self, d):
        """ Add a docstring. """
        # TODO

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