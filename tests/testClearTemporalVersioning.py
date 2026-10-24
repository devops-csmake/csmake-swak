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
"""ClearTemporalVersioning: removes the sticky-version file and environment.

The pickle file is a real temp file (it is the thing being deleted); os.remove
is mocked for the failure case.
"""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from tests import csmake_alias, fakes

ClearTemporalVersioning = csmake_alias.import_module(
    'CsmakeModules.ClearTemporalVersioning').ClearTemporalVersioning


class TestClearTemporalVersioning(unittest.TestCase):

    def setUp(self):
        self.results = tempfile.mkdtemp(prefix='swak-clear-')
        self.addCleanup(shutil.rmtree, self.results, True)
        self.pickleFile = os.path.join(self.results, '.__temporalversions')
        with open(self.pickleFile, 'wb') as f:
            f.write(b'pickled')
        self.env = fakes.FakeEnv(self.results, phase='clean')
        self.env.addTransPhase('__TemporalVersioning', {'snap': '1-2'})
        self.log = fakes.FakeLog()
        self.module = ClearTemporalVersioning(self.env, self.log)

    def test_default_removes_the_file_and_the_environment_entries(self):
        self.module.default({'phases': 'clean'})
        self.assertFalse(os.path.exists(self.pickleFile))
        self.assertNotIn('__TemporalVersioning', self.env.env)
        self.assertNotIn('__TemporalVersioning', self.env.transPhase)
        self.assertEqual('passed', self.log.result)

    def test_default_phases_may_be_comma_or_newline_delimited(self):
        self.module.default({'phases': 'build, test\n clean\n'})
        self.assertFalse(os.path.exists(self.pickleFile))
        self.assertEqual('passed', self.log.result)

    def test_default_skips_when_the_current_phase_is_not_listed(self):
        self.assertIsNone(self.module.default({'phases': 'build,test'}))
        self.assertTrue(os.path.exists(self.pickleFile))
        self.assertIn('__TemporalVersioning', self.env.env)
        self.assertEqual('skipped', self.log.result)

    def test_default_without_a_stored_file_still_clears_the_environment(self):
        os.remove(self.pickleFile)
        self.module.default({'phases': 'clean'})
        self.assertNotIn('__TemporalVersioning', self.env.env)
        self.assertEqual('passed', self.log.result)

    def test_default_without_any_stored_versions_is_still_a_pass(self):
        os.remove(self.pickleFile)
        env = fakes.FakeEnv(self.results, phase='clean')
        module = ClearTemporalVersioning(env, self.log)
        module.default({'phases': 'clean'})
        self.assertEqual('passed', self.log.result)

    def test_default_removal_failure_fails_and_keeps_the_environment(self):
        with mock.patch('os.remove', side_effect=PermissionError('read-only')):
            self.assertIsNone(self.module.default({'phases': 'clean'}))
        self.assertEqual('failed', self.log.result)
        self.assertEqual(['Could not delete stored versions'],
                         self.log.messages('exception'))
        self.assertIn('__TemporalVersioning', self.env.env)


if __name__ == '__main__':
    unittest.main()
