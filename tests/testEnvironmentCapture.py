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
"""EnvironmentCapture with subprocess.Popen mocked.

Python 3 conversion points: ``options.iteritems()`` -> ``items()`` and
``shell_<key>`` output captured with ``universal_newlines=True`` so it is
``str`` (otherwise ``str(b'...')`` yields the literal text ``"b'...'"``).
The fake Popen returns bytes unless text was requested, like the real one.
"""
import subprocess
import unittest

from tests import csmake_alias, fakes

EnvironmentCapture = csmake_alias.import_module(
    'CsmakeModules.EnvironmentCapture').EnvironmentCapture


class _Case(unittest.TestCase):

    def setUp(self):
        self.sub = fakes.FakeSubprocess().install(self)
        self.metadata = fakes.FakeMetadata()
        self.env = fakes.FakeEnv(metadata=self.metadata, phase='build')
        self.log = fakes.FakeLog()
        self.capture = EnvironmentCapture(self.env, self.log)

    def run_capture(self, **options):
        options.setdefault('env-name', 'BUILD_ID')
        return self.capture.default(options)


class TestEnvironmentCaptureShell(_Case):

    def test_default_shell_output_is_text_substituted_into_the_format(self):
        self.sub.on('git rev-parse', stdout=b'abc1234\n')
        result = self.run_capture(**{
            'format': 'v{sha}-{kind}',
            'shell_sha': 'git rev-parse --short HEAD',
            'value_kind': 'dev'})
        self.assertEqual('vabc1234-dev', result)
        self.assertIsInstance(result, str)
        self.assertEqual('vabc1234-dev', self.env.env['BUILD_ID'])
        self.assertEqual('passed', self.log.result)

    def test_default_runs_the_shell_command_through_popen_in_text_mode(self):
        self.sub.on('git rev-parse', stdout=b'abc1234\n')
        self.run_capture(format='{sha}', shell_sha='git rev-parse --short HEAD')
        call = self.sub.calls[0]
        self.assertEqual('Popen', call.kind)
        self.assertEqual('git rev-parse --short HEAD', call.args)
        self.assertIs(True, call.kwargs['shell'])
        self.assertIs(subprocess.PIPE, call.kwargs['stdout'])
        self.assertIs(subprocess.PIPE, call.kwargs['stderr'])
        self.assertTrue(fakes.is_text_mode(call.kwargs))

    def test_default_strips_surrounding_whitespace_and_crlf(self):
        self.sub.on('emit', stdout=b'  1.2.3\r\n')
        self.assertEqual('1.2.3', self.run_capture(format='{v}', shell_v='emit'))

    def test_default_empty_output_gives_an_empty_value(self):
        self.sub.on('emit', stdout=b'')
        self.assertEqual('[]', self.run_capture(format='[{v}]', shell_v='emit'))

    def test_default_decodes_non_ascii_output(self):
        self.sub.on('emit', stdout=u'café\n'.encode('utf-8'))
        self.assertEqual(
            u'café', self.run_capture(format='{v}', shell_v='emit'))

    def test_default_nonzero_exit_is_replaced_by_the_error_marker(self):
        self.sub.on('git log', stdout=b'partial', returncode=128)
        result = self.run_capture(format='{sha}', shell_sha='git log')
        self.assertEqual('<<error>>', result)
        self.assertEqual('<<error>>', self.env.env['BUILD_ID'])
        self.assertTrue(any('non-zero returncode (128)' in m
                            for m in self.log.messages('warning')))

    def test_default_one_failing_command_does_not_spoil_the_others(self):
        self.sub.on('good', stdout=b'ok\n')
        self.sub.on('bad', returncode=1)
        result = self.run_capture(
            format='{a}/{b}', shell_a='good', shell_b='bad')
        self.assertEqual('ok/<<error>>', result)

    def test_default_ignores_options_that_are_not_shell_value_or_step_keys(self):
        self.sub.on('emit', stdout=b'x\n')
        result = self.run_capture(**{
            'format': '{a}', 'shell_a': 'emit', 'description': 'ignored',
            'shell_two_parts': 'never run', 'other': '1'})
        self.assertEqual('x', result)
        self.assertEqual(['emit'], self.sub.commands())


class TestEnvironmentCaptureValuesAndSteps(_Case):

    def test_default_value_keys_are_used_verbatim(self):
        self.assertEqual(
            '1-2', self.run_capture(
                format='{a}-{b}', value_a='1', value_b='2'))

    def test_default_step_result_is_substituted(self):
        self.env.engine.steps['get-version'] = fakes.FakeStepResult(42)
        result = self.run_capture(format='r{n}', step_n='get-version')
        self.assertEqual('r42', result)
        self.assertEqual([('get-version', 'build')], self.env.engine.launched)

    def test_default_step_that_did_not_run_gives_the_error_marker(self):
        result = self.run_capture(format='{n}', step_n='missing')
        self.assertEqual('<<error>>', result)
        self.assertTrue(any('step failed' in m
                            for m in self.log.messages('warning')))

    def test_default_step_that_failed_gives_the_error_marker(self):
        self.env.engine.steps['broken'] = fakes.FakeStepResult(
            'ignored', passed=False)
        self.assertEqual(
            '<<error>>', self.run_capture(format='{n}', step_n='broken'))


class TestEnvironmentCaptureEnvironmentUpdate(_Case):

    def test_dry_run_true_returns_the_value_without_setting_the_environment(self):
        result = self.run_capture(format='{a}', value_a='x', **{'dry-run': 'True'})
        self.assertEqual('x', result)
        self.assertNotIn('BUILD_ID', self.env.env)

    def test_dry_run_false_still_sets_the_environment(self):
        self.run_capture(format='{a}', value_a='x', **{'dry-run': 'False'})
        self.assertEqual('x', self.env.env['BUILD_ID'])

    def test_without_metadata_the_environment_is_left_alone(self):
        env = fakes.FakeEnv(metadata=None)
        capture = EnvironmentCapture(env, self.log)
        result = capture.default(
            {'env-name': 'BUILD_ID', 'format': '{a}', 'value_a': 'x'})
        self.assertEqual('x', result)
        self.assertNotIn('BUILD_ID', env.env)

    def test_curly_escapes_are_honoured(self):
        # Doubling the right brace makes '{b}}' the literal text '{b}'.
        self.assertEqual(
            'a-{b}', self.run_capture(format='{x}-{b}}', value_x='a'))


if __name__ == '__main__':
    unittest.main()
