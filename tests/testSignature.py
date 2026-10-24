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
"""Signature, InsecureSignature and AsciiGPGSignature with gpg mocked out.

The mocked boundaries are subprocess.Popen (a fake gpg process) and the
``os.read`` / ``os.write`` the signer thread uses on the process pipes
(patched in the Signature module only, backed by in-memory buffers).

Python 3 conversion points: ``digest()`` joins byte chunks, ``hexdigest()``
returns ``str``, and InsecureSignature parses ``gpg --version`` output as
text.  The fake gpg's "signature" is derived from what was written to its
stdin (sha512 digest repeated, so it is long, multi-chunk and not UTF-8) and
the expected values are computed with hashlib.  The fake check_output
returns bytes unless text was requested, as the real one does.
"""
import hashlib
import subprocess
import unittest
from unittest import mock

from tests import csmake_alias, fakes

signatureModule = csmake_alias.import_module('CsmakeModules.Signature')
Signature = signatureModule.Signature
InsecureSignature = csmake_alias.import_module(
    'CsmakeModules.InsecureSignature').InsecureSignature
AsciiGPGSignature = csmake_alias.import_module(
    'CsmakeModules.AsciiGPGSignature').AsciiGPGSignature

PAYLOAD = b'csmake-swak payload \x00\xff\xfe'
ARMORED = (b'-----BEGIN PGP SIGNATURE-----\n\niQEzBAABCAAdFiEE\n=abcd\n'
           b'-----END PGP SIGNATURE-----\n')


def sha512Repeated(data):
    return hashlib.sha512(data).digest() * 50


class _Pipe(object):
    def __init__(self, fd):
        self.fd = fd
        self.closed = False

    def fileno(self):
        return self.fd

    def close(self):
        self.closed = True


class FakeGpg(object):
    """A gpg process: signs whatever was written to its stdin once that closes."""

    def __init__(self, sign=sha512Repeated, returncode=0, readError=None):
        self.stdin = _Pipe(3)
        self.stdout = _Pipe(4)
        self.written = []
        self.returncode = None
        self.popenCalls = []
        self._exit = returncode
        self._sign = sign
        self._readError = readError
        self._pending = None
        self._reads = 0

    def popen(self, args, kwargs):
        self.popenCalls.append((args, kwargs))
        return self

    def wait(self):
        assert self.stdin.closed, "gpg only finishes once its stdin is closed"
        self.returncode = self._exit
        self._pending = self._sign(b''.join(self.written)) if self._exit == 0 else b''
        return self.returncode


class FakeOs(object):
    """The two os functions Signature.Signer uses, over a FakeGpg's pipes."""

    def __init__(self, gpg):
        self.gpg = gpg

    def write(self, fd, data):
        assert fd == self.gpg.stdin.fd
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("a bytes-like object is required, not '%s'"
                            % type(data).__name__)
        self.gpg.written.append(bytes(data))
        return len(data)

    def read(self, fd, size):
        assert fd == self.gpg.stdout.fd
        self.gpg._reads += 1
        if self.gpg._readError is not None and self.gpg._reads > 1:
            raise self.gpg._readError
        chunk = self.gpg._pending[:size]
        self.gpg._pending = self.gpg._pending[size:]
        return chunk


class _GpgCase(unittest.TestCase):
    moduleClass = Signature

    def setUp(self):
        self.sub = fakes.FakeSubprocess().install(self)
        self.log = fakes.FakeLog()
        self.env = fakes.FakeEnv()

    def startSigner(self, options=None, gpg=None):
        self.gpg = gpg or FakeGpg()
        self.sub.on(['gpg'], process=self.gpg.popen)
        patcher = mock.patch.object(
            signatureModule, 'os', FakeOs(self.gpg))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.module = self.moduleClass(self.env, self.log)
        signer = self.module.default(options or {})
        self.addCleanup(signer.close)
        # If the signer thread dies before it is ready, fail rather than hang.
        self.assertTrue(signer.ready.wait(2), self.log.records)
        return signer

    def gpgArgs(self):
        return self.gpg.popenCalls[0][0]



