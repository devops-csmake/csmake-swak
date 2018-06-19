# <copyright>
# (c) Copyright 2018 Cardinal Peak Technologies
# (c) Copyright 2017 Hewlett Packard Enterprise Development LP
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
from Csmake.CsmakeModuleAllPhase import CsmakeModuleAllPhase
import threading
import subprocess
import binascii

class Signature(CsmakeModuleAllPhase):
    """Purpose: Returns an object that behaves like a hashlib hash function.
                That object will return a signature when digest or hexdigest
                is called
       Type: Submodule   Library: csmake-swak
       Phases: *any*
       Options:
           signer - (OPTIONAL) Default will be a default key holder
       Notes: To finish cleanly, the close, or digest/hexdigest must be
              called.
              You must have a private key installed on your keyring to
              be able to do signing.
              See: https://fedoraproject.org/wiki/Creating_GPG_Keys
              for example.
       Also Note: The signer digest object will also respond to the
                  'signtype' method.
                  This submodule's signtype is: GPG
              This produces an RSA/SHA512 (RPM compliant) signature
    """

    #TODO: Pull this (or better) in to csmake core (CLDSYS-10109).
    #TODO: The addTransPhase is missing the obvious clearTransPhase
    #       in Csmake.Environment

    def __repr__(self):
        return "<Signature step definition>"

    def __str__(self):
        return "<Signature step definition>"

    def __init__(self, env, log):
        CsmakeModuleAllPhase.__init__(self, env, log)
        self.signerFactory = Signature.Signer

    class Signer(threading.Thread):
        def __init__(self, options, log, parent):
            threading.Thread.__init__(self)
            self.parent = parent
            self.input = None
            self.output = None
            self.process = None
            self.options = options
            self.ready = threading.Event()
            self.finish = threading.Event()
            self.failed = False
            self.log = log
            self.command = ['gpg', '-b', '--digest-algo', 'SHA512']

        def signtype(self):
            return 'GPG'

        def update(self, buf):
            if self.finish.is_set():
                raise RuntimeError("update may not be called after digest or close")
            self.ready.wait()
            self.input.write(buf)

        def _finish(self):
            if self.finish.is_set():
                self.join()
            self.finish.set()
            self.join()

        def hexdigest(self):
            self._finish()
            return binascii.hexlify(''.join(self.output))

        def digest(self):
            self._finish()
            return ''.join(self.output)

        def close(self):
            self._finish()

        def didFail(self):
            return self.failed

        def _setSigner(self, signer):
            self.command.extend(['--local-user', signer])

        def run(self):
            if 'signer' in self.options:
                self._setSigner(self.options['signer'])
            self.process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stdin=subprocess.PIPE )
            self.input = self.process.stdin
            self.ready.set()
            self.finish.wait()
            self.input.close()
            self.process.wait()
            buf = self.process.stdout.read()
            self.output = []
            while len(buf) > 0:
                self.output.append(buf)
                try:
                    buf = self.process.stdout.read()
                except:
                    break
            self.parent._unregisterOnExitCallback("_stopSigner")
            result = self.process.returncode
            self.failed = result != 0
            if self.failed:
                self.log.error(
                    "The encoding failed with exit status: %d",
                    self.process.returncode )
                return 1
            else:
                return 0

    def _stopSigner(self):
        if self.result is not None:
            try:
                self.result.close()
            except:
                self.log.exception("Could not properly end Signer object")

    def default(self, options):
        self.result = self.signerFactory(options, self.log, self)
        self._registerOnExitCallback("_stopSigner")
        self.result.start()
        self.log.passed()
        return self.result
