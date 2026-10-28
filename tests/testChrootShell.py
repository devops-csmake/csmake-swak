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
"""ChrootShell with the subprocess boundary mocked.

ChrootShell wraps the command in ``sudo -E chroot ... -c "<command>"`` and
hands it to the core Shell module, which calls subprocess.  The fake
subprocess records the exact command line so the quoting/escaping is asserted
without a chroot, sudo or root.
"""
import subprocess
import unittest

from tests import csmake_alias, fakes

ChrootShell = csmake_alias.import_module('CsmakeModules.ChrootShell').ChrootShell


class _Case(unittest.TestCase):

    def setUp(self):
        self.sub = fakes.FakeSubprocess().install(self)
        self.sub.on(lambda args, kwargs: True, returncode=0)
        # Shell's probe for how this bash exports functions; it is not under
        # test here, so let it fail (Shell logs a warning and carries on).
        self.sub.on('export -f foo', returncode=1)
        self.env = fakes.FakeEnv(phase='build')
        self.log = fakes.FakeLog()
        self.shell = ChrootShell(self.env, self.log)

    def executed(self):
        return [c for c in self.sub.calls if c.kind == 'call']


class TestChrootShellExecute(_Case):

    def test_executeShell_wraps_the_command_in_sudo_chroot(self):
        self.shell.chroot = '/srv/root'
        self.shell.asUser = None
        result = self.shell._executeShell('ls -l', {'A': '1'})
        self.assertEqual(0, result)
        call = self.executed()[0]
        self.assertEqual('sudo -E chroot /srv/root /bin/bash -c "ls -l"', call.args)
        self.assertIs(True, call.kwargs['shell'])
        self.assertEqual({'A': '1'}, call.kwargs['env'])

    def test_executeShell_escapes_backslash_backtick_quote_and_dollar(self):
        self.shell.chroot = '/srv/root'
        self.shell.asUser = None
        self.shell._executeShell('echo "$HOME" `date` \\n', {})
        self.assertEqual(
            'sudo -E chroot /srv/root /bin/bash -c '
            '"echo \\"\\$HOME\\" \\`date\\` \\\\n"',
            self.executed()[0].args)

    def test_executeShell_as_user_runs_the_shell_under_sudo_u(self):
        self.shell.chroot = '/srv/root'
        self.shell.asUser = 'builder'
        self.shell._executeShell('id', {})
        self.assertEqual(
            'sudo -E chroot /srv/root sudo -H -E -u builder /bin/bash -c "id"',
            self.executed()[0].args)

    def test_executeShell_without_a_chroot_runs_the_command_as_is(self):
        self.shell.chroot = None
        self.shell.asUser = None
        self.shell._executeShell('make all', {})
        self.assertEqual('make all', self.executed()[0].args)
        self.assertTrue(any('does not specify a chroot' in m
                            for m in self.log.messages('warning')))

    def test_executeShell_returns_the_exit_status(self):
        self.shell.chroot = '/srv/root'
        self.shell.asUser = None
        self.sub.on('chroot', returncode=3)
        self.assertEqual(3, self.shell._executeShell('false', {}))


class TestChrootShellDefault(_Case):

    def test_default_runs_the_command_in_the_chroot_and_passes(self):
        self.shell.default({'command': 'ls', 'chroot': '/srv/root'})
        self.assertEqual(
            ['sudo -E chroot /srv/root /bin/bash -c "ls"'],
            [c.args for c in self.executed()])
        self.assertEqual('passed', self.log.result)

    def test_default_as_user_option_is_applied(self):
        self.shell.default(
            {'command': 'id', 'chroot': '/srv/root', 'as-user': 'builder'})
        self.assertIn('sudo -H -E -u builder', self.executed()[0].args)

    def test_default_exec_option_selects_the_shell_inside_the_chroot(self):
        self.shell.default(
            {'command': 'ls', 'chroot': '/srv/root', 'exec': '/bin/sh'})
        self.assertEqual(
            'sudo -E chroot /srv/root /bin/sh -c "ls"', self.executed()[0].args)

    def test_default_without_chroot_behaves_like_shell(self):
        self.shell.default({'command': 'make'})
        self.assertEqual(['make'], [c.args for c in self.executed()])
        self.assertEqual('passed', self.log.result)

    def test_default_failing_command_fails_the_step(self):
        self.sub.on('chroot', returncode=1)
        self.shell.default({'command': 'false', 'chroot': '/srv/root'})
        self.assertEqual('failed', self.log.result)

    def test_default_command_for_another_phase_is_skipped(self):
        self.shell.default({'command(clean)': 'rm -rf x', 'chroot': '/srv/root'})
        self.assertEqual('skipped', self.log.result)
        self.assertEqual([], self.executed())

    def test_default_phase_specific_command_is_used(self):
        self.env.engine.phase = 'clean'
        self.shell.default(
            {'command(clean)': 'rm -rf x', 'chroot': '/srv/root'})
        self.assertEqual(
            'sudo -E chroot /srv/root /bin/bash -c "rm -rf x"',
            self.executed()[0].args)


if __name__ == '__main__':
    unittest.main()
