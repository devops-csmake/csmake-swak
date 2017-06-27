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

class EnvironmentConditional(CsmakeAspect):
    """Purpose: Conditionally do a section
       Type: Module   Library: csmake-swak
       Phases:
           * - Will allow execution of a section if the environment
               variable is not set, then set the option from the
               section.  If the environment variable is set,
               it will advise skipping the section.

               The environment name will only be set if the
               main section passes.
       Options:
           ifEnvNotSet   - Environment variable to check and possibly set...
                   (Environment substitutions are not applied)
                   If the specified environment variable is set,
                     This step will be skipped.
                   If the specified environment vairable is not set,
                     This step will be executed, and the given variable
                     will be set to the path to the repo.
           thenUseSectionOptions -
                   Option to use as the value ifEnvSet's option name
                   is not defined in the environment. The option names
                   need to be enclosed in braces ('{' '}') and other text
                   may be used with the substitutions.  To literally put a
                   right brace in the resulting text, use a double brace ('}}')
       Example:
           [&EnvironmentConditional@stuff]
           ifEnvNotSet=myenv
           thenUseSectionOptions={xyzzy}/{abcaba}

           [MyModule@stuff]
           xyzzy = my stuff
           abcaba = other stuff

           * If myenv isn't defined in the csmake environment
             the stuff section will be executed and xyzzy's value
             (my stuff) along with abcaba's value (other stuff) will
             be put in the environment as "my stuff/other stuff".
    """

    REQUIRED_OPTIONS = ['ifEnvNotSet', 'thenUseSectionOptions']

    def start(self, phase, options, gitDependent, sectionOptions):
        envTarget = options['ifEnvNotSet']
        if envTarget in self.env.env:
            self.log.info("'%s' is defined in the environment, section will be skipped", envTarget)
            self.flowcontrol.vote("doNotStart", True, self)
            self.log.passed()
        else:
            self.flowcontrol.vote("doNotStart", False, self)
            self.log.passed()
        return True

    def end(self, phase, options, gitDependent, sectionOptions):
        #Gahhh - sorry this is a little gross....
        #  This just breaks out all the single right braces and looks
        #  for brace enclosed sections and does the substitutions
        #  preserving the double right braces as single right braces.
        envTarget = options['ifEnvNotSet']
        if envTarget in self.env.env:
            self.log.debug("Not setting '%s' - already set", envTarget)
            self.log.passed()
            return True
        envValue = self._parseBrackets(options['thenUseSectionOptions'], sectionOptions)
        self.log.info("Setting environment variable '%s' with value '%s'",
            options['ifEnvNotSet'],
            envValue )
        self.env.env[options['ifEnvNotSet']] = envValue
        self.log.passed()
        return True
