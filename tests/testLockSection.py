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
"""LockSection takes a real flock in a temp directory.

Python 3 conversion point: the ``0777`` / ``0666`` literals became ``0o777`` /
``0o666``.  The chmod calls are wrapped in a blanket ``except`` that only logs,
so the modes are asserted explicitly, under a restrictive umask that would
otherwise leave the lock directory unusable by other users.
"""
import fcntl
import os
import shutil
import stat
import tempfile
import unittest

from tests import csmake_alias, fakes

LockSection = csmake_alias.import_module('CsmakeModules.LockSection').LockSection


def mode_of(path):
    return stat.S_IMODE(os.stat(path).st_mode)


class TestLockSection(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='swak-lock-')
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.lockdir = os.path.join(self.tmp, 'locks')
        self.log = fakes.FakeLog()
        self.lock = LockSection(fakes.FakeEnv(self.tmp), self.log)
        oldUmask = os.umask(0o077)
        self.addCleanup(os.umask, oldUmask)

    def contended(self, path):
        """True if another open file description cannot flock ``path`` now."""
        with open(path, 'a') as other:
            try:
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (IOError, OSError):
                return True
            fcntl.flock(other, fcntl.LOCK_UN)
            return False

    def test_lock_dir_and_file_are_world_usable_and_flock_is_held(self):
        options = {'tag': 'build', 'path': self.lockdir}
        self.assertEqual('build', self.lock._lock('build', options, None, None))
        lockfile = os.path.join(self.lockdir, 'build')
        try:
            self.assertEqual(0o777, mode_of(self.lockdir))
            self.assertEqual(0o666, mode_of(lockfile))
            self.assertEqual([], self.log.messages('exception'))
            self.assertTrue(self.contended(lockfile))
        finally:
            self.lock._unlock('build', options, None, None)
        self.assertFalse(self.contended(lockfile))


if __name__ == '__main__':
    unittest.main()
