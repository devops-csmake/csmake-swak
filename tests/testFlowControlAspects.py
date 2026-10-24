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
"""Flow-control aspects: SkipSection, SkipIfFileExists, SkipIfFileNotExist,
SkipUnlessEqual, SectionOnlyOnce, EnvironmentConditional and AssertFails.

These aspects only talk to the aspect flow-control object, the csmake
environment and the result log, so those are the fakes; the file-existence
aspects have ``glob.glob`` mocked.  Each is checked for the votes/overrides
it casts, not just that it ran.
"""
import types
import unittest
from unittest import mock

from tests import csmake_alias, fakes

AssertFails = csmake_alias.import_module('CsmakeModules.AssertFails').AssertFails
EnvironmentConditional = csmake_alias.import_module(
    'CsmakeModules.EnvironmentConditional').EnvironmentConditional
SectionOnlyOnce = csmake_alias.import_module(
    'CsmakeModules.SectionOnlyOnce').SectionOnlyOnce
SkipIfFileExists = csmake_alias.import_module(
    'CsmakeModules.SkipIfFileExists').SkipIfFileExists
SkipIfFileNotExist = csmake_alias.import_module(
    'CsmakeModules.SkipIfFileNotExist').SkipIfFileNotExist
SkipSection = csmake_alias.import_module('CsmakeModules.SkipSection').SkipSection
SkipUnlessEqual = csmake_alias.import_module(
    'CsmakeModules.SkipUnlessEqual').SkipUnlessEqual

DO_NOT_START = 'doNotStart'


class _AspectCase(unittest.TestCase):
    aspectClass = None

    def setUp(self):
        self.env = fakes.FakeEnv()
        self.log = fakes.FakeLog()
        self.flow = fakes.FakeFlowControl()
        self.aspect = self.aspectClass(self.env, self.log)
        self.aspect.initFlowControl(self.flow)

    def start(self, options, step=None):
        return self.aspect.start('build', options, step, {})


class TestSkipSection(_AspectCase):
    aspectClass = SkipSection

    def test_start_overrides_do_not_start(self):
        self.assertTrue(self.start({}))
        self.assertEqual([(DO_NOT_START, True)], self.flow.overrides)
        self.assertEqual('passed', self.log.result)


class TestSkipUnlessEqual(_AspectCase):
    aspectClass = SkipUnlessEqual

    def test_start_equal_values_let_the_section_run(self):
        self.start({'given': 'x86', 'comparison': 'x86'})
        self.assertEqual([], self.flow.overrides)
        self.assertEqual('passed', self.log.result)

    def test_start_different_values_skip_the_section(self):
        self.start({'given': 'arm', 'comparison': 'x86'})
        self.assertEqual([(DO_NOT_START, True)], self.flow.overrides)
        self.assertEqual('passed', self.log.result)
        self.assertTrue(any('arm is not x86' in m
                            for m in self.log.messages('info')))

    def test_start_comparison_is_exact_not_case_insensitive(self):
        self.start({'given': 'X86', 'comparison': 'x86'})
        self.assertEqual([(DO_NOT_START, True)], self.flow.overrides)

    def test_start_two_empty_values_are_equal(self):
        self.start({'given': '', 'comparison': ''})
        self.assertEqual([], self.flow.overrides)


class TestSkipIfFileExists(_AspectCase):
    aspectClass = SkipIfFileExists

    def test_start_skips_when_a_matching_file_exists(self):
        with mock.patch('glob.glob', return_value=['/etc/hosts']) as glob:
            self.start({'file': '/etc/ho*'})
        glob.assert_called_once_with('/etc/ho*')
        self.assertEqual([(DO_NOT_START, True)], self.flow.overrides)
        self.assertEqual('passed', self.log.result)

    def test_start_runs_when_nothing_matches(self):
        with mock.patch('glob.glob', return_value=[]):
            self.start({'file': '/nope/*'})
        self.assertEqual([], self.flow.overrides)
        self.assertEqual('passed', self.log.result)


class TestSkipIfFileNotExist(_AspectCase):
    aspectClass = SkipIfFileNotExist

    def test_start_skips_when_nothing_matches(self):
        with mock.patch('glob.glob', return_value=[]) as glob:
            self.start({'file': '/nope/*'})
        glob.assert_called_once_with('/nope/*')
        self.assertEqual([(DO_NOT_START, True)], self.flow.overrides)
        self.assertEqual('passed', self.log.result)

    def test_start_runs_when_a_file_matches(self):
        with mock.patch('glob.glob', return_value=['/etc/hosts', '/etc/hostname']):
            self.start({'file': '/etc/host*'})
        self.assertEqual([], self.flow.overrides)
        self.assertEqual('passed', self.log.result)


