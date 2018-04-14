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
from CsmakeModules.Shell import Shell
import os
import re
import subprocess
import sys

class ChrootShell(Shell):
    """Purpose: Execute out to a shell command in a chroot environment
       Type: Module   Library: csmake-swak
       Options:
           command - shell command to execute (semi-colons need to be escaped)
             use command(<phase>) to specify the command for a given phase
             default is 'build'
           env - (OPTIONAL) Reference to a ShellEnv to use
                 Can be multiple envs, comma separated
                 These environment definitions will be used in conjunction
                 with the current DIB environment.
           exec - (OPTIONAL) command to execute
           chroot - (OPTIONAL) path to the chroot
                     If not given, this will behave just like Shell
           as-user - (OPTIONAL) sudo to given user
                     (requires sudo installed in chroot environment)
       Phase: Any
       Notes: chrooting requires sudo access
           The chroot execution works by
           doing sudo -E chroot bash -c "<contents of command>"
           On execution, csmake will escape ` " and $ so that they will
           not be expanded outside of the execution of the "command"
       Example:
           [ShellEnv@my-command-env]
           THIS_DIR=mydir

           [ChrootShell@my-command]
           command = mkdir -p ${THIS_DIR} && pushd ${THIS_DIR}
              ifconfig > my.cfg
              ls
              popd
              ls
           env = my-command-env, default-env
           chroot = /path/to/my/chroot
    """

    def _substituteSlashes(self, matchobj):
        return '\\' + matchobj.group(0)

    SHELL_ESCAPES = re.compile('[`"$]')
    def _executeShell(self, command, env, execer='/bin/bash'):
        modcommand = None
        if self.chroot is None:
            self.log.warning("ChrootShell section does not specify a chroot path")
            modcommand = command
        else:
            asUserPart = " "
            if self.asUser is not None:
                asUserPart = " sudo -H -E -u %s " % self.asUser
            modcommand = "sudo -E chroot %s%s%s -c \"%s\"" % (
                self.chroot,
                asUserPart,
                execer,
                re.sub(self.SHELL_ESCAPES, self._substituteSlashes, command) )
        return Shell._executeShell(self, modcommand, env)

    def default(self, options):
        self.chroot = None
        self.asUser = None
        if 'chroot' in options:
            self.chroot = options['chroot']
        if 'as-user' in options:
            self.asUser = options['as-user']
        return Shell.default(self, options)
