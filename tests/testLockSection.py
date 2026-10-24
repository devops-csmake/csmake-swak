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
"""LockSection unit tests: ``fcntl.flock`` is the mocked boundary.

The kernel lock itself is replaced by a recorder so each test asserts which
lock was requested and when it was released.  Lock directories and files are
real temp paths because the Python 3 conversion point is file mode: the
``0777`` / ``0666`` literals became ``0o777`` / ``0o666``.  The chmod calls
are wrapped in a blanket ``except`` that only logs, so the resulting modes
are asserted explicitly, under a restrictive umask that would otherwise leave
the lock directory unusable by other users.
"""
import fcntl
import os
import shutil
import stat
import tempfile
import unittest
from unittest import mock

from tests import csmake_alias, fakes

lockModule = csmake_alias.import_module('CsmakeModules.LockSection')
LockSection = lockModule.LockSection


def mode_of(path):
    return stat.S_IMODE(os.stat(path).st_mode)


class _Case(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='swak-lock-')
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.lockdir = os.path.join(self.tmp, 'locks')
        self.lockfile = os.path.join(self.lockdir, 'build')
        self.options = {'tag': 'build', 'path': self.lockdir}

        patcher = mock.patch.object(lockModule.fcntl, 'flock')
        self.flock = patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.closeLockFiles)

        oldUmask = os.umask(0o077)
        self.addCleanup(os.umask, oldUmask)

        self.env = fakes.FakeEnv(self.tmp)
        self.log = fakes.FakeLog()
        self.lock = self.newLock()

    def newLock(self):
        return LockSection(self.env, self.log)

    def closeLockFiles(self):
        # tests that stop with a lock still held would leak the open file
        for call in self.flock.call_args_list:
            call[0][0].close()

    def flockOps(self):
        """The operations (LOCK_EX, LOCK_UN, ...) passed to flock, in order."""
        return [c[0][1] for c in self.flock.call_args_list]


class TestLockSectionLocking(_Case):

    def test_lock_takes_an_exclusive_flock_on_the_tag_file(self):
        self.assertEqual('build', self.lock._lock('build', self.options, None, None))
        self.assertEqual([fcntl.LOCK_EX], self.flockOps())
        locked = self.flock.call_args[0][0]
        self.assertEqual(self.lockfile, locked.name)
        self.assertEqual('passed', self.log.result)

    def test_lock_registers_an_exit_callback_that_releases_the_lock(self):
        self.lock._lock('build', self.options, None, None)
        self.assertEqual(1, len(self.env.engine.callbacks))
        for callback in list(self.env.engine.callbacks.values()):
            callback()
        self.assertEqual([fcntl.LOCK_EX, fcntl.LOCK_UN], self.flockOps())
        self.assertEqual({}, self.env.engine.callbacks)

    def test_lock_read_option_takes_a_shared_lock(self):
        self.options['read'] = 'True'
        self.lock._lock('build', self.options, None, None)
        self.assertEqual([fcntl.LOCK_SH], self.flockOps())

    def test_lock_read_option_other_than_true_stays_exclusive(self):
        self.options['read'] = 'False'
        self.lock._lock('build', self.options, None, None)
        self.assertEqual([fcntl.LOCK_EX], self.flockOps())

    def test_lock_defaults_to_the_system_lock_directory(self):
        with mock.patch.object(LockSection, '_lockSection') as lockSection:
            self.lock._lock('build', {'tag': 'build'}, None, None)
        lockSection.assert_called_once_with('/var/lock/csmake', 'build')

    def test_lock_makes_the_directory_and_file_world_usable_despite_umask(self):
        self.lock._lock('build', self.options, None, None)
        self.assertEqual(0o777, mode_of(self.lockdir))
        self.assertEqual(0o666, mode_of(self.lockfile))
        self.assertEqual([], self.log.messages('exception'))

    def test_lock_survives_chmod_failures_and_logs_them(self):
        with mock.patch('os.chmod', side_effect=PermissionError('not owner')):
            self.lock._lock('build', self.options, None, None)
        self.assertEqual([fcntl.LOCK_EX], self.flockOps())
        self.assertEqual(
            ['Attempting lock chmod on lock dir',
             'Attempting lock chmod on lock'],
            self.log.messages('exception'))

    def test_lock_fails_when_the_lock_directory_cannot_be_created(self):
        with mock.patch('os.makedirs', side_effect=PermissionError('read-only')):
            with self.assertRaises(PermissionError):
                self.lock._lock('build', self.options, None, None)
        self.assertEqual([], self.flockOps())


