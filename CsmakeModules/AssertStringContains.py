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
from Csmake.CsmakeModule import CsmakeModule

class AssertStringContains(CsmakeModule):
    """Purpose: Assert that a given string (haystack) contains a
                substring (needle).
       Type: Module   Library: csmake-swak
       Phases: build - The assert is only valid in the "build" phase
       Options:
           haystack - The string that the needle must be found in.
           needle - The substring that the haystack must contain
       Future: Consider making the phase configurable
    """

    REQUIRED_OPTIONS = ['needle', 'haystack']

    def build(self, options):
        if options['needle'] in options['haystack']:
            self.log.passed()
        else:
            self.log.error("Expected '" + options['needle'] + "' to appear in '" + options['haystack'] + "'")
            self.log.failed()
