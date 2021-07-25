# <copyright>
# (c) Copyright 2021 Cardinal Peak Technologies
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
import os.path

class SkipUnlessEqual(CsmakeAspect):
    """Purpose: Only allow the cross-cut section to run if the 'given'
                parameter is equal to the 'comparison'
       Type: Aspect   Library: csmake-swak
       Options:
          given      - The given value to compare
          comparison - The equality value to use in the comparison
       Phases: *
       Joinpoints: start - Will skip the section unless given == comparison
    """

    REQUIRED_OPTIONS = ['given', 'comparison']

    def start(self, phase, options, step, stepoptions):
        if options['given'] != options['comparison']:
            self.log.info("Skipping section - %s is not %s", options['given'], options['comparison'])
            self.flowcontrol.override("doNotStart", True, self)
        self.log.passed()

