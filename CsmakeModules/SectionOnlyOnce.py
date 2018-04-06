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
from Csmake.CsmakeAspect import CsmakeAspect

class SectionOnlyOnce(CsmakeAspect):
    """Purpose: Only allow the cross-cut section to run one time (per phase)
       Type: Aspect   Library: csmake-swak
       Phases: *
       Joinpoint: start - will only allow the section one time per phase
       Flowcontrol: Issues an overriding doNotStart after the first execution
       Environment: Adds a __<step id>:SectionOnlyOnce__ definition to mark
                    that the section was executed
    """

    def start(self, phase, options, step, stepoptions):
        calledIdEnv = "__%s:SectionOnlyOnce__" % step.calledId
        if calledIdEnv in self.env.env:
            self.flowcontrol.override("doNotStart", True, self)
        self.env.env[calledIdEnv] = True
        self.log.passed()
