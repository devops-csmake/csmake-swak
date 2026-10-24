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
"""Every Python file in the repo must still compile under Python 3.

Catches Python 2 syntax (``print x``, ``except E, e``, ``0777``, ``ur''``),
TabError and friends creeping back in.  Invalid escape sequences such as an
un-raw ``"\\g<name>"`` are turned into errors too: they are only a warning
today, but they are exactly the kind of regex-substitution string that the
migration made raw and a future Python will reject.
"""
import os
import unittest
import warnings

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = ('.git', '__pycache__')


def python_files():
    for dirpath, dirnames, filenames in os.walk(REPO):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith('.py'):
                yield os.path.join(dirpath, name)


class TestCompiles(unittest.TestCase):

    def test_every_python_file_compiles(self):
        files = list(python_files())
        self.assertTrue(files, "no python files found under %s" % REPO)
        for path in files:
            with self.subTest(file=os.path.relpath(path, REPO)):
                with open(path, 'rb') as f:
                    source = f.read()
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        'error', message='.*invalid escape sequence')
                    compile(source, path, 'exec', dont_inherit=True)


if __name__ == '__main__':
    unittest.main()
