# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.application.runner._runner}.
"""

from signal import SIGTERM
from io import BytesIO

from twisted.logger import LogPublisher, LogBeginner

from ...runner import _runner
from .._exit import ExitStatus
from .._runner import Runner, RunnerOptions

import twisted.trial.unittest



class CommandTests(twisted.trial.unittest.TestCase):
    """
    Tests for L{Command}.
    """

    def setUp(self):
        # Patch exit and kill so we can capture usage and prevent actual exits
        # and kills.

        self.exit = DummyExit()
        self.kill = DummyKill()

        self.patch(_runner, "exit", self.exit)
        self.patch(_runner, "kill", self.kill)

        # Patch getpid so we get a known result

        self.pid = 1337
        self.pidFileContent = u"{}\n".format(self.pid).encode("utf-8")
        self.patch(_runner, "getpid", lambda: self.pid)

        # Patch globalLogBeginner so that we aren't trying to install multiple
        # global log observers.

        self.stdout = BytesIO()
        self.stderr = BytesIO()
        self.stdio = DummyStandardIO(self.stdout, self.stderr)
        self.warnings = DummyWarningsModule()

        self.globalLogPublisher = LogPublisher()
        self.globalLogBeginner = LogBeginner(
            self.globalLogPublisher,
            self.stdio.stderr, self.stdio,
            self.warnings,
        )

        self.patch(_runner, "stderr", self.stderr)
        self.patch(_runner, "globalLogBeginner", self.globalLogBeginner)


    def test_execute(self):
        """
        L{Runner.execute} calls the documented methods in order.
        """
        called = []

        methodNames = [
            "killIfRequested",
            "writePIDFile",
            "startLogging",
            "startReactor",
            "reactorExited",
            "removePIDFile",
        ]

        for name in methodNames:
            self.patch(
                Runner, name, lambda self, name=name: called.append(name)
            )

        runner = Runner({})
        runner.execute()

        self.assertEqual(called, methodNames)


    def test_killNotRequested(self):
        """
        L{Runner.killIfRequested} without L{RunnerOptions.kill} doesn't exit
        and doesn't indiscriminately murder anyone.
        """
        runner = Runner({})
        runner.killIfRequested()

        self.assertEqual(self.kill.calls, [])
        self.assertFalse(self.exit.exited)


    def test_killRequestedWithoutPIDFile(self):
        """
        L{Runner.killIfRequested} with L{RunnerOptions.kill} but without
        L{RunnerOptions.pidFilePath}, exits with L{ExitStatus.EX_USAGE} and
        the expected message, and also doesn't indiscriminately murder anyone.
        """
        runner = Runner({RunnerOptions.kill: True})
        runner.killIfRequested()

        self.assertEqual(self.kill.calls, [])
        self.assertEqual(self.exit.status, ExitStatus.EX_USAGE)
        self.assertEqual(self.exit.message, "No PID file specified")


    def test_killRequestedWithPIDFile(self):
        """
        L{Runner.killIfRequested} with both L{RunnerOptions.kill} and
        L{RunnerOptions.pidFilePath} performs a targeted killing of the
        appropriate process.
        """
        pidFilePath = DummyFilePath(self.pidFileContent)
        runner = Runner({
            RunnerOptions.kill: True,
            RunnerOptions.pidFilePath: pidFilePath,
        })
        runner.killIfRequested()

        self.assertEqual(self.kill.calls, [(self.pid, SIGTERM)])
        self.assertEqual(self.exit.status, ExitStatus.EX_OK)
        self.assertIdentical(self.exit.message, None)


    def test_writePIDFileWithPIDFile(self):
        """
        L{Runner.writePIDFile} with L{RunnerOptions.pidFilePath} writes a PID
        file.
        """
        pidFilePath = DummyFilePath()
        runner = Runner({
            RunnerOptions.pidFilePath: pidFilePath,
        })
        runner.writePIDFile()

        self.assertEqual(pidFilePath.getContent(), self.pidFileContent)


    def test_removePIDFileWithPIDFile(self):
        """
        L{Runner.removePIDFile} with L{RunnerOptions.pidFilePath} removes the
        PID file.
        """
        pidFilePath = DummyFilePath()
        runner = Runner({
            RunnerOptions.pidFilePath: pidFilePath,
        })
        runner.removePIDFile()

        self.assertFalse(pidFilePath.exists())


    def test_startLogging(self):
        raise NotImplementedError()
    test_startLogging.todo = "unimplemented"


    def test_startReactor(self):
        raise NotImplementedError()
    test_startReactor.todo = "unimplemented"


    def test_whenRunning(self):
        raise NotImplementedError()
    test_whenRunning.todo = "unimplemented"


    def test_reactorExited(self):
        raise NotImplementedError()
    test_reactorExited.todo = "unimplemented"



class DummyExit(object):
    """
    Stub for L{exit} that remembers whether it's been called and, if it has,
    what arguments it was given.
    """

    def __init__(self):
        self.exited = False


    def __call__(self, status, message=None):
        assert not self.exited

        self.status  = status
        self.message = message
        self.exited  = True



class DummyKill(object):
    """
    Stub for L{os.kill} that remembers whether it's been called and, if it has,
    what arguments it was given.
    """

    def __init__(self):
        self.calls = []


    def __call__(self, pid, sig):
        self.calls.append((pid, sig))



class DummyFilePath(object):
    """
    Stub for L{twisted.python.filepath.FilePath} which returns a stream
    containing the given data when opened.
    """

    def __init__(self, content=b""):
        self.setContent(content)


    def open(self, mode="r"):
        return BytesIO(self._content)


    def setContent(self, content):
        self._exits = True
        self._content = content


    def getContent(self):
        return self._content


    def remove(self):
        self._exits = False


    def exists(self):
        return self._exits



class DummyStandardIO(object):
    """
    Stub for L{sys} which provides L{BytesIO} streams as stdout and stderr.
    """

    def __init__(self, stdout, stderr):
        self.stdout = stdout
        self.stderr = stderr



class DummyWarningsModule(object):
    """
    Stub for L{warnings} which provides a C{showwarning} method that is a no-op.
    """

    def showwarning(*args, **kwargs):
        pass
