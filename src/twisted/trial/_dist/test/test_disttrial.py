# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.trial._dist.disttrial}.
"""

from __future__ import annotations

import os
import sys
from functools import partial
from io import StringIO
from typing import List

from zope.interface import implementer, verify

from attrs import Factory, define, field
from hamcrest import assert_that, equal_to, has_length, none

from twisted.internet import interfaces
from twisted.internet.defer import Deferred, succeed
from twisted.internet.protocol import ProcessProtocol, Protocol
from twisted.python.failure import Failure
from twisted.python.filepath import FilePath
from twisted.python.lockfile import FilesystemLock
from twisted.test.proto_helpers import MemoryReactorClock
from twisted.trial._dist.distreporter import DistReporter
from twisted.trial._dist.disttrial import DistTrialRunner, WorkerPool, WorkerPoolConfig
from twisted.trial._dist.functional import countingCalls, iterateWhile, sequence, void
from twisted.trial._dist.worker import LocalWorker, WorkerAction
from twisted.trial.reporter import (
    Reporter,
    TestResult,
    TreeReporter,
    UncleanWarningsReporterWrapper,
)
from twisted.trial.runner import ErrorHolder, TrialSuite
from twisted.trial.unittest import SynchronousTestCase, TestCase
from ...test import erroneous


class FakeTransport:
    """
    A simple fake process transport.
    """

    def writeToChild(self, fd, data):
        """
        Ignore write calls.
        """


@implementer(interfaces.IReactorProcess)
class CountingReactor(MemoryReactorClock):
    """
    A fake reactor that counts the calls to L{IReactorCore.run},
    L{IReactorCore.stop}, and L{IReactorProcess.spawnProcess}.
    """

    spawnCount = 0
    stopCount = 0
    runCount = 0

    def __init__(self, workers):
        MemoryReactorClock.__init__(self)
        self._workers = workers

    def spawnProcess(
        self,
        workerProto,
        executable,
        args=(),
        env={},
        path=None,
        uid=None,
        gid=None,
        usePTY=0,
        childFDs=None,
    ):
        """
        See L{IReactorProcess.spawnProcess}.

        @param workerProto: See L{IReactorProcess.spawnProcess}.
        @param args: See L{IReactorProcess.spawnProcess}.
        @param kwargs: See L{IReactorProcess.spawnProcess}.
        """
        self._workers.append(workerProto)
        workerProto.makeConnection(FakeTransport())
        self.spawnCount += 1

    def stop(self):
        """
        See L{IReactorCore.stop}.
        """
        MemoryReactorClock.stop(self)
        self.stopCount += 1

    def run(self):
        """
        See L{IReactorCore.run}.
        """
        self.runCount += 1

        # The same as IReactorCore.run, except no stop.
        self.running = True
        self.hasRun = True

        for f, args, kwargs in self.whenRunningHooks:
            f(*args, **kwargs)


class CountingReactorTests(SynchronousTestCase):
    """
    Tests for L{CountingReactor}.
    """

    def setUp(self):
        self.workers = []
        self.reactor = CountingReactor(self.workers)

    def test_providesIReactorProcess(self):
        """
        L{CountingReactor} instances provide L{IReactorProcess}.
        """
        verify.verifyObject(interfaces.IReactorProcess, self.reactor)

    def test_spawnProcess(self):
        """
        The process protocol for a spawned process is connected to a
        transport and appended onto the provided C{workers} list, and
        the reactor's C{spawnCount} increased.
        """
        self.assertFalse(self.reactor.spawnCount)

        proto = Protocol()
        for count in [1, 2]:
            self.reactor.spawnProcess(proto, sys.executable, args=[sys.executable])
            self.assertTrue(proto.transport)
            self.assertEqual(self.workers, [proto] * count)
            self.assertEqual(self.reactor.spawnCount, count)

    def test_stop(self):
        """
        Stopping the reactor increments its C{stopCount}
        """
        self.assertFalse(self.reactor.stopCount)
        for count in [1, 2]:
            self.reactor.stop()
            self.assertEqual(self.reactor.stopCount, count)

    def test_run(self):
        """
        Running the reactor increments its C{runCount}, does not imply
        C{stop}, and calls L{IReactorCore.callWhenRunning} hooks.
        """
        self.assertFalse(self.reactor.runCount)

        whenRunningCalls = []
        self.reactor.callWhenRunning(whenRunningCalls.append, None)

        for count in [1, 2]:
            self.reactor.run()
            self.assertEqual(self.reactor.runCount, count)
            self.assertEqual(self.reactor.stopCount, 0)
            self.assertEqual(len(whenRunningCalls), count)


class WorkerPoolTests(TestCase):
    """
    Tests for L{WorkerPool}.
    """

    def setUp(self):
        self.parent = FilePath(self.mktemp())
        self.workingDirectory = self.parent.child("_trial_temp")
        self.config = WorkerPoolConfig(
            numWorkers=4,
            workingDirectory=self.workingDirectory,
            workerArguments=[],
            logFile="out.log",
        )
        self.pool = WorkerPool(self.config)

    def test_createLocalWorkers(self):
        """
        C{createLocalWorkers} iterates the list of protocols and create one
        L{LocalWorker} for each.
        """
        protocols = [object() for x in range(4)]
        workers = self.pool.createLocalWorkers(protocols, FilePath("path"), StringIO())
        for s in workers:
            self.assertIsInstance(s, LocalWorker)
        self.assertEqual(4, len(workers))

    def test_launchWorkerProcesses(self):
        """
        Given a C{spawnProcess} function, C{launchWorkerProcess} launches a
        python process with an existing path as its argument.
        """
        protocols = [ProcessProtocol() for i in range(4)]
        arguments = []
        environment = {}

        def fakeSpawnProcess(
            processProtocol,
            executable,
            args=(),
            env={},
            path=None,
            uid=None,
            gid=None,
            usePTY=0,
            childFDs=None,
        ):
            arguments.append(executable)
            arguments.extend(args)
            environment.update(env)

        self.pool._launchWorkerProcesses(fakeSpawnProcess, protocols, ["foo"])
        self.assertEqual(arguments[0], arguments[1])
        self.assertTrue(os.path.exists(arguments[2]))
        self.assertEqual("foo", arguments[3])
        # The child process runs with PYTHONPATH set to exactly the parent's
        # import search path so that the child has a good chance of finding
        # the same source files the parent would have found.
        self.assertEqual(os.pathsep.join(sys.path), environment["PYTHONPATH"])

    def test_run(self):
        """
        C{run} dispatches the given action to each of its workers exactly once.
        """
        # Make sure the parent of the working directory exists so
        # manage a lock in it.
        self.parent.makedirs()

        workers = []
        starting = self.pool.start(CountingReactor([]))
        started = self.successResultOf(starting)
        running = started.run(lambda w: succeed(workers.append(w)))
        self.successResultOf(running)
        assert_that(workers, has_length(self.config.numWorkers))

    def test_runUsedDirectory(self):
        """
        L{WorkerPool.start} checks if the test directory is already locked, and if
        it is generates a name based on it.
        """
        # Make sure the parent of the working directory exists so we can
        # manage a lock in it.
        self.parent.makedirs()

        # Lock the directory the runner will expect to use.
        lock = FilesystemLock(self.workingDirectory.path + ".lock")
        self.assertTrue(lock.lock())
        self.addCleanup(lock.unlock)

        # Start up the pool
        fakeReactor = CountingReactor([])
        started = self.successResultOf(self.pool.start(fakeReactor))

        # Verify it took a nearby directory instead.
        self.assertEqual(
            started.workingDirectory,
            self.workingDirectory.sibling("_trial_temp-1"),
        )


class DistTrialRunnerTests(TestCase):
    """
    Tests for L{DistTrialRunner}.
    """

    def getRunner(self, **overrides):
        """
        Create a runner for testing.
        """
        args = dict(
            reporterFactory=TreeReporter,
            workingDirectory=self.mktemp(),
            stream=StringIO(),
            maxWorkers=4,
            workerArguments=[],
            workerPoolFactory=partial(LocalWorkerPool, autostop=True),
        )
        args.update(overrides)
        return DistTrialRunner(**args)

    def test_writeResults(self):
        """
        L{DistTrialRunner.writeResults} writes to the stream specified in the
        init.
        """
        stringIO = StringIO()
        result = DistReporter(Reporter(stringIO))
        runner = self.getRunner()
        runner.writeResults(result)
        self.assertTrue(stringIO.tell() > 0)

    def test_minimalWorker(self):
        """
        L{DistTrialRunner.runAsync} doesn't try to start more workers than the
        number of tests.
        """
        pool = None

        def recordingFactory(*a, **kw):
            nonlocal pool
            pool = LocalWorkerPool(*a, autostop=True, **kw)
            return pool

        maxWorkers = 7
        numTests = 3

        runner = self.getRunner(
            maxWorkers=maxWorkers, workerPoolFactory=recordingFactory
        )
        suite = TrialSuite([TestCase() for n in range(numTests)])
        fakeReactor = object()
        self.successResultOf(runner.runAsync(suite, fakeReactor))
        assert_that(pool._started[0].workers, has_length(numTests))

    def test_runUncleanWarnings(self):
        """
        Running with the C{unclean-warnings} option makes L{DistTrialRunner} uses
        the L{UncleanWarningsReporterWrapper}.
        """
        runner = self.getRunner(uncleanWarnings=True)
        fakeReactor = object()
        d = runner.runAsync(
            TestCase(),
            fakeReactor,
        )
        result = self.successResultOf(d)
        self.assertIsInstance(result, DistReporter)
        self.assertIsInstance(result.original, UncleanWarningsReporterWrapper)

    def test_runWithoutTest(self):
        """
        L{DistTrialRunner} can run an empty test suite.
        """
        stream = StringIO()
        runner = self.getRunner(stream=stream)
        fakeReactor = object()
        result = self.successResultOf(runner.runAsync(TrialSuite(), fakeReactor))
        self.assertIsInstance(result, DistReporter)
        output = stream.getvalue()
        self.assertIn("Running 0 test", output)
        self.assertIn("PASSED", output)

    def test_runWithoutTestButWithAnError(self):
        """
        Even if there is no test, the suite can contain an error (most likely,
        an import error): this should make the run fail, and the error should
        be printed.
        """
        err = ErrorHolder("an error", Failure(RuntimeError("foo bar")))
        stream = StringIO()
        runner = self.getRunner(stream=stream)

        fakeReactor = CountingReactor([])
        result = self.successResultOf(runner.runAsync(err, fakeReactor))
        self.assertIsInstance(result, DistReporter)
        output = stream.getvalue()
        self.assertIn("Running 0 test", output)
        self.assertIn("foo bar", output)
        self.assertIn("an error", output)
        self.assertIn("errors=1", output)
        self.assertIn("FAILED", output)

    def test_runUnexpectedError(self):
        """
        If for some reasons we can't connect to the worker process, the test
        suite catches and fails.
        """
        fakeReactor = object()
        runner = self.getRunner(workerPoolFactory=BrokenWorkerPool)
        result = self.successResultOf(runner.runAsync(TestCase(), fakeReactor))
        errors = result.original.errors
        assert_that(errors, has_length(1))
        assert_that(errors[0][1].type, equal_to(WorkerPoolBroken))

    def test_runWaitForProcessesDeferreds(self):
        """
        L{DistTrialRunner} waits for the worker pool to stop.
        """
        pool = None

        def recordingFactory(*a, **kw):
            nonlocal pool
            pool = LocalWorkerPool(*a, autostop=False, **kw)
            return pool

        runner = self.getRunner(
            workerPoolFactory=recordingFactory,
        )
        d = Deferred.fromCoroutine(runner.runAsync(TestCase(), CountingReactor([])))
        stopped = pool._started[0]._stopped
        self.assertNoResult(d)
        stopped.callback(None)
        result = self.successResultOf(d)
        self.assertIsInstance(result, DistReporter)

    def test_runUntilFailure(self):
        """
        L{DistTrialRunner} can run in C{untilFailure} mode where it will run
        the given tests until they fail.
        """
        stream = StringIO()
        case = erroneous.EventuallyFailingTestCase("test_it")
        runner = self.getRunner(stream=stream)
        d = runner.runAsync(
            case,
            CountingReactor([]),
            untilFailure=True,
        )
        result = self.successResultOf(d)
        # The case is hard-coded to fail on its 5th run.
        self.assertEqual(5, case.n)
        self.assertFalse(result.wasSuccessful())
        output = stream.getvalue()

        # It passes each time except the last.
        self.assertEqual(
            output.count("PASSED"),
            case.n - 1,
            "expected to see PASSED in output",
        )
        # It also fails at the end.
        self.assertIn("FAIL", output)

        # It also reports its progress.
        for i in range(1, 6):
            self.assertIn(f"Test Pass {i}", output)

        # It also reports the number of tests run as part of each iteration.
        self.assertEqual(
            output.count("Ran 1 tests in"),
            case.n,
            "expected to see per-iteration test count in output",
        )


class FunctionalTests(TestCase):
    """
    Tests for the functional helpers that need it.
    """

    def test_void(self) -> None:
        """
        ``void`` accepts an awaitable and returns a ``Deferred`` that fires with
        ``None`` after the awaitable completes.
        """
        a: Deferred[str] = Deferred()
        d = void(a)
        self.assertNoResult(d)
        a.callback("result")
        assert_that(self.successResultOf(d), none())

    def test_sequence(self):
        """
        ``sequence`` accepts two awaitables and returns an awaitable that waits
        for the first one to complete and then completes with the result of
        the second one.
        """
        a: Deferred[str] = Deferred()
        b: Deferred[int] = Deferred()
        c = Deferred.fromCoroutine(sequence(a, b))
        b.callback(42)
        self.assertNoResult(c)
        a.callback("hello")
        assert_that(self.successResultOf(c), equal_to(42))

    def test_iterateWhile(self):
        """
        ``iterateWhile`` executes the actions from its factory until the predicate
        does not match an action result.
        """
        actions: list[Deferred[int]] = [Deferred(), Deferred(), Deferred()]

        def predicate(value):
            return value != 42

        d: Deferred[int] = Deferred.fromCoroutine(
            iterateWhile(predicate, list(actions).pop)
        )
        # Let the action it is waiting on complete
        actions.pop().callback(7)

        # It does not match the predicate so it is not done yet.
        self.assertNoResult(d)

        # Let the action it is waiting on now complete - with the result it
        # wants.
        actions.pop().callback(42)

        assert_that(self.successResultOf(d), equal_to(42))

    def test_countingCalls(self):
        """
        ``countingCalls`` decorates a function so that it is called with an
        increasing counter and passes the return value through.
        """

        @countingCalls
        def target(n: int) -> int:
            return n + 1

        for expected in range(1, 10):
            assert_that(target(), equal_to(expected))


class WorkerPoolBroken(Exception):
    """
    An exception for ``StartedWorkerPoolBroken`` to fail with to allow tests
    to exercise exception code paths.
    """


@define
class BrokenWorkerPool:
    """
    A worker pool that has workers with a broken ``run`` method.
    """

    _config: WorkerPoolConfig

    async def start(
        self, reactor: interfaces.IReactorProcess
    ) -> StartedWorkerPoolBroken:
        return StartedWorkerPoolBroken()


class StartedWorkerPoolBroken:
    """
    A broken, started worker pool.  Its workers cannot run actions.  They
    always raise an exception.
    """

    async def run(self, workerAction: WorkerAction) -> None:
        raise WorkerPoolBroken()

    async def join(self) -> None:
        return None


class _LocalWorker:
    async def run(self, case: TestCase, result: TestResult) -> None:
        TrialSuite([case]).run(result)


@define
class StartedLocalWorkerPool:
    """
    A started L{LocalWorkerPool}.
    """

    workingDirectory: FilePath
    workers: list[_LocalWorker]
    _stopped: Deferred

    async def run(self, workerAction: WorkerAction) -> None:
        """
        Run the action with each local worker.
        """
        for worker in self.workers:
            await workerAction(worker)

    async def join(self):
        await self._stopped


@define
class LocalWorkerPool:
    """
    Implement a worker pool that runs tests in-process instead of in child
    processes.
    """

    _config: WorkerPoolConfig
    _started: list[StartedLocalWorkerPool] = field(default=Factory(list))
    _autostop: bool = False

    async def start(
        self, reactor: interfaces.IReactorProcess
    ) -> StartedLocalWorkerPool:
        workers = [_LocalWorker() for i in range(self._config.numWorkers)]
        started = StartedLocalWorkerPool(
            self._config.workingDirectory,
            workers,
            (succeed(None) if self._autostop else Deferred()),
        )
        self._started.append(started)
        return started
