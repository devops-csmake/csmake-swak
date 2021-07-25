# <copyright>
# (c) Copyright 2021 Cardinal Peak Technologies
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
from Csmake.CsmakeAspect import CsmakeAspect
import glob

class SkipIfFileNotExist(CsmakeAspect):
    """Purpose: Only allow the cross-cut section to run if given file does
                exist
       Type: Aspect   Library: csmake-swak
       Options: file - Path to the file to check (may use wildcards)
       Phases: *
       Joinpoints: start - Will skip the section if the specified file
                           does not exist
    """

    REQUIRED_OPTIONS = ['file']

    def start(self, phase, options, step, stepoptions):
        paths = glob.glob(options['file'])
        if len(paths) == 0:
            self.log.info("Skipping section - file '%s' found", options['file'])
            self.flowcontrol.override("doNotStart", True, self)
        self.log.passed()

