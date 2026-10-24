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
"""TemporaryFileHack on real files with real chmod.

The aspect shells out to ``sudo chmod`` / ``sudo mv`` to hack files it may not
own.  A fake ``sudo`` that simply runs its arguments is put first on PATH so
the real chmod still happens, without needing root.

Python 3 conversion points: ``oct(mode)[1:]`` -> ``'%o' % mode`` (py3 gives
``'0o755'``, so the old slice produced ``'o755'`` and the restore chmod
failed, leaving files world-writable), ``file()`` -> ``open()``, octal
literals, and feeding the patch text to ``patch`` in text mode.
"""
import os
import shutil
import stat
import tempfile
import unittest

from tests import csmake_alias, fakes

TemporaryFileHack = csmake_alias.import_module(
    'CsmakeModules.TemporaryFileHack').TemporaryFileHack

FAKE_SUDO = '#!/bin/sh\nexec "$@"\n'

PATCH = """\
--- a/target.txt
+++ b/target.txt
@@ -1,3 +1,3 @@
 one
-two
+TWO
 three
"""


def mode_of(path):
    return stat.S_IMODE(os.stat(path).st_mode)


class TestTemporaryFileHack(unittest.TestCase):

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix='swak-hack-'))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        bindir = os.path.join(self.tmp, 'bin')
        os.mkdir(bindir)
        fakes.write_executable(bindir, 'sudo', FAKE_SUDO)
        patcher = fakes.path_first(bindir)
        patcher.start()
        self.addCleanup(patcher.stop)

        # The directory holding the hacked file, with distinctive modes so a
        # failed restore is visible (the hack itself opens everything to 777).
        self.workdir = os.path.join(self.tmp, 'work')
        os.mkdir(self.workdir)
        os.chmod(self.workdir, 0o750)
        self.target = os.path.join(self.workdir, 'target.txt')
        self.saved = self.target + '.csmake-TemporaryFileHack-save'

        self.log = fakes.FakeLog()
        self.aspect = TemporaryFileHack(fakes.FakeEnv(self.tmp), self.log)

    def writeTarget(self, text, mode=0o640):
        with open(self.target, 'w') as f:
            f.write(text)
        os.chmod(self.target, mode)

    def read(self, path):
        with open(path) as f:
            return f.read()

    def hack(self, **options):
        options['file'] = self.target
        self.options = options
        self.aspect._hackFile('build', options, None, None)
        self.assertEqual('passed', self.log.result, self.log.records)

    def unhack(self):
        self.aspect._unhackFile('build', self.options, None, None)
        self.assertEqual('passed', self.log.result, self.log.records)

    def test_replace_hacks_then_restores_content_and_permissions(self):
        self.writeTarget('original\n', mode=0o640)

        self.hack(replace='replaced\n')

        self.assertEqual('replaced\n', self.read(self.target))
        self.assertEqual('original\n', self.read(self.saved))
        # Plain digits such as '640', never '0o640' / 'o640'.
        self.assertEqual('640', self.aspect.realFileMode)
        self.assertEqual('750', self.aspect.realDirMode)

        self.unhack()

        self.assertEqual('original\n', self.read(self.target))
        self.assertFalse(os.path.exists(self.saved))
        self.assertEqual(0o640, mode_of(self.target))
        self.assertEqual(0o750, mode_of(self.workdir))
        self.assertEqual([], self.log.messages('error'))

    def test_hack_of_a_new_file_removes_it_and_restores_the_directory(self):
        self.hack(append='created\n')

        self.assertEqual('created\n', self.read(self.target))

        self.unhack()

        self.assertFalse(os.path.exists(self.target))
        self.assertEqual(0o750, mode_of(self.workdir))

    def test_append_and_append_file_add_text_to_the_original(self):
        self.writeTarget('base\n')
        extra = os.path.join(self.tmp, 'extra.txt')
        with open(extra, 'w') as f:
            f.write('from file\n')

        self.hack(append='inline\n')
        self.assertEqual('base\ninline\n', self.read(self.target))
        self.unhack()
        self.assertEqual('base\n', self.read(self.target))

        self.log.result = None
        self.hack(**{'append-file': extra})
        self.assertEqual('base\nfrom file\n', self.read(self.target))
        self.unhack()
        self.assertEqual('base\n', self.read(self.target))
        self.assertEqual(0o640, mode_of(self.target))

    @unittest.skipUnless(shutil.which('patch'), "patch is not installed")
    def test_inline_patch_is_fed_to_patch_as_text(self):
        self.writeTarget('one\ntwo\nthree\n')

        self.hack(patch=PATCH)

        self.assertEqual('one\nTWO\nthree\n', self.read(self.target))
        self.unhack()
        self.assertEqual('one\ntwo\nthree\n', self.read(self.target))


if __name__ == '__main__':
    unittest.main()
