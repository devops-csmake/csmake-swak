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
from Csmake.CsmakeModuleAllPhase import CsmakeModuleAllPhase
import subprocess

class EnvironmentCapture(CsmakeModuleAllPhase):
    """Purpose:
           When executed, will modify the current version to include
           specified information.
           A special field is enclosed in curly braces, i.e. {datetime}
           The module may be specialized to allow for special fields
           calculated in ways not anticipated by this module
           Essentially, you can specify a constant, a shell calculated value,
               or a value returned from a module.
       Type: Module   Library: csmake-swak
       Phases: *any*
       Options:
           env-name=Environment variable to set with the formatted result
           format= Any string.  keys are enclosed with curlies
                    e.g., {datetime}.{getSHA}
                Note: Any specified csmake environment variables are substituted
                before the keys are processed.
                To escape curly braces - double the right side
                    e.g.,  {my}} Will literally be {my} in the result
           shell_<key>= executes a shell command and puts the result in for
                        any references of <key>
           step_<key>= executes a specified step and puts the result in for
                        any references of <key>
           value_<key>= places the string in for any references of key
           dry-run=(OPTIONAL) If true will only return the calculated
                   version string without updating the metadata.
    """

    REQUIRED_OPTIONS=['env-name', 'format']

    def __repr__(self):
        return "<<EnvironmentShellCapture step definition>>"

    def __str__(self):
        return "<<EnvironmentShellCapture step definition>>"

    def default(self, options):
        self.format = options['format']
        formatdict = {}
        for key, value in options.iteritems():
            keyparts = key.split('_')
            if len(keyparts) != 2:
                continue
            #TODO: Structure this so keyparts[0] makes a call
            #      using the value so that it's easy to extend this
            #      apparatus
            if keyparts[0] == 'shell':
                p = subprocess.Popen(
                    value,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE )
                stdout, stderr = p.communicate()
                if p.returncode != 0:
                    self.log.warning("%s produced a non-zero returncode (%d)",
                        value,
                        p.returncode )
                    self.log.warning("   As a result, <<error>> will be given instead of the intended value")
                    formatdict[keyparts[1]] = '<<error>>'
                else:
                    resultvalue = str(stdout).strip()
                    self.log.debug("Version %s: %s", keyparts[1], resultvalue)
                    formatdict[keyparts[1]] = resultvalue
            elif keyparts[0] == 'value':
                formatdict[keyparts[1]] = value
            elif keyparts[0] == 'step':
                phase = self.engine.getPhase()
                result = self.engine.launchStep(
                    value,
                    phase)
                if result is None or not result._didPass():
                    self.log.warning("%s step failed", value)
                    self.log.warning("   As a result, <<error>> will be given instead of the intended value")
                    formatdict[keyparts[1]] = '<<error>>'
                else:
                    formatdict[keyparts[1]] = str(result._getReturnValue(phase))
        result = self.format
        result = self._parseBrackets(result, formatdict)
        if self.metadata is not None and (
            'dry-run' not in options or options['dry-run'].strip() != 'True'):
            self.env.env[options['env-name']] = result
        self.log.passed()
        return result
