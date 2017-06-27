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
import shutil
import os.path
import subprocess
import fcntl
import threading

class LockSection(CsmakeAspect):
    """Purpose: Create a critical section across builds on a single system
       Type: Aspect   Library: csmake-swak
       Description:
           This aspect will lock for an entire execution of a section
           Locks are reenterant
           Locks may be a "reader" lock or an "exclusive" lock
           NOTE: A reader lock that reenters and attempts to become
                 exclusive will cause a failure, the proper pattern is
                 to use two different tags.
       Phases: Default - *, may be determined by 'phases' options
       Joinpoints: start, end
       Options:
           tag - The tag/label to use for the lock
           path - (OPTIONAL) Path to use to create file locks
                 Default is /var/lock/csmake
           phases - (OPTIONAL) Select the phases on which to lock
           read - (OPTIONAL) When 'True' the lock will just be a read lock
                 Default is an exclusive lock
    """

    REQUIRED_OPTIONS=['tag']

    processLocks = {}
    locktableLock = threading.Lock()

    def _onExit(self):
        self._cleanUpLock(self.path, self.tag, self.flock)

    def _cleanUpLock(self, path, tag, flock):
        if self.flockPath is None:
            self.log.info("cleaning up lock '%s' before it was locked", tag)
            self.log.devdebug(str(id(self)))
            return
        processLock = LockSection.processLocks[self.flockPath]
        self.log.devdebug("$#@$#@ Release count check: %s: %s(%d), %s(%s)", tag, self.flockPath, processLock[2], hex(id(self)), hex(id(processLock[0])))
        if processLock[2] > 1:
            processLock[2] -= 1
            processLock[0].release()
            return
        try:
            if self.watchdogevent is not None:
                self.watchdogevent.set()
                if self.watchdog is not None:
                    self.watchdog.join()
                self.watchdog = None
            if self.flock is None:
                self._unregisterOnExitCallback("_onExit")
                return False
            flockPath = os.path.join(path, tag)
            fcntl.flock(flock, fcntl.LOCK_UN)
        finally:
            try:
                self.flock.close()
            except:
                self.log.exception("Could not close lock file: %s", self.flockPath)
            self.flock = None
            self.log.info("UNLOCKED   Tag: %s  In: %s", tag, path)
            self._unregisterOnExitCallback("_onExit")
            processLock[1] = None
            processLock[2] -= 1
            self.log.devdebug("$#@$#@ Releasing: %s: %s(%d), %s(%s)", tag, self.flockPath, processLock[2], hex(id(self)), hex(id(processLock[0])))
            processLock[0].release()
        return True

    def _lockSection(self, path, tag):
        self.flockPath = os.path.join(path, tag)
        LockSection.locktableLock.acquire()
        try:
            if self.flockPath not in LockSection.processLocks:
                LockSection.processLocks[self.flockPath] = [
                    threading.RLock(),
                    None,
                    0
                ]
        finally:
            LockSection.locktableLock.release()
        processLock = LockSection.processLocks[self.flockPath]
        self.log.devdebug("$#@$#@ Acquire: %s: %s(%d), %s(%s)", tag, self.flockPath, processLock[2], hex(id(self)), hex(id(processLock[0])))
        self.log.devdebug("$#@$#@     table: %s", hex(id(LockSection.processLocks)))
        processLock[0].acquire()
        processLock[2] += 1
        self.log.devdebug("$#@$#@     success: %s: %s(%d), %s(%s)", tag, self.flockPath, processLock[2], hex(id(self)), hex(id(processLock[0])))
        if processLock[2] > 1:
            if processLock[1] == fcntl.LOCK_SH \
                and self.locktype == fcntl.LOCK_EX:
                self.log.error(
                    "A read lock '%s', attempted to be promoted",
                    tag )
                processLock[2] -= 1
                processLock[0].release()
                raise ValueError("A read lock cannot be promoted to exclusive")
            return
        processLock[1] = self.locktype
        if not os.path.exists(path):
            os.makedirs(path)
        try:
            os.chmod(path, 0777)
        except:
            self.log.exception("Attempting lock chmod on lock dir")
        self.flock = open(self.flockPath, 'a')
        try:
            os.chmod(self.flockPath, 0666)
        except:
            self.log.exception("Attempting lock chmod on lock")
        self.log.info("___ attempting lock   Tag: %s  In: %s", tag, path)
        self.log.out()
        fcntl.flock(self.flock, self.locktype)
        self.log.info("LOCKED   Tag: %s  In: %s", tag, path)
        self._registerOnExitCallback("_onExit")

    def _joinPointLookup(self, joinpoint, phase, options):
        if 'phases' in options:
            if options['phases'] == '*':
                phases = None
            else:
                phases = self._parseCommaAndNewlineList(options['phases'])
        else:
            phases = None

        if phases is None or phase in phases:
            if joinpoint == 'start':
                return self._lock
            elif joinpoint == 'end':
                return self._unlock
            else:
                return None


    def _lock(self, phase, options, step, stepoptions):
        self.flock = None
        self.flockPath = None
        self.options = options
        self.watchdogevent = None
        self.watchdog = None
        self.locktype = fcntl.LOCK_EX
        if 'read' in self.options:
            if self.options['read'] == 'True':
                self.locktype = fcntl.LOCK_SH
        self.path = "/var/lock/csmake"
        if 'path' in self.options:
            self.path = self.options['path']
        self.tag = self.options['tag']

        self._lockSection(self.path, self.tag)
        self.log.passed()
        return self.tag

    def _unlock(self, phase, options, step, stepoptions):
        self._onExit()
        self.log.passed()
        return self.tag