class TestLockSectionReentrancy(_Case):

    def test_second_lock_on_the_same_tag_reuses_the_held_flock(self):
        second = self.newLock()
        self.lock._lock('build', self.options, None, None)
        second._lock('build', self.options, None, None)
        self.assertEqual([fcntl.LOCK_EX], self.flockOps())

    def test_flock_is_released_only_by_the_last_unlock(self):
        second = self.newLock()
        self.lock._lock('build', self.options, None, None)
        second._lock('build', self.options, None, None)

        second._unlock('build', self.options, None, None)
        self.assertEqual([fcntl.LOCK_EX], self.flockOps())

        self.lock._unlock('build', self.options, None, None)
        self.assertEqual([fcntl.LOCK_EX, fcntl.LOCK_UN], self.flockOps())

    def test_read_lock_cannot_be_promoted_to_exclusive(self):
        reader = dict(self.options, read='True')
        self.lock._lock('build', reader, None, None)
        with self.assertRaises(ValueError):
            self.newLock()._lock('build', self.options, None, None)
        self.assertTrue(any('promoted' in m for m in self.log.messages('error')))
        self.assertEqual([fcntl.LOCK_SH], self.flockOps())

    def test_failed_promotion_does_not_leak_a_hold_on_the_lock(self):
        reader = dict(self.options, read='True')
        self.lock._lock('build', reader, None, None)
        with self.assertRaises(ValueError):
            self.newLock()._lock('build', self.options, None, None)
        self.lock._unlock('build', reader, None, None)
        self.assertEqual([fcntl.LOCK_SH, fcntl.LOCK_UN], self.flockOps())

    def test_shared_locks_can_be_stacked(self):
        reader = dict(self.options, read='True')
        self.lock._lock('build', reader, None, None)
        self.newLock()._lock('build', reader, None, None)
        self.assertEqual([fcntl.LOCK_SH], self.flockOps())


class TestLockSectionUnlocking(_Case):

    def test_unlock_releases_the_flock_and_closes_the_file(self):
        self.lock._lock('build', self.options, None, None)
        locked = self.flock.call_args[0][0]
        self.assertEqual('build', self.lock._unlock('build', self.options, None, None))
        self.assertEqual([fcntl.LOCK_EX, fcntl.LOCK_UN], self.flockOps())
        self.assertTrue(locked.closed)
        self.assertEqual({}, self.env.engine.callbacks)
        self.assertEqual('passed', self.log.result)

    def test_unlock_releases_the_process_lock_even_if_flock_fails(self):
        self.lock._lock('build', self.options, None, None)
        locked = self.flock.call_args[0][0]
        self.flock.side_effect = OSError('flock failed')
        with self.assertRaises(OSError):
            self.lock._unlock('build', self.options, None, None)
        self.assertTrue(locked.closed)
        # the table entry is free again, so the tag can be locked afresh
        self.flock.side_effect = None
        self.newLock()._lock('build', self.options, None, None)
        self.assertEqual(
            [fcntl.LOCK_EX, fcntl.LOCK_UN, fcntl.LOCK_EX], self.flockOps())

    def test_cleanup_before_the_lock_was_taken_is_harmless(self):
        self.lock.flockPath = None
        self.lock._cleanUpLock(self.lockdir, 'build', None)
        self.assertEqual([], self.flockOps())
        self.assertTrue(any('before it was locked' in m
                            for m in self.log.messages('info')))


class TestLockSectionJoinPoints(_Case):

    def test_start_locks_and_end_unlocks_in_every_phase_by_default(self):
        lookup = self.lock._joinPointLookup
        self.assertEqual(self.lock._lock, lookup('start', 'build', {}))
        self.assertEqual(self.lock._unlock, lookup('end', 'test', {}))

    def test_other_joinpoints_are_ignored(self):
        self.assertIsNone(self.lock._joinPointLookup('passed', 'build', {}))

    def test_phases_option_limits_the_phases(self):
        options = {'phases': 'build,\n test'}
        lookup = self.lock._joinPointLookup
        self.assertEqual(self.lock._lock, lookup('start', 'test', options))
        self.assertIsNone(lookup('start', 'package', options))

    def test_star_phases_means_every_phase(self):
        self.assertEqual(
            self.lock._lock,
            self.lock._joinPointLookup('start', 'any', {'phases': '*'}))


if __name__ == '__main__':
    unittest.main()
