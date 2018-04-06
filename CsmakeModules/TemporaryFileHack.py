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
import shutil
import os.path
import os
import subprocess

class TemporaryFileHack(CsmakeAspect):
    """Purpose: Modify a file for a specific specification section
       Type: Aspect   Library: csmake-swak
       Description:
           This aspect allows you to modify a file during a build while
           a specific section is being performed.
           This can be helpful if most of the build requires one configuration
           but another requires a special configuration.
           Or, in cases where developer provided content is consumed as part
           of the build, but needs to be modified for the purposes of the build
       Phases: (Defined by options)
       Options:
           file - File to modify
         :: Types of hacking - use one of the following ::
           patch - Inline patch diff
           patch-file - Path to file containing the patch diff to apply
           replace - Inline replacement of the file
           replace-file - Path to file containing the new file contents
           append - Inline append of the file
           append-file - Path to file containing the new lines to append
         :: Controls for hacking - these are all OPTIONAL ::
           phases - comma/newline separated list of phases to apply the hack
                    Default is: * (all phases)
           joinpoint - Joinpoint advice to act on.
                    Default is: start
           end-joinpoint - Joinpoint advice to restore with.
                    Default is: end
           line-pad - character or string that will start each line
                    line-pad is helpful to maintain spacing, for inline
                    patches, for example.  The csmakefile will not maintain
                    whitespace without a pad.
                    Default is: (no padding)
           temp-file -  location to store the old file to restore it
                    Default is:
                       <file dir>/<file name>.csmake-TemporaryFileHack-save
           keepChanges - The old file will not be restored if True
                    Default is: False
        Notes:
           The step actions will be skipped if 'temp-file' already exists
           If multiple hack methods are defined, the execution order is:
              replace, replace-file, patch, patch-file, append, append-file
           If 'file' and the path to 'file' does not exist
             it will be created then deleted unless 'keepChanges' is True
           The path to temp-file will not be created if it does not exist
    """

    REQUIRED_OPTIONS=['file']

    def __init__(self, env, log):
        CsmakeAspect.__init__(self, env, log)
        self.dirpath = None
        self.islink = False

    def _filterLinePad(self, options, intext):
        if 'line-pad' in options:
            replstr = '\n%s' % options['line-pad'].strip()
            return intext.replace(replstr,'\n')
        else:
            return intext

    def _replace(self, options):
        self.log.devdebug("Replacing: %s", self.targetFile)
        self.log.devdebug("  starting with: %s", options['replace'])
        replaceText = self._filterLinePad(options, options['replace'])
        self.log.devdebug("  after stripping: %s", replaceText)
        with file(self.targetFile, 'w') as openTarget:
            openTarget.write(replaceText)
        self.log.passed()
        return True

    def _replaceFile(self, options):
        shutil.copy(
            options['replace-file'],
            self.targetFile )
        self.log.passed()
        return True

    def _applyPatch(self, options):
        patchText = self._filterLinePad(options, options['patch'])
        self.log.devdebug("Applying patch: %s", patchText)
        process = subprocess.Popen(
            ['patch', self.targetFile],
            stdout=self.log.out(),
            stderr=self.log.err(),
            stdin=subprocess.PIPE )
        process.stdin.write(patchText)
        process.stdin.close()
        result = process.wait()
        if result != 0:
            self.log.error("File was not patched")
            self.log.failed()
            return False
        self.log.passed()
        return True

    def _applyPatchFile(self, options):
        patchFile = options['patch-file']
        result = subprocess.call(
            "patch %s < %s" % (
                self.targetFile,
                patchFile ),
            stdout=self.log.out(),
            stderr=self.log.err(),
            shell=True,
            executable='/bin/bash')
        if result != 0:
            self.log.error("File was not patched")
            self.log.failed()
            return False
        self.log.passed()
        return True

    def _append(self, options):
        appendText = self._filterLinePad(options, options['append'])
        with file(self.targetFile, 'a') as openTarget:
            openTarget.write(appendText)
        self.log.passed()
        return True

    def _appendFile(self, options):
        sourceFile = options['append-file']
        with file(self.targetFile, 'a') as openTarget:
            with file(sourceFile) as source:
                openTarget.writelines(source.readlines())
        self.log.passed()
        return True

    def _setFileMode(self, path, mode):
        result = subprocess.call(
            ['sudo', 'chmod', mode, path],
            stdout = self.log.out(),
            stderr = self.log.err() )
        if result != 0:
            self.log.error("Could not set mode (%s) on '%s'",
                mode,
                path )
            return False
        return True

    def _setPermissiveMode(self, path):
        oldMode = oct(os.stat(self.dirpath).st_mode & 0777)[1:]
        if not self._setFileMode(path, '777'):
            self.log.error("Could not set permissive move on '%s'",
                path )
            return None
        return oldMode

    def _removeCreatedPath(self):
        if len(self.createdParts) > 0:
            os.removedirs(
                os.path.join(
                    self.dirpath,
                    self.createdParts[0] ) )
            return True
        return False

    def _createPathTo(self, path):
        self.createdParts = []
        currentPath = path
        while currentPath != '' \
            and currentPath !='/' \
            and not os.path.exists(currentPath):
            currentPath, last = os.path.split(currentPath)
            self.createdParts.append(last)
        if currentPath == '':
            currentPath = '.'
        self.dirpath = currentPath
        self.realDirMode = self._setPermissiveMode(self.dirpath)
        self.createdParts.reverse()
        if len(self.createdParts) > 0:
            os.makedirs(
                os.path.join(
                    self.dirpath,
                    *self.createdParts) )
        return self.realDirMode is not None

    def _joinPointLookup(self, joinpoint, phase, options):
        self.log.devdebug("lookup aspect id: %s", self.log.params['AspectId'])
        self.log.devdebug("lookup options are: %s", str(options))
        self.log.devdebug("lookup aspect address: %s", hex(id(self)))
        if 'phases' in options:
            if options['phases'] == '*':
                phases = None
            else:
                phases = self._parseCommaAndNewlineList(options['phases'])
        else:
            phases = None

        if phases is None or phase in phases:
            if 'joinpoint' in options:
                myjoinpoint = options['joinpoint']
            else:
                myjoinpoint = 'start'
            if 'end-joinpoint' in options:
                myendjoinpoint = options['end-joinpoint']
            else:
                myendjoinpoint = 'end'
            if joinpoint == myjoinpoint:
                return self._hackFile
            elif joinpoint == myendjoinpoint:
                return self._unhackFile
            else:
                return None

    def _hackFile(self, phase, options, step, stepoptions):
        self.log.devdebug("aspect id: %s", self.log.params['AspectId'])
        self.log.devdebug("options are: %s", str(options))
        self.log.devdebug("aspect address: %s", hex(id(self)))
        self.targetFile = options['file']
        self.log.info("Modifying file '%s'", self.targetFile)
        try:
            self.isLink = os.path.exists(self.targetFile) \
                          and os.path.islink(self.targetFile)
        except:
            try:
                subprocess.check_call(
                    ['sudo', 'test', '-L', self.targetFile] )
                self.isLink = True
            except Exception as e:
                self.log.info("File '%s' is not a link or could not be queried", self.targetFile)
                self.log.debug("    Exception: %s: %s", e.__class__.__name__, str(e))
        if self.isLink:
            self.log.debug("'%s' is a link", self.targetFile)
            try:
                self.linkPath = os.readlink(self.targetFile)
            except:
                try:
                    self.linkPath = subprocess.check_output(
                        ['sudo', 'readlink', self.targetFile] ).strip()
                except Exception as e:
                    self.log.info("Link for '%s' could not be resolved", self.targetFile)
                    self.log.debug("    Exception: %s: %s", e.__class__.__name__, str(e))
                    self.isLink = False
            dirtolink, _ = os.path.split(self.targetFile)
            self.originalLink = self.linkPath
            self.linkPath = os.path.join(dirtolink, self.linkPath)
            if self.isLink:
                try:
                    os.unlink(self.targetFile)
                    os.copy(self.linkPath, self.targetFile)
                except:
                    try:
                        subprocess.call(
                            ['sudo', 'unlink', self.targetFile],
                            stdout = self.log.out(),
                            stderr = self.log.err())
                        subprocess.check_call(
                            ['sudo', 'cp', self.linkPath, self.targetFile],
                            stdout = self.log.out(),
                            stderr = self.log.err())
                    except Exception as e:
                        self.log.info("Link for '%s' could not be duplicated to an original file", self.targetFile)
                        self.log.debug("    Exception: %s: %s", e.__class__.__name__, str(e))
                        subprocess.call(
                            ['sudo', 'ln', '-s', self.linkPath, self.targetFile],
                            stdout = self.log.out(),
                            stderr = self.log.err())
                        self.isLink = False
        self.tempFile = self.targetFile + ".csmake-TemporaryFileHack-save"
        if 'temp-file' in options:
            self.tempFile = options['temp-file']
        self.log.info("Saving original file in '%s'", self.tempFile)
        if os.path.exists(self.tempFile):
            self.log.warning("The temporary original file already exists")
            self.log.warning("Not applying this change as it is assumed it is already applied")
            self.log.passed()
            return None

        self.dirpath = os.path.dirname(self.targetFile)
        if not self._createPathTo(self.dirpath):
            self.log.error("Create path to directory '%s' failed", self.dirpath)
            self.dirpath = None
            self.log.failed()
            return None

        #Save the mode string for the dir to restore it on exit

        if os.path.exists(self.targetFile):
            self.realFileMode = oct(os.stat(self.targetFile).st_mode & 0777)[1:]
            self._ensureDirectoryExists(self.tempFile)
            result = subprocess.call(
                ['sudo', 'chmod', '777', self.targetFile],
                stdout = self.log.out(),
                stderr = self.log.err() )
            if result != 0:
                self.log.warning("Attempting to change the mode of the target file failed")
            shutil.copy2(self.targetFile, self.tempFile)
        else:
            #Go ahead and touch the file
            with file(self.targetFile, 'w') as openTarget:
                openTarget.write('')
        if 'replace' in options:
            return self._replace(options)
        if 'replace-file' in options:
            return self._replaceFile(options)
        if 'patch' in options:
            return self._applyPatch(options)
        if 'patch-file' in options:
            return self._applyPatchFile(options)
        if 'append' in options:
            return self._append(options)
        if 'append-file' in options:
            return self._appendFile(options)
        self.log.error("A file hack aspect was specified, but no action option was given")
        self.log.failed()
        return False

    def _unhackFile(self, phase, options, step, stepoptions):
        self.log.devdebug("aspect id: %s", self.log.params['AspectId'])
        self.log.devdebug("options are: %s", str(options))
        self.log.devdebug("aspect address: %s", hex(id(self)))
        if self.dirpath is None:
            self.log.error("File was not hacked: %s", options['file'])
            self.log.failed()
            return False

        if 'keepChanges' in options and options['keepChanges'].strip() == 'True':
            self.log.info("Keeping modified file from aspect")
            self.log.passed()
            return True
        try:
            try:
                self.log.debug("Removing hacked file: %s", self.targetFile)
                os.remove(self.targetFile)
            except OSError as e:
                self.log.warning("Removal of hacked file failed: %s", repr(e))
            if os.path.exists(self.tempFile):
                try:
                    self.log.debug("Restoring original file from: %s   to: %s", self.tempFile, self.targetFile)
                    os.rename(self.tempFile, self.targetFile)
                except OSError as oserr:
                    self.log.debug("rename of file failed: (errno: %d)", oserr.errno)
                    subprocess.check_call(
                        ['sudo', 'mv', self.tempFile, self.targetFile],
                        stdout=self.log.out(),
                        stderr=self.log.err() )
                result = subprocess.call(
                    ['sudo', 'chmod', self.realFileMode, self.targetFile],
                    stdout=self.log.out(),
                    stderr=self.log.err() )
                if result != 0:
                    self.log.error('Could not reset mode for the target file - SECURITY')
                self._cleanEnsuredDirectory(self.tempFile)
            else:
                try:
                    self._removeCreatedPath()
                except Exception as e:
                    self.log.warning("Could not remove created path", repr(e))

            result = subprocess.call(
                ['sudo', 'chmod', self.realDirMode, self.dirpath],
                stdout=self.log.out(),
                stderr=self.log.err() )
            if result != 0:
                self.log.warning("Could not reset mode for the target file directory")

            if self.isLink:
                try:
                    os.unlink(self.targetFile)
                except:
                    try:
                        subprocess.check_call(
                            ['sudo', 'rm', '-f', self.targetFile],
                            stdout = self.log.out(),
                            stderr = self.log.err())
                    except Exception as e:
                        self.log.warning("Could not remove the link copy for '%s'", self.targetFile)
                        self.log.debug("    Exception: %s: %s", e.__class__.__name__, str(e))
                try:
                    os.symlink(self.originalLink, self.targetFile)
                except:
                    subprocess.call(
                        ['sudo', 'ln', '-s', self.originalLink, self.targetFile],
                        stdout = self.log.out(),
                        stderr = self.log.err())
            self.log.passed()
        except:
            self.log.exception("Failed to restore files")
            self.log.failed()
        return True

