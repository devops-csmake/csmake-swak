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
"""AssertStringContains: pass when the needle is in the haystack, else fail."""
import unittest

from tests import csmake_alias, fakes

AssertStringContains = csmake_alias.import_module(
    'CsmakeModules.AssertStringContains').AssertStringContains


class TestAssertStringContains(unittest.TestCase):

    def setUp(self):
        self.log = fakes.FakeLog()
        self.module = AssertStringContains(fakes.FakeEnv(), self.log)

    def test_build_passes_when_the_needle_is_present(self):
        self.module.build({'haystack': 'hello brave world', 'needle': 'brave'})
        self.assertEqual('passed', self.log.result)
        self.assertEqual([], self.log.messages('error'))

    def test_build_fails_when_the_needle_is_absent(self):
        self.module.build({'haystack': 'hello world', 'needle': 'brave'})
        self.assertEqual('failed', self.log.result)
        self.assertEqual(
            ["Expected 'brave' to appear in 'hello world'"],
            self.log.messages('error'))

    def test_build_match_is_case_sensitive(self):
        self.module.build({'haystack': 'Hello', 'needle': 'hello'})
        self.assertEqual('failed', self.log.result)

    def test_build_empty_needle_is_always_found(self):
        self.module.build({'haystack': 'anything', 'needle': ''})
        self.assertEqual('passed', self.log.result)

    def test_build_empty_haystack_only_contains_the_empty_needle(self):
        self.module.build({'haystack': '', 'needle': 'x'})
        self.assertEqual('failed', self.log.result)

    def test_build_handles_non_ascii_text(self):
        self.module.build({'haystack': u'café au lait', 'needle': u'é'})
        self.assertEqual('passed', self.log.result)


if __name__ == '__main__':
    unittest.main()