class TestSectionOnlyOnce(_AspectCase):
    aspectClass = SectionOnlyOnce

    def step(self, calledId='step-1'):
        return types.SimpleNamespace(calledId=calledId)

    def test_start_first_time_lets_the_section_run_and_marks_it(self):
        self.start({}, self.step('step-1'))
        self.assertEqual([], self.flow.overrides)
        self.assertIs(True, self.env.env['__step-1:SectionOnlyOnce__'])
        self.assertEqual('passed', self.log.result)

    def test_start_second_time_vetoes_the_section(self):
        self.start({}, self.step('step-1'))
        self.start({}, self.step('step-1'))
        self.assertEqual([(DO_NOT_START, True)], self.flow.overrides)

    def test_start_is_tracked_per_step(self):
        self.start({}, self.step('step-1'))
        self.start({}, self.step('step-2'))
        self.assertEqual([], self.flow.overrides)
        self.assertIn('__step-2:SectionOnlyOnce__', self.env.env)

    def test_start_runs_again_once_the_environment_is_flushed(self):
        self.start({}, self.step('step-1'))
        self.env.env.clear()          # what a new phase does
        self.start({}, self.step('step-1'))
        self.assertEqual([], self.flow.overrides)


class TestEnvironmentConditional(_AspectCase):
    aspectClass = EnvironmentConditional
    OPTIONS = {'ifEnvNotSet': 'MYENV', 'thenUseSectionOptions': '{xyzzy}/{abcaba}'}
    SECTION = {'xyzzy': 'my stuff', 'abcaba': 'other stuff'}

    def end(self, options=None, section=None):
        return self.aspect.end(
            'build', options or self.OPTIONS, None, section or self.SECTION)

    def test_start_variable_not_set_votes_to_run_the_section(self):
        self.assertTrue(self.start(self.OPTIONS))
        self.assertEqual([(DO_NOT_START, False)], self.flow.votes)
        self.assertEqual('passed', self.log.result)

    def test_start_variable_already_set_votes_to_skip_the_section(self):
        self.env.env['MYENV'] = 'already'
        self.assertTrue(self.start(self.OPTIONS))
        self.assertEqual([(DO_NOT_START, True)], self.flow.votes)
        self.assertTrue(any('is defined in the environment' in m
                            for m in self.log.messages('info')))

    def test_end_sets_the_variable_from_the_section_options(self):
        self.assertTrue(self.end())
        self.assertEqual('my stuff/other stuff', self.env.env['MYENV'])
        self.assertEqual('passed', self.log.result)

    def test_end_keeps_an_existing_value(self):
        self.env.env['MYENV'] = 'already'
        self.assertTrue(self.end())
        self.assertEqual('already', self.env.env['MYENV'])

    def test_end_double_right_brace_is_a_literal_brace(self):
        options = {'ifEnvNotSet': 'MYENV', 'thenUseSectionOptions': '{xyzzy}} done'}
        self.end(options, {'xyzzy': 'x'})
        self.assertEqual('{xyzzy} done', self.env.env['MYENV'])

    def test_end_option_missing_from_the_section_is_an_error(self):
        with self.assertRaises(KeyError):
            self.end(section={'xyzzy': 'only one'})
        self.assertNotIn('MYENV', self.env.env)


class _Result(object):
    """A step result node: records passed()/failed(), has child results."""

    def __init__(self, *children):
        self.state = None
        self.childResults = list(children)

    def passed(self):
        self.state = 'passed'

    def failed(self):
        self.state = 'failed'


class TestAssertFails(_AspectCase):
    aspectClass = AssertFails

    def test_failed_turns_the_step_and_its_children_to_passed(self):
        grandchild = _Result()
        child = _Result(grandchild)
        sibling = _Result()
        step = types.SimpleNamespace(log=_Result(child, sibling))
        step.log.state = 'failed'

        self.aspect.failed('build', {}, step, {})

        self.assertEqual(
            ['passed'] * 4,
            [r.state for r in (step.log, child, grandchild, sibling)])

    def test_passed_turns_the_step_to_failed(self):
        step = types.SimpleNamespace(log=_Result())
        step.log.state = 'passed'
        self.aspect.passed('build', {}, step, {})
        self.assertEqual('failed', step.log.state)


if __name__ == '__main__':
    unittest.main()
