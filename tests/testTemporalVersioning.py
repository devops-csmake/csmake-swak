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
"""TemporalVersioning's sticky version really round-trips through pickle.

Python 3 pickles are bytes, so the file must be opened 'wb'/'rb'.  Opening in
text mode is swallowed by the module's blanket ``except`` (it only logs), so
the failure mode is silent: nothing is persisted, or a stored value is ignored
and recomputed.  These tests assert on the file and on the value reused by a
second "process" instead.
"""
import os
import pickle
import shutil
import tempfile
import unittest

from tests import csmake_alias, fakes

TemporalVersioning = csmake_alias.import_module(
    'CsmakeModules.TemporalVersioning').TemporalVersioning


class TestTemporalVersioning(unittest.TestCase):

    def setUp(self):
        self.results = tempfile.mkdtemp(prefix='swak-temporal-')
        self.addCleanup(shutil.rmtree, self.results, True)
        self.pickleFile = os.path.join(self.results, '.__temporalversions')

    def run_section(self, **values):
        """Run the section as a fresh csmake process would: new env, new log."""
        options = {'designation': 'snap', 'format': '{a}-{b}'}
        options.update(('value_' + k, v) for k, v in values.items())
        metadata = fakes.FakeMetadata()
        log = fakes.FakeLog()
        module = TemporalVersioning(
            fakes.FakeEnv(self.results, metadata=metadata), log)
        result = module.default(options)
        return result, metadata, log

    def test_first_run_persists_a_binary_pickle(self):
        _, metadata, log = self.run_section(a='1', b='2')
        self.assertEqual({'snap': '1-2'}, metadata.version)
        self.assertEqual([], log.messages('exception'))
        with open(self.pickleFile, 'rb') as f:
            self.assertEqual({'snap': '1-2'}, pickle.load(f))

    def test_later_run_reuses_the_stored_value(self):
        self.run_section(a='1', b='2')
        # New inputs, but the designation is already pinned by the pickle.
        result, metadata, log = self.run_section(a='9', b='9')
        self.assertEqual([], log.messages('exception'))
        self.assertEqual('1-2', result)
        self.assertEqual({'snap': '1-2'}, metadata.version)


if __name__ == '__main__':
    unittest.main()
