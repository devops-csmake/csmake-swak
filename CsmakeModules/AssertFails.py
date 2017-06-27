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
from Csmake.CsmakeAspect import CsmakeAspect

class AssertFails(CsmakeAspect):
    """Purpose: Assert that a decorated section fails.
       Type: Aspect   Library: csmake-swak
       Phases: *
       Joinpoints: failed - Changes failed to passed
                   passed - Changes passed to failed
    """
    def recursivePassed(self, result):
        result.passed()
        for child in result.childResults:
            self.recursivePassed(child)

    def failed(self, phase, options, step, stepoptions):
        # We expected the failure, so let's set the step status to passed
        self.recursivePassed(step.log)

    def passed(self, phase, options, step, stepoptions):
        # We expect a failure, so if we get a pass, that's a fail for us
        step.log.failed()
