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
from Csmake.CsmakeModule import CsmakeModule
import os.path
import os

class ClearTemporalVersioning(CsmakeModule):
    """Purpose: Clear the 'sticky' temporal version in phases specified
                in the 'phases' option below.
       Type: Module   Library: csmake-swak
       Phases: *any* (as listed in the 'phases' option.)
       Options: (same as "versioning", see csmake --list-type=versioning)
           phases - Phases to execute clear (comma or newline delimited)
       Notes: It is suggested that this section be executed *before*
                TemporalVersioning sections are executed.
                (for: CLDSYS-10109, consider pulling into csmake core)
              This will clear the file %(RESULTS)s/,__temporalversions
       Environment: In addition to the file, this also deletes the
           cross-phase environment dictionary for these versions in
           the environment with the key: __TemporalVersioning
    """

    REQUIRED_OPTIONS = ['phases']

    def __repr__(self):
        return "<ClearTemporalVersioning step definition>"

    def __str__(self):
        return "<ClearTemporalVersioning step definition>"

    def default(self, options):
        phase = self.engine.getPhase()
        execPhases = ','.join(options['phases'].split('\n')).split(',')
        execPhases = [ x.strip() for x in execPhases if len(x.strip()) > 0 ]
        if phase not in execPhases:
            self.log.skipped()
            return None
        pathToTemporalFile = os.path.join(
            self.env.env['RESULTS'],
            '.__temporalversions')
        if os.path.exists(pathToTemporalFile):
            try:
                os.remove(pathToTemporalFile)
            except:
                self.log.exception("Could not delete stored versions")
                self.log.failed()
                return None

        if '__TemporalVersioning' in self.env.transPhase:
            del self.env.transPhase['__TemporalVersioning']

        if '__TemporalVersioning' in self.env.env:
            del self.env.env['__TemporalVersioning']
        self.log.passed()

