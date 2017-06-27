# <copyright>
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
# <copyright>
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
from CsmakeModules.Signature import Signature
import threading
import subprocess
import binascii

class AsciiGPGSignature(Signature):
    """Purpose: Returns an object that behaves like a hashlib hash function.
                That object will return an ASCII armored GPG signature
                when digest or hexdigest is called.
       Type: Submodule   Library: csmake-swak
       Implements: Signature
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
        return "<AsciiGPGSignature step definition>"

    def __str__(self):
        return "<AsciiGPGSignature step definition>"

    def __init__(self, env, log):
        Signature.__init__(self, env, log)
        self.signerFactory = AsciiGPGSignature.AsciiGPGSigner

    class AsciiGPGSigner(Signature.Signer):
        def __init__(self, options, log, parent):
            Signature.Signer.__init__(self, options, log, parent)
            self.command = ['gpg', '-abs']

        def signtype(self):
            return 'GPG Ascii'

        def hexdigest(self):
            #This actually doesn't make sense to try to do a hexl
            return self.digest()

