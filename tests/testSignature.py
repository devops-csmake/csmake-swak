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
"""Signature / InsecureSignature against a fake ``gpg`` on PATH.

The real signer pipes data into ``gpg -b`` and reads the binary signature
back in 1 KiB chunks, so the interesting Python 3 points are bytes handling
(``digest()`` joins byte chunks, ``hexdigest()`` must hand back ``str``) and,
for InsecureSignature, parsing ``gpg --version`` output as text.  The fake gpg
emits a deterministic, non-UTF-8, multi-chunk "signature" derived from stdin
(sha512 digest repeated) so the expected values come from hashlib.
"""
import hashlib
import os
import shutil
import tempfile
import unittest
import warnings

from tests import csmake_alias, fakes

Signature = csmake_alias.import_module('CsmakeModules.Signature').Signature
InsecureSignature = csmake_alias.import_module(
    'CsmakeModules.InsecureSignature').InsecureSignature

FAKE_GPG = """\
import hashlib
import os
import sys

args = sys.argv[1:]
if '--version' in args:
    sys.stdout.write('gpg (GnuPG) %s\\nlibgcrypt 1.8.8\\n'
                     % os.environ.get('FAKE_GPG_VERSION', '2.2.27'))
    sys.exit(0)
with open(os.environ['FAKE_GPG_ARGS'], 'a') as f:
    f.write(' '.join(args) + '\\n')
data = sys.stdin.buffer.read()
sys.stdout.buffer.write(hashlib.sha512(data).digest() * 50)
"""

PAYLOAD = b'csmake-swak payload \x00\xff\xfe'


def expectedSignature(data):
    return hashlib.sha512(data).digest() * 50


class _FakeGpgCase(unittest.TestCase):
    version = '2.2.27'

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='swak-gpg-')
        self.addCleanup(shutil.rmtree, self.tmp, True)
        bindir = os.path.join(self.tmp, 'bin')
        os.mkdir(bindir)
        fakes.write_python_executable(bindir, 'gpg', FAKE_GPG)
        # Pre-existing and harmless: Signer.run() passes bufsize=1 for binary
        # pipes, a RuntimeWarning on 3.8+.  Keep it out of the test output.
        warningState = warnings.catch_warnings()
        warningState.__enter__()
        self.addCleanup(warningState.__exit__, None, None, None)
        warnings.filterwarnings(
            'ignore', message='line buffering', category=RuntimeWarning)
        self.argsLog = os.path.join(self.tmp, 'gpg-args')
        patcher = fakes.path_first(bindir)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ['FAKE_GPG_ARGS'] = self.argsLog
        os.environ['FAKE_GPG_VERSION'] = self.version
        self.log = fakes.FakeLog()

    def sign(self, moduleClass, options):
        module = moduleClass(fakes.FakeEnv(self.tmp), self.log)
        signer = module.default(options)
        # Signer reads process.stdout by fileno and never closes it; do so
        # here (cleanups run last-in first-out, so after signer.close).
        self.addCleanup(
            lambda: signer.process is None or signer.process.stdout.close())
        self.addCleanup(signer.close)
        # If the signer thread dies before it is ready (e.g. while setting up
        # its gpg command line), fail promptly instead of blocking forever.
        self.assertTrue(signer.ready.wait(10), self.log.records)
        signer.update(PAYLOAD)
        return signer

    def gpgArgs(self):
        with open(self.argsLog) as f:
            return f.read().split()


class TestSignature(_FakeGpgCase):

    def test_digest_is_bytes_and_hexdigest_is_str(self):
        expected = expectedSignature(PAYLOAD)
        # The comparison below is only meaningful if str-joining would have
        # been wrong: the signature is not text and spans several read chunks.
        self.assertRaises(UnicodeDecodeError, expected.decode, 'utf-8')
        self.assertGreater(len(expected), 1024)

        signer = self.sign(Signature, {})

        digest = signer.digest()
        self.assertIsInstance(digest, bytes)
        self.assertEqual(expected, digest)
        self.assertGreater(len(signer.output), 1)

        hexdigest = signer.hexdigest()
        self.assertIsInstance(hexdigest, str)
        self.assertEqual(hexdigest, hashlib.sha512(PAYLOAD).hexdigest() * 50)
        self.assertFalse(signer.didFail())


class TestInsecureSignature(_FakeGpgCase):

    def test_gpg2_version_enables_loopback_pinentry(self):
        # _setPassword parses 'gpg --version' output with str.split('.').
        signer = self.sign(
            InsecureSignature, {'password': 'hunter2', 'signer': 'KEY1'})
        self.assertEqual(expectedSignature(PAYLOAD), signer.digest())
        self.assertEqual(
            ['-b', '--digest-algo', 'SHA512',
             '--passphrase', 'hunter2', '--batch',
             '--pinentry-mode', 'loopback', '--local-user', 'KEY1'],
            self.gpgArgs())

    def test_gpg1_version_does_not_use_loopback_pinentry(self):
        os.environ['FAKE_GPG_VERSION'] = '1.4.23'
        signer = self.sign(InsecureSignature, {'password': 'hunter2'})
        signer.close()
        self.assertEqual(
            ['-b', '--digest-algo', 'SHA512', '--passphrase', 'hunter2',
             '--batch'],
            self.gpgArgs())


if __name__ == '__main__':
    unittest.main()