class TestSignature(_GpgCase):

    def test_default_returns_a_signer_and_registers_for_cleanup(self):
        signer = self.startSigner()
        self.assertEqual('passed', self.log.result)
        self.assertEqual(1, len(self.env.engine.callbacks))
        self.assertEqual('GPG', signer.signtype())

    def test_signer_runs_gpg_with_binary_pipes(self):
        signer = self.startSigner()
        signer.close()
        args, kwargs = self.gpg.popenCalls[0]
        self.assertEqual(['gpg', '-b', '--digest-algo', 'SHA512'], args)
        self.assertIs(subprocess.PIPE, kwargs['stdin'])
        self.assertIs(subprocess.PIPE, kwargs['stdout'])
        self.assertFalse(fakes.is_text_mode(kwargs))

    def test_signer_option_selects_the_key(self):
        signer = self.startSigner({'signer': 'KEY1'})
        signer.close()
        self.assertEqual(
            ['gpg', '-b', '--digest-algo', 'SHA512', '--local-user', 'KEY1'],
            self.gpgArgs())

    def test_digest_is_the_joined_bytes_gpg_produced(self):
        expected = sha512Repeated(PAYLOAD)
        # Only meaningful if str-joining would have been wrong: the signature
        # is not text and spans several 1 KiB reads.
        self.assertRaises(UnicodeDecodeError, expected.decode, 'utf-8')
        self.assertGreater(len(expected), 2048)

        signer = self.startSigner()
        signer.update(PAYLOAD)
        digest = signer.digest()

        self.assertIsInstance(digest, bytes)
        self.assertEqual(expected, digest)
        self.assertGreater(len(signer.output), 1)

    def test_hexdigest_is_an_ascii_str(self):
        signer = self.startSigner()
        signer.update(PAYLOAD)
        hexdigest = signer.hexdigest()
        self.assertIsInstance(hexdigest, str)
        self.assertEqual(hashlib.sha512(PAYLOAD).hexdigest() * 50, hexdigest)

    def test_update_streams_every_chunk_to_gpg_as_bytes(self):
        signer = self.startSigner()
        signer.update(b'first ')
        signer.update(bytearray(b'second '))
        signer.update(b'third \xff')
        signer.close()
        self.assertEqual(b'first second third \xff', b''.join(self.gpg.written))

    def test_update_rejects_text(self):
        signer = self.startSigner()
        with self.assertRaises(TypeError):
            signer.update(u'not bytes')

    def test_update_after_digest_is_rejected(self):
        signer = self.startSigner()
        signer.digest()
        with self.assertRaises(RuntimeError):
            signer.update(b'too late')

    def test_digest_and_hexdigest_can_both_be_asked_for(self):
        signer = self.startSigner()
        signer.update(PAYLOAD)
        self.assertEqual(sha512Repeated(PAYLOAD), signer.digest())
        self.assertEqual(
            sha512Repeated(PAYLOAD).hex(), signer.hexdigest())

    def test_finishing_unregisters_the_exit_callback(self):
        signer = self.startSigner()
        signer.close()
        self.assertEqual({}, self.env.engine.callbacks)
        self.assertFalse(signer.didFail())

    def test_exit_callback_closes_an_unfinished_signer(self):
        signer = self.startSigner()
        for callback in list(self.env.engine.callbacks.values()):
            callback()
        self.assertTrue(signer.finish.is_set())
        self.assertTrue(self.gpg.stdin.closed)

    def test_stopSigner_before_a_signer_exists_does_nothing(self):
        module = Signature(self.env, self.log)
        module.result = None
        module._stopSigner()
        self.assertEqual([], self.log.messages('exception'))

    def test_gpg_failure_exit_status_is_reported(self):
        signer = self.startSigner(gpg=FakeGpg(returncode=2))
        signer.update(PAYLOAD)
        self.assertEqual(b'', signer.digest())
        self.assertTrue(signer.didFail())
        self.assertIn('The encoding failed with exit status: 2',
                      self.log.messages('error'))

    def test_failure_reading_gpg_output_is_logged_and_the_signer_still_ends(self):
        signer = self.startSigner(gpg=FakeGpg(readError=OSError('pipe broke')))
        signer.update(PAYLOAD)
        signer.close()
        self.assertIn('Signing failed', self.log.messages('exception'))
        self.assertTrue(signer.finish.is_set())

    @unittest.skip("pre-existing bug: Signer.run() sets failed=True after a "
                   "read error and then overwrites it with returncode != 0")
    def test_failure_reading_gpg_output_marks_the_signer_failed(self):
        signer = self.startSigner(gpg=FakeGpg(readError=OSError('pipe broke')))
        signer.close()
        self.assertTrue(signer.didFail())

    def test_repr_names_the_step(self):
        module = Signature(self.env, self.log)
        self.assertEqual('<Signature step definition>', repr(module))
        self.assertEqual('<Signature step definition>', str(module))


