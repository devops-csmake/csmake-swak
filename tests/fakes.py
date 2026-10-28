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

FakeSubprocess scripts the external-process boundary (Popen / call /
check_call / check_output).  It honours the real API's type contract: output
is ``bytes`` unless the caller asked for text (``universal_newlines=True``,
``text=True`` or ``encoding=``), and every call's arguments are recorded, so
a module that forgets to ask for text sees bytes exactly as it would for real.
"""
import subprocess
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

    def skipped(self):
        self.result = 'skipped'

    def out(self):
        return subprocess.DEVNULL

    err = out

    def chatStartOnExitCallback(self, method):
        pass

    def chatEndOnExitCallback(self, method):
        pass


class FakeEngine(object):
    def __init__(self, phase='build'):
        self.settings = {'debug': False, 'verbose': False, 'quiet': True}
        self.phase = phase
        self.steps = {}
        self.launched = []
        self.callbacks = {}
        self._nextId = 1

    def getPhase(self):
        return self.phase

    def launchStep(self, name, phase):
        """Run a named step: ``self.steps`` maps name -> result (or None)."""
        self.launched.append((name, phase))
        return self.steps.get(name)

    def registerBuildExitCallback(self, callback):
        regid = self._nextId
        self._nextId += 1
        self.callbacks[regid] = callback
        return regid

    def unregisterBuildExitCallback(self, regid):
        self.callbacks.pop(regid, None)


class FakeStepResult(object):
    """What engine.launchStep returns for a section that ran."""

    def __init__(self, value, passed=True):
        self._value = value
        self._passed = passed

    def _didPass(self):
        return self._passed

    def _getReturnValue(self, phase):
        return self._value


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

    def __init__(self, results_dir='/nonexistent-results', metadata=None,
                 phase='build'):
        self.engine = FakeEngine(phase)
        self.env = {'RESULTS': results_dir}
        self.transPhase = {}
        self._metadata = metadata
        self.metadata = types.SimpleNamespace(getCurrent=lambda: self._metadata)

    def addTransPhase(self, key, value):
        self.transPhase[key] = value
        self.env[key] = value

    def doSubstitutions(self, text):
        return text


class FakeFlowControl(object):
    """Records the votes / overrides an aspect casts."""

    def __init__(self):
        self.votes = []
        self.overrides = []

    def vote(self, issue, vote, voter):
        self.votes.append((issue, vote))

    def override(self, issue, vote, voter):
        self.overrides.append((issue, vote))


# --------------------------------------------------------------------------
# The subprocess boundary
# --------------------------------------------------------------------------

def is_text_mode(kwargs):
    return bool(kwargs.get('universal_newlines') or kwargs.get('text')
                or kwargs.get('encoding') or kwargs.get('errors'))


def render_output(data, kwargs):
    """What a real subprocess hands back: bytes, or str when text was asked."""
    if data is None or not is_text_mode(kwargs):
        return data
    text = data.decode(kwargs.get('encoding') or 'utf-8',
                       kwargs.get('errors') or 'strict')
    return text.replace('\r\n', '\n').replace('\r', '\n')


def joined(args):
    return args if isinstance(args, str) else ' '.join(str(a) for a in args)


class Call(object):
    def __init__(self, kind, args, kwargs):
        self.kind = kind
        self.args = args
        self.kwargs = kwargs

    @property
    def command(self):
        return joined(self.args)

    def __repr__(self):
        kwargs = dict(self.kwargs)
        if 'env' in kwargs:
            kwargs['env'] = '<%d variables>' % len(kwargs['env'])
        return '<%s %r %r>' % (self.kind, self.args, kwargs)


class _Result(object):
    def __init__(self, stdout, stderr, returncode, raises, effect, process=None):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.raises = raises
        self.effect = effect
        self.process = process


class FakeStdin(object):
    """A Popen stdin pipe: binary unless the process was opened in text mode."""

    def __init__(self, text):
        self.text = text
        self.chunks = []
        self.closed = False

    def write(self, data):
        if self.closed:
            raise ValueError('write to closed file')
        if self.text and not isinstance(data, str):
            raise TypeError('write() argument must be str, not %s'
                            % type(data).__name__)
        if not self.text and not isinstance(data, (bytes, bytearray)):
            raise TypeError("a bytes-like object is required, not '%s'"
                            % type(data).__name__)
        self.chunks.append(data)
        return len(data)

    def close(self):
        self.closed = True

    def flush(self):
        pass

    @property
    def written(self):
        return (u'' if self.text else b'').join(self.chunks)


class FakeProcess(object):
    def __init__(self, result, kwargs):
        self._result = result
        self._kwargs = kwargs
        self.returncode = None
        self.pid = 4242
        self.stdin = (FakeStdin(is_text_mode(kwargs))
                      if kwargs.get('stdin') == subprocess.PIPE else None)

    def communicate(self, input=None, timeout=None):
        if input is not None:
            self.stdin.write(input)
        self.returncode = self._result.returncode
        out = (render_output(self._result.stdout, self._kwargs)
               if self._kwargs.get('stdout') == subprocess.PIPE else None)
        err = (render_output(self._result.stderr, self._kwargs)
               if self._kwargs.get('stderr') == subprocess.PIPE else None)
        return out, err

    def wait(self, timeout=None):
        self.returncode = self._result.returncode
        return self.returncode

    def poll(self):
        return self.returncode


class FakeSubprocess(object):
    """Scripted subprocess.Popen / call / check_call / check_output.

    ``on(match, ...)`` scripts a response; the most recent matching entry wins,
    so a test can override a default set up in setUp.
    ``match`` is a substring of the space-joined command, a list that must
    equal the start of the argv, or a callable(args, kwargs).  A call with no
    scripted response is recorded in ``unscripted`` (which fails the test at
    cleanup) and raises AssertionError.
    """

    NAMES = ('Popen', 'call', 'check_call', 'check_output')

    def __init__(self):
        self.calls = []
        self.processes = []
        self.unscripted = []
        self._script = []

    def on(self, match, stdout=b'', stderr=b'', returncode=0, raises=None,
           effect=None, process=None):
        """Script a response.

        ``effect(args, kwargs)`` may return an int to override returncode.
        ``process(args, kwargs)`` supplies a custom Popen object.
        """
        self._script.append(
            (match, _Result(stdout, stderr, returncode, raises, effect, process)))
        return self

    def install(self, testcase):
        for name in self.NAMES:
            patcher = mock.patch.object(
                subprocess, name, getattr(self, '_' + name))
            patcher.start()
            testcase.addCleanup(patcher.stop)
        testcase.addCleanup(
            lambda: testcase.assertEqual(
                [], self.unscripted, 'unscripted subprocess calls'))
        return self

    def commands(self, kind=None):
        return [c.command for c in self.calls if kind in (None, c.kind)]

    def _matches(self, match, args, kwargs):
        if callable(match):
            return match(args, kwargs)
        if isinstance(match, str):
            return match in joined(args)
        return list(args)[:len(match)] == list(match)

    def _lookup(self, kind, args, kwargs):
        self.calls.append(Call(kind, args, kwargs))
        for match, result in reversed(self._script):
            if self._matches(match, args, kwargs):
                if result.raises is not None:
                    raise result.raises
                if result.effect is not None:
                    override = result.effect(args, kwargs)
                    if override is not None:
                        result = _Result(result.stdout, result.stderr, override,
                                         None, None, result.process)
                return result
        self.unscripted.append(self.calls[-1])
        raise AssertionError('unscripted subprocess.%s: %r' % (kind, args))

    def _Popen(self, args, **kwargs):
        result = self._lookup('Popen', args, kwargs)
        process = (result.process(args, kwargs) if result.process is not None
                   else FakeProcess(result, kwargs))
        self.processes.append(process)
        return process

    def _call(self, args, **kwargs):
        return self._lookup('call', args, kwargs).returncode

    def _check_call(self, args, **kwargs):
        result = self._lookup('check_call', args, kwargs)
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, args)
        return 0

    def _check_output(self, args, **kwargs):
        result = self._lookup('check_output', args, kwargs)
        output = render_output(result.stdout, kwargs)
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, args, output=output)
        return output
