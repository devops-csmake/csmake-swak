# <copyright>
# (c) Copyright 2026 Autumn Patterson
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# </copyright>
"""Test-only shim: make plugin imports of ``Csmake.X`` resolve to CsmakeCore.

Plugin modules do ``from Csmake.CsmakeModule import CsmakeModule`` but the
installed csmake only ships ``CsmakeCore``.  That mismatch is a known,
separate ecosystem issue; production imports are deliberately left alone and
the alias exists only inside the test process.
"""
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _AliasFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Resolve ``Csmake.<sub>`` to the very same module as ``CsmakeCore.<sub>``."""

    def __init__(self):
        self._real_specs = {}

    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('Csmake.'):
            return importlib.machinery.ModuleSpec(fullname, self)
        return None

    def create_module(self, spec):
        module = importlib.import_module('CsmakeCore.' + spec.name[len('Csmake.'):])
        self._real_specs[module.__name__] = module.__spec__
        return module

    def exec_module(self, module):
        # The import machinery stamps the alias spec onto the shared module
        # object; put the real one back so CsmakeCore itself is unaffected.
        module.__spec__ = self._real_specs.pop(module.__name__)


def install():
    """Alias Csmake -> CsmakeCore, or raise SkipTest if csmake core is absent."""
    if 'Csmake' in sys.modules or importlib.util.find_spec('Csmake') is not None:
        return
    if importlib.util.find_spec('CsmakeCore') is None:
        sibling = os.path.join(os.path.dirname(REPO), 'csmake')
        if not os.path.isdir(os.path.join(sibling, 'CsmakeCore')):
            raise unittest.SkipTest("csmake core not found")
        sys.path.append(sibling)
    sys.modules['Csmake'] = importlib.import_module('CsmakeCore')
    sys.meta_path.insert(0, _AliasFinder())


def import_module(name):
    """Import a repo module; skip (not fail) if a *csmake* dependency is absent.

    Only a missing csmake/plugin-ecosystem module (e.g. the core's
    CsmakeModules.versioning) turns into a skip.  Any other ImportError, such
    as a leftover ``import urllib2``, is a real failure and propagates.
    """
    install()
    try:
        return importlib.import_module(name)
    except ImportError as e:
        missing = getattr(e, 'name', None) or ''
        if missing != name and missing.split('.')[0] in (
                'Csmake', 'CsmakeCore', 'CsmakeModules'):
            raise unittest.SkipTest(
                "%s needs csmake pieces that are not available here (%s)"
                % (name, e))
        raise
