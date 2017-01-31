# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.application.runner._runner}.
"""

from signal import SIGTERM
from io import BytesIO
import errno

from twisted.logger import (
    LogLevel, LogPublisher, LogBeginner,
    FileLogObserver, FilteringLogObserver, LogLevelFilterPredicate,
)
from twisted.test.proto_helpers import MemoryReactor

from ...runner import _runner
from .._exit import ExitStatus
from .._pidfile import PIDFile, NonePIDFile
from .._runner import Runner, RunnerOptions
from .test_pidfile import DummyFilePath

import twisted.trial.unittest



class RunnerTests(twisted.trial.unittest.TestCase):
    """
    Tests for L{Runner}.
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


    def test_runInOrder(self):
        """
        L{Runner.run} calls the expected methods in order.
        """
        runner = DummyRunner({})
        runner.run()

        self.assertEqual(
            runner.calledMethods,
            [
                "killIfRequested",
                "startLogging",
                "startReactor",
                "reactorExited",
            ]
        )


    def test_runUsesPIDFile(self):
        """
        L{Runner.run} uses the provided PID file.
        """
        pidFile = DummyPIDFile()

        runner = DummyRunner({RunnerOptions.pidFile: pidFile})

        self.assertFalse(pidFile.entered)
        self.assertFalse(pidFile.exited)

        runner.run()

        self.assertTrue(pidFile.entered)
        self.assertTrue(pidFile.exited)


    def test_runAlreadyRunning(self):
        """
        L{Runner.run} exits with L{ExitStatus.EX_USAGE} and the expected
        message if a process is already running that corresponds to the given
        PID file.
        """
        pidFile = PIDFile(DummyFilePath(self.pidFileContent))
        pidFile.isRunning = lambda: True

        runner = DummyRunner({RunnerOptions.pidFile: pidFile})
        runner.run()

        self.assertEqual(self.exit.status, ExitStatus.EX_CONFIG)
        self.assertEqual(self.exit.message, "Already running.")


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
        L{RunnerOptions.pidFile}, exits with L{ExitStatus.EX_USAGE} and
        the expected message, and also doesn't indiscriminately murder anyone.
        """
        runner = Runner({RunnerOptions.kill: True})
        runner.killIfRequested()

        self.assertEqual(self.kill.calls, [])
        self.assertEqual(self.exit.status, ExitStatus.EX_USAGE)
        self.assertEqual(self.exit.message, "No PID file specified.")


    def test_killRequestedWithPIDFile(self):
        """
        L{Runner.killIfRequested} with both L{RunnerOptions.kill} and
        L{RunnerOptions.pidFile} performs a targeted killing of the
        appropriate process.
        """
        pidFile = PIDFile(DummyFilePath(self.pidFileContent))
        runner = Runner({
            RunnerOptions.kill: True,
            RunnerOptions.pidFile: pidFile,
        })
        runner.killIfRequested()

        self.assertEqual(self.kill.calls, [(self.pid, SIGTERM)])
        self.assertEqual(self.exit.status, ExitStatus.EX_OK)
        self.assertIdentical(self.exit.message, None)


    def test_killRequestedWithPIDFileCantRead(self):
        """
        L{Runner.killIfRequested} with both L{RunnerOptions.kill} and a
        L{RunnerOptions.pidFile} that it can't read exits with
        L{ExitStatus.EX_IOERR}.
        """
        pidFile = PIDFile(DummyFilePath(None))

        def read():
            raise OSError(errno.EACCES, "Permission denied")

        pidFile.read = read

        runner = Runner({
            RunnerOptions.kill: True,
            RunnerOptions.pidFile: pidFile,
        })
        runner.killIfRequested()

        self.assertEqual(self.exit.status, ExitStatus.EX_IOERR)
        self.assertEqual(self.exit.message, "Unable to read PID file.")


    def test_killRequestedWithPIDFileEmpty(self):
        """
        L{Runner.killIfRequested} with both L{RunnerOptions.kill} and a
        L{RunnerOptions.pidFile} containing no value exits with
        L{ExitStatus.EX_DATAERR}.
        """
        pidFile = PIDFile(DummyFilePath(b""))
        runner = Runner({
            RunnerOptions.kill: True,
            RunnerOptions.pidFile: pidFile,
        })
        runner.killIfRequested()

        self.assertEqual(self.exit.status, ExitStatus.EX_DATAERR)
        self.assertEqual(self.exit.message, "Invalid PID file.")


    def test_killRequestedWithPIDFileNotAnInt(self):
        """
        L{Runner.killIfRequested} with both L{RunnerOptions.kill} and a
        L{RunnerOptions.pidFile} containing a non-integer value exits with
        L{ExitStatus.EX_DATAERR}.
        """
        pidFile = PIDFile(DummyFilePath(b"** totally not a number, dude **"))
        runner = Runner({
            RunnerOptions.kill: True,
            RunnerOptions.pidFile: pidFile,
        })
        runner.killIfRequested()

        self.assertEqual(self.exit.status, ExitStatus.EX_DATAERR)
        self.assertEqual(self.exit.message, "Invalid PID file.")


    def test_startLogging(self):
        """
        L{Runner.startLogging} sets up a filtering observer with a log level
        predicate set to the given log level that contains a file observer of
        the given type which writes to the given file.
        """
        logFile = object()

        # Patch the log beginner so that we don't try to start the already
        # running (started by trial) logging system.

        class LogBeginner(object):
            def beginLoggingTo(self, observers):
                LogBeginner.observers = observers

        self.patch(_runner, "globalLogBeginner", LogBeginner())

        # Patch FilteringLogObserver so we can capture its arguments

        class MockFilteringLogObserver(FilteringLogObserver):
            def __init__(
                self, observer, predicates,
                negativeObserver=lambda event: None
            ):
                MockFilteringLogObserver.observer = observer
                MockFilteringLogObserver.predicates = predicates
                FilteringLogObserver.__init__(
                    self, observer, predicates, negativeObserver
                )

        self.patch(_runner, "FilteringLogObserver", MockFilteringLogObserver)

        # Patch FileLogObserver so we can capture its arguments

        class MockFileLogObserver(FileLogObserver):
            def __init__(self, outFile):
                MockFileLogObserver.outFile = outFile
                FileLogObserver.__init__(self, outFile, str)

        # Start logging
        runner = Runner({
            RunnerOptions.logFile: logFile,
            RunnerOptions.fileLogObserverFactory: MockFileLogObserver,
            RunnerOptions.defaultLogLevel: LogLevel.critical,
        })
        runner.startLogging()

        # Check for a filtering observer
        self.assertEqual(len(LogBeginner.observers), 1)
        self.assertIsInstance(LogBeginner.observers[0], FilteringLogObserver)

        # Check log level predicate with the correct default log level
        self.assertEqual(len(MockFilteringLogObserver.predicates), 1)
        self.assertIsInstance(
            MockFilteringLogObserver.predicates[0],
            LogLevelFilterPredicate
        )
        self.assertIdentical(
            MockFilteringLogObserver.predicates[0].defaultLogLevel,
            LogLevel.critical
        )

        # Check for a file observer attached to the filtering observer
        self.assertIsInstance(
            MockFilteringLogObserver.observer, MockFileLogObserver
        )

        # Check for the file we gave it
        self.assertIdentical(
            MockFilteringLogObserver.observer.outFile, logFile
        )


    def test_startReactorWithoutReactor(self):
        """
        L{Runner.startReactor} without L{RunnerOptions.reactor} runs the default
        reactor.
        """
        # Patch defaultReactor
        reactor = MemoryReactor()
        self.patch(_runner, "defaultReactor", reactor)

        runner = Runner({})
        runner.startReactor()

        self.assertTrue(reactor.hasInstalled)
        self.assertTrue(reactor.hasRun)


    def test_startReactorWithReactor(self):
        """
        L{Runner.startReactor} with L{RunnerOptions.reactor} runs that reactor.
        """
        reactor = MemoryReactor()
        runner = Runner({RunnerOptions.reactor: reactor})
        runner.startReactor()

        self.assertTrue(reactor.hasRun)


    def test_startReactorWithWhenRunning(self):
        """
        L{Runner.startReactor} with L{RunnerOptions.whenRunning} ensures that
        the given callable is called with the runner's options when the reactor
        is running.
        """
        optionsSeen = []

        def txmain(options):
            optionsSeen.append(options)

        options = {
            RunnerOptions.reactor: MemoryReactor(),
            RunnerOptions.whenRunning: txmain,
        }
        runner = Runner(options)
        runner.startReactor()

        self.assertEqual(len(optionsSeen), 1)
        self.assertIdentical(optionsSeen[0], options)


    def test_whenRunningWithWhenRunning(self):
        """
        L{Runner.whenRunning} with L{RunnerOptions.whenRunning} calls the given
        callable with the runner's options.
        """
        optionsSeen = []

        def txmain(options):
            optionsSeen.append(options)

        options = {RunnerOptions.whenRunning: txmain}
        runner = Runner(options)
        runner.whenRunning()

        self.assertEqual(len(optionsSeen), 1)
        self.assertIdentical(optionsSeen[0], options)


    def test_reactorExitedWithReactorExited(self):
        """
        L{Runner.reactorExited} with L{RunnerOptions.reactorExited} calls the
        given callable with the runner's options.
        """
        optionsSeen = []

        def exited(options):
            optionsSeen.append(options)

        options = {RunnerOptions.reactorExited: exited}
        runner = Runner(options)
        runner.reactorExited()

        self.assertEqual(len(optionsSeen), 1)
        self.assertIdentical(optionsSeen[0], options)



class DummyRunner(Runner):
    """
    Stub for L{Runner}.

    Keep track of calls to some methods without actually doing anything.
    """
    def __init__(self, *args, **kwargs):
        Runner.__init__(self, *args, **kwargs)

        self.calledMethods = []


    def killIfRequested(self):
        self.calledMethods.append("killIfRequested")


    def startLogging(self):
        self.calledMethods.append("startLogging")


    def startReactor(self):
        self.calledMethods.append("startReactor")


    def reactorExited(self):
        self.calledMethods.append("reactorExited")



class DummyPIDFile(NonePIDFile):
    """
    Stub for L{PIDFile}.

    Tracks context manager entry/exit without doing anything.
    """
    def __init__(self):
        NonePIDFile.__init__(self)

        self.entered = False
        self.exited  = False


    def __enter__(self):
        self.entered = True
        return self


    def __exit__(self, excType, excValue, traceback):
        self.exited  = True



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
        """
        Do nothing.

        @param args: ignored.
        @param kwargs: ignored.
        """
