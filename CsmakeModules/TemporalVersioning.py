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
from CsmakeModules.versioning import versioning
import pickle
import os.path
import os

class TemporalVersioning(versioning):
    """Purpose: Implement a 'sticky' version for use with timestamps
                and other information that may change within each phase.
       Implements: versioning
       Type: Module   Library: csmake-swak
       Phases: *any*
       Options:
           designation - The designation of the version part (a key)
           format - Any string with designations in curly braces:
                 e.g. {a}-{b}.part{c} where a, b, and c are <key>s in the
                      options below
           shell_<key> - executes a shell command and puts the
                        result in for any references of {<key>} in the format
                        option.
           step_<key> - executes a specified step and puts the result in for
                        any references of {<key>} in the format option
           value_<key> - places the string in for any references of {<key>}
                        in the format option.
       Notes: This will drop a pickle file %(RESULTS)s/.__temporalversions
                The file may be cleared by deleting the this file
                or by use of the ClearTemporalVersioning section.
              Consider using the ClearTemporalVersioning section prior
                to use of this section to ensure consistency arcoss
                phases of the build based on the options in the clear section.
       Environment: In addition to the file, this also creates a
           cross-phase environment dictionary for these versions in
           the environment with the key: __TemporalVersioning
       See Also:
           csmake --list-type versioning
       Future Work:
           Ultimately, a redesign of versioning
           should consider concepts explored here to ensure
           consistent management of versioning across phases
           of the build: CLDSYS-10109
    """

    #TODO: Pull this (or better) in to csmake core (CLDSYS-10109).
    #TODO: The addTransPhase is missing the obvious clearTransPhase
    #       in Csmake.Environment

    def __repr__(self):
        return "<TemporalVersioning step definition>"

    def __str__(self):
        return "<TemporalVersioning step definition>"

    def default(self, options):
        pathToTemporalFile = os.path.join(
            self.env.env['RESULTS'],
            '.__temporalversions' )
        if '__TemporalVersioning' not in self.env.env:
            temporal = {}
            if os.path.exists(pathToTemporalFile):
                try:
                    with open(pathToTemporalFile) as temporalFile:
                        temporal = pickle.load(temporalFile)
                except:
                    self.log.exception("Failed to open/read temporal file")
                    #TODO: attempt to remove unusable file
            self.env.addTransPhase('__TemporalVersioning', temporal)
        temporal = self.env.env['__TemporalVersioning']
        result = None
        designation = options['designation']
        if designation not in temporal:
            #Do calculation
            result = versioning.default(self, options)

            #add it to the dictionary
            temporal[designation] = self.metadata.version[designation]

            #Rewrite the pickle
            try:
                with open(pathToTemporalFile, 'w') as temporalFile:
                    pickle.dump(temporal, temporalFile)
            except:
                self.log.exception("Failed to store the updated temporal versioning")
        else:
            result = temporal[designation]
            self.metadata._addVersionString(designation, result)
        self.log.passed()
        return result
