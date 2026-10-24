# <copyright>
# (c) Copyright 2026 Autumn Patterson
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
"""Just enough of a csmake engine/environment/log to construct a real module.

CsmakeModule.__init__ only needs ``env.engine`` (with ``settings``) and
``env.metadata.getCurrent()``, so the modules under test are instantiated
for real; only the surrounding engine is faked.

Also helpers for dropping fake executables first on PATH, so the code under
test runs real subprocesses (real pipes, real bytes) against a stand-in tool.
"""
import os
import shlex
import stat
import subprocess
import sys
import types
from unittest import mock


class FakeLog(object):
    """Records messages; out()/err() are valid subprocess stdout/stderr."""

    LEVELS = ('devdebug', 'debug', 'info', 'warning', 'error', 'exception')

    def __init__(self):
        self.records = []
        self.result = None
        self.params = {'AspectId': 'test-aspect'}
        for level in self.LEVELS:
            setattr(self, level, self._recorder(level))

    def _recorder(self, level):
        def record(msg, *args, **kwargs):
            try:
                msg = msg % args
            except (TypeError, ValueError):
                pass
            self.records.append((level, msg))
        return record

    def messages(self, level):
        return [m for l, m in self.records if l == level]

    def passed(self):
        self.result = 'passed'

    def failed(self):
        self.result = 'failed'

    def out(self):
        return subprocess.DEVNULL

    err = out

    def chatStartOnExitCallback(self, method):
        pass

    def chatEndOnExitCallback(self, method):
        pass


class FakeEngine(object):
    def __init__(self):
        self.settings = {'debug': False, 'verbose': False, 'quiet': True}
        self.callbacks = {}
        self._nextId = 1

    def registerBuildExitCallback(self, callback):
        regid = self._nextId
        self._nextId += 1
        self.callbacks[regid] = callback
        return regid

    def unregisterBuildExitCallback(self, regid):
        self.callbacks.pop(regid, None)


class FakeMetadata(object):
    """The slice of csmake metadata that the versioning modules touch."""

    def __init__(self):
        self.version = {}
        self.versionkeys = []

    def _addVersionString(self, versionkey, value):
        self.version[versionkey] = value
        self.versionkeys.append(versionkey)


class FakeEnv(object):
    """Stands in for CsmakeCore.Environment.Environment."""

    def __init__(self, results_dir, metadata=None):
        self.engine = FakeEngine()
        self.env = {'RESULTS': results_dir}
        self._metadata = metadata
        self.metadata = types.SimpleNamespace(getCurrent=lambda: self._metadata)

    def addTransPhase(self, key, value):
        self.env[key] = value


def write_executable(bindir, name, text):
    path = os.path.join(bindir, name)
    with open(path, 'w') as f:
        f.write(text)
    os.chmod(path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP
             | stat.S_IROTH | stat.S_IXOTH)
    return path


def write_python_executable(bindir, name, source):
    """A fake command implemented in Python, run with the current interpreter."""
    impl = write_executable(bindir, name + '.impl.py', source)
    return write_executable(
        bindir, name,
        '#!/bin/sh\nexec %s %s "$@"\n' % (
            shlex.quote(sys.executable), shlex.quote(impl)))


def path_first(bindir):
    """Patch os.environ so executables in ``bindir`` win over real ones."""
    return mock.patch.dict(
        os.environ, {'PATH': bindir + os.pathsep + os.environ.get('PATH', '')})
