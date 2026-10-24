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
"""EnvironmentCapture with a fake ``git`` first on PATH.

Python 3 conversion points: ``options.iteritems()`` -> ``items()`` and
``shell_<key>`` output captured with ``universal_newlines=True`` so it is
``str`` (otherwise ``str(b'...')`` yields the literal text ``"b'...'"``).
"""
import os
import shutil
import tempfile
import unittest

from tests import csmake_alias, fakes

EnvironmentCapture = csmake_alias.import_module(
    'CsmakeModules.EnvironmentCapture').EnvironmentCapture

FAKE_GIT = """#!/bin/sh
if [ "$1" = "rev-parse" ]; then
    echo abc1234
    exit 0
fi
exit 1
"""


class TestEnvironmentCapture(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='swak-envcap-')
        self.addCleanup(shutil.rmtree, self.tmp, True)
        bindir = os.path.join(self.tmp, 'bin')
        os.mkdir(bindir)
        fakes.write_executable(bindir, 'git', FAKE_GIT)
        patcher = fakes.path_first(bindir)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.env = fakes.FakeEnv(self.tmp, metadata=fakes.FakeMetadata())
        self.log = fakes.FakeLog()
        self.capture = EnvironmentCapture(self.env, self.log)

    def test_shell_output_is_text_and_substituted_into_format(self):
        result = self.capture.default({
            'env-name': 'BUILD_ID',
            'format': 'v{sha}-{kind}',
            'shell_sha': 'git rev-parse --short HEAD',
            'value_kind': 'dev'})
        self.assertEqual('vabc1234-dev', result)
        self.assertIsInstance(result, str)
        self.assertEqual('vabc1234-dev', self.env.env['BUILD_ID'])
        self.assertEqual('passed', self.log.result)

    def test_failing_shell_command_is_replaced_by_error_marker(self):
        result = self.capture.default({
            'env-name': 'BUILD_ID',
            'format': '{sha}',
            'shell_sha': 'git log'})
        self.assertEqual('<<error>>', result)
        self.assertTrue(
            any('non-zero returncode' in m
                for m in self.log.messages('warning')))


if __name__ == '__main__':
    unittest.main()
