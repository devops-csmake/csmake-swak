# <copyright>
# (c) Copyright 2018,2020 Cardinal Peak Technologies
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
from CsmakeModules.Signature import Signature
import threading
import subprocess
import binascii

class InsecureSignature(Signature):
    """Purpose: Returns an object that behaves like a hashlib hash function.
                That object will return a signature when digest or hexdigest
                is called
       Type: Submodule   Library: csmake-swak
       Implements: Signature
       Phases: *any*
       Options:
           signer - (OPTIONAL) Default will be a default key holder
           password - (OPTIONAL) Default will be to ask the user
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
        return "<InsecureSignature step definition>"

    def __str__(self):
        return "<InsecureSignature step definition>"

    def __init__(self, env, log):
        Signature.__init__(self, env, log)
        self.signerFactory = InsecureSignature.InsecureSigner

    class InsecureSigner(Signature.Signer):
        def _setPassword(self, password):
            self.command.extend(['--passphrase', password, '--batch'])
            try:
                version = subprocess.check_output(
                    "gpg --version | head -n 1 | cut -d\' \' -f 3",
                    shell=True ).strip()
                major, minor, patch = version.split('.')
                major = int(major)
                minor = int(minor)
                patch = int(patch)
                if major >= 2 and minor >= 1:
                    self.command.extend(['--pinentry-mode', 'loopback'])
            except:
                self.log.warning("GPG version test failed: %s", str(ex))

        def run(self):
            if 'password' in self.options:
                self._setPassword(self.options['password'])
            return Signature.Signer.run(self)
