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
"""TemporalVersioning's sticky version round-trips through a real pickle file.

Python 3 pickles are bytes, so the file must be opened 'wb'/'rb'.  Opening in
text mode is swallowed by the module's blanket ``except`` (it only logs), so
the failure mode is silent: nothing is persisted, or a stored value is ignored
and recomputed.  The pickle file is a real temp file because the file mode and
the pickle format are exactly what is under test; the csmake engine and
metadata around it are fakes.
"""
import os
import pickle
import shutil
import tempfile
import unittest

from tests import csmake_alias, fakes

TemporalVersioning = csmake_alias.import_module(
    'CsmakeModules.TemporalVersioning').TemporalVersioning


class _Case(unittest.TestCase):

    def setUp(self):
        self.results = tempfile.mkdtemp(prefix='swak-temporal-')
        self.addCleanup(shutil.rmtree, self.results, True)
        self.pickleFile = os.path.join(self.results, '.__temporalversions')

    def run_section(self, designation='snap', env=None, results=None, **values):
        """Run the section; by default as a fresh csmake process would."""
        options = {'designation': designation, 'format': '{a}-{b}'}
        options.update(('value_' + k, v) for k, v in values.items())
        metadata = fakes.FakeMetadata()
        log = fakes.FakeLog()
        env = env or fakes.FakeEnv(results or self.results, metadata=metadata)
        env._metadata = metadata
        module = TemporalVersioning(env, log)
        result = module.default(options)
        return result, metadata, log

    def stored(self):
        with open(self.pickleFile, 'rb') as f:
            return pickle.load(f)


class TestTemporalVersioning(_Case):

    def test_default_first_run_persists_a_binary_pickle(self):
        _, metadata, log = self.run_section(a='1', b='2')
        self.assertEqual({'snap': '1-2'}, metadata.version)
        self.assertEqual([], log.messages('exception'))
        self.assertEqual({'snap': '1-2'}, self.stored())
        self.assertEqual('passed', log.result)

    def test_default_later_process_reuses_the_stored_value(self):
        self.run_section(a='1', b='2')
        # New inputs, but the designation is already pinned by the pickle.
        result, metadata, log = self.run_section(a='9', b='9')
        self.assertEqual([], log.messages('exception'))
        self.assertEqual('1-2', result)
        self.assertEqual({'snap': '1-2'}, metadata.version)
        self.assertEqual({'snap': '1-2'}, self.stored())

    def test_default_new_designation_is_computed_and_added_to_the_pickle(self):
        self.run_section('snap', a='1', b='2')
        _, metadata, log = self.run_section('rc', a='3', b='4')
        self.assertEqual({'rc': '3-4'}, metadata.version)
        self.assertEqual({'snap': '1-2', 'rc': '3-4'}, self.stored())

    def test_default_same_process_uses_the_cross_phase_dictionary(self):
        env = fakes.FakeEnv(self.results)
        self.run_section(env=env, a='1', b='2')
        os.remove(self.pickleFile)
        # The dictionary kept in the environment wins over the (gone) file.
        result, _, log = self.run_section(env=env, a='9', b='9')
        self.assertEqual('1-2', result)
        self.assertEqual([], log.messages('exception'))
        self.assertFalse(os.path.exists(self.pickleFile))
        self.assertEqual({'snap': '1-2'}, env.env['__TemporalVersioning'])

    def test_default_corrupt_pickle_is_logged_and_the_version_recomputed(self):
        with open(self.pickleFile, 'wb') as f:
            f.write(b'\xffthis is not a pickle')
        _, metadata, log = self.run_section(a='1', b='2')
        self.assertEqual(['Failed to open/read temporal file'],
                         log.messages('exception'))
        self.assertEqual({'snap': '1-2'}, metadata.version)
        self.assertEqual({'snap': '1-2'}, self.stored())

    def test_default_empty_pickle_file_is_logged_and_the_version_recomputed(self):
        open(self.pickleFile, 'wb').close()
        _, metadata, log = self.run_section(a='1', b='2')
        self.assertEqual(['Failed to open/read temporal file'],
                         log.messages('exception'))
        self.assertEqual({'snap': '1-2'}, metadata.version)

    def test_default_unwritable_results_directory_is_logged_but_not_fatal(self):
        missing = os.path.join(self.results, 'no', 'such', 'dir')
        _, metadata, log = self.run_section(results=missing, a='1', b='2')
        self.assertEqual(['Failed to store the updated temporal versioning'],
                         log.messages('exception'))
        self.assertEqual({'snap': '1-2'}, metadata.version)
        self.assertEqual('passed', log.result)


if __name__ == '__main__':
    unittest.main()