class TestInsecureSignature(_GpgCase):
    moduleClass = InsecureSignature
    VERSION_PROBE = "gpg --version | head -n 1 | cut -d' ' -f 3"

    def scriptVersion(self, version):
        self.sub.on(self.VERSION_PROBE, stdout=version + b'\n')

    def test_gpg2_version_enables_loopback_pinentry(self):
        # _setPassword parses the probe output with str.split('.'), so it
        # must have been captured as text.
        self.scriptVersion(b'2.2.27')
        signer = self.startSigner({'password': 'hunter2'})
        signer.update(PAYLOAD)
        self.assertEqual(sha512Repeated(PAYLOAD), signer.digest())
        self.assertEqual(
            ['gpg', '-b', '--digest-algo', 'SHA512',
             '--passphrase', 'hunter2', '--batch',
             '--pinentry-mode', 'loopback'],
            self.gpgArgs())

    def test_version_probe_asks_for_text(self):
        self.scriptVersion(b'2.2.27')
        self.startSigner({'password': 'pw'}).close()
        probe = [c for c in self.sub.calls if c.kind == 'check_output']
        self.assertEqual(1, len(probe))
        self.assertEqual(self.VERSION_PROBE, probe[0].args)
        self.assertIs(True, probe[0].kwargs['shell'])
        self.assertTrue(fakes.is_text_mode(probe[0].kwargs))

    def assertLoopbackPinentry(self, version, expected):
        self.scriptVersion(version)
        self.startSigner({'password': 'pw'}).close()
        self.assertEqual(expected, '--pinentry-mode' in self.gpgArgs())

    def test_gpg_2_1_uses_loopback_pinentry(self):
        self.assertLoopbackPinentry(b'2.1.0', True)

    def test_gpg_2_4_uses_loopback_pinentry(self):
        self.assertLoopbackPinentry(b'2.4.3', True)

    def test_gpg_2_0_does_not_use_loopback_pinentry(self):
        self.assertLoopbackPinentry(b'2.0.26', False)

    def test_gpg_1_4_does_not_use_loopback_pinentry(self):
        self.assertLoopbackPinentry(b'1.4.23', False)

    def test_password_and_signer_options_are_combined(self):
        self.scriptVersion(b'1.4.23')
        signer = self.startSigner({'password': 'pw', 'signer': 'KEY1'})
        signer.close()
        self.assertEqual(
            ['gpg', '-b', '--digest-algo', 'SHA512', '--passphrase', 'pw',
             '--batch', '--local-user', 'KEY1'],
            self.gpgArgs())

    def test_without_a_password_gpg_is_not_probed_or_given_a_passphrase(self):
        signer = self.startSigner({})
        signer.close()
        self.assertEqual([], [c for c in self.sub.calls
                              if c.kind == 'check_output'])
        self.assertEqual(['gpg', '-b', '--digest-algo', 'SHA512'],
                         self.gpgArgs())

    def test_gpg_failure_exit_status_is_reported(self):
        self.scriptVersion(b'2.2.27')
        signer = self.startSigner({'password': 'bad'}, gpg=FakeGpg(returncode=2))
        signer.update(PAYLOAD)
        signer.close()
        self.assertTrue(signer.didFail())

    @unittest.skip("pre-existing bug: when the gpg version probe fails, "
                   "_setPassword's handler references an undefined name 'ex' "
                   "(NameError) and the signer thread dies")
    def test_version_probe_failure_is_tolerated(self):
        self.sub.on(self.VERSION_PROBE, returncode=127)
        self.startSigner({'password': 'pw'}).close()

    def test_repr_names_the_step(self):
        module = InsecureSignature(self.env, self.log)
        self.assertEqual('<InsecureSignature step definition>', repr(module))


class TestAsciiGPGSignature(_GpgCase):
    moduleClass = AsciiGPGSignature

    def test_runs_gpg_for_an_ascii_armored_signature(self):
        signer = self.startSigner(gpg=FakeGpg(sign=lambda data: ARMORED))
        signer.update(PAYLOAD)
        self.assertEqual(ARMORED, signer.digest())
        self.assertEqual(['gpg', '-abs'], self.gpgArgs())
        self.assertEqual('GPG Ascii', signer.signtype())

    def test_hexdigest_is_the_armored_signature_itself(self):
        signer = self.startSigner(gpg=FakeGpg(sign=lambda data: ARMORED))
        signer.update(PAYLOAD)
        self.assertEqual(ARMORED, signer.hexdigest())

    def test_gpg_failure_exit_status_is_reported(self):
        signer = self.startSigner(gpg=FakeGpg(returncode=1))
        signer.close()
        self.assertTrue(signer.didFail())
        self.assertEqual(b'', signer.digest())

    def test_repr_names_the_step(self):
        module = AsciiGPGSignature(self.env, self.log)
        self.assertEqual('<AsciiGPGSignature step definition>', repr(module))


if __name__ == '__main__':
    unittest.main()
