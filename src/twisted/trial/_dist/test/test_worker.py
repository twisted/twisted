# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test for distributed trial worker side.
"""

import os
from io import BytesIO, StringIO
from typing import Type
from unittest import TestCase as PyUnitTestCase

from zope.interface.verify import verifyObject

from hamcrest import assert_that, equal_to, has_item, has_length

from twisted.internet.defer import fail
from twisted.internet.error import ProcessDone
from twisted.internet.interfaces import IAddress, ITransport
from twisted.python.failure import Failure
from twisted.python.filepath import FilePath
from twisted.test.iosim import connectedServerAndClient
from twisted.trial._dist import managercommands
from twisted.trial._dist.worker import (
    LocalWorker,
    LocalWorkerAMP,
    LocalWorkerTransport,
    NotRunning,
    WorkerException,
    WorkerProtocol,
)
from twisted.trial.reporter import TestResult
from twisted.trial.test import pyunitcases, skipping
from twisted.trial.unittest import TestCase, makeTodo
from .matchers import isFailure, matches_result, similarFrame


class WorkerProtocolTests(TestCase):
    """
    Tests for L{WorkerProtocol}.
    """

    worker: WorkerProtocol
    server: LocalWorkerAMP

    def setUp(self) -> None:
        """
        Set up a transport, a result stream and a protocol instance.
        """
        self.worker, self.server, pump = connectedServerAndClient(
            LocalWorkerAMP, WorkerProtocol, greet=False
        )
        self.flush = pump.flush

    def test_run(self) -> None:
        """
        Sending the L{workercommands.Run} command to the worker returns a
        response with C{success} sets to C{True}.
        """
        d = self.server.run(pyunitcases.PyUnitTest("test_pass"), TestResult())
        self.flush()
        self.assertEqual({"success": True}, self.successResultOf(d))

    def test_start(self) -> None:
        """
        The C{start} command changes the current path.
        """
        curdir = os.path.realpath(os.path.curdir)
        self.addCleanup(os.chdir, curdir)
        self.worker.start("..")
        self.assertNotEqual(os.path.realpath(os.path.curdir), curdir)


class LocalWorkerAMPTests(TestCase):
    """
    Test case for distributed trial's manager-side local worker AMP protocol
    """

    def setUp(self) -> None:
        self.worker, self.managerAMP, pump = connectedServerAndClient(
            LocalWorkerAMP, WorkerProtocol, greet=False
        )
        self.flush = pump.flush

    def workerRunTest(
        self, testCase: PyUnitTestCase, makeResult: Type[TestResult] = TestResult
    ) -> TestResult:
        result = makeResult()
        d = self.managerAMP.run(testCase, result)
        self.flush()
        self.assertEqual({"success": True}, self.successResultOf(d))
        return result

    def test_runSuccess(self) -> None:
        """
        Run a test, and succeed.
        """
        result = self.workerRunTest(pyunitcases.PyUnitTest("test_pass"))
        assert_that(result, matches_result(successes=equal_to(1)))

    def test_runExpectedFailure(self) -> None:
        """
        Run a test, and fail expectedly.
        """
        expectedCase = skipping.SynchronousStrictTodo("test_todo1")
        result = self.workerRunTest(expectedCase)
        assert_that(result, matches_result(expectedFailures=has_length(1)))
        [(actualCase, exceptionMessage, todoReason)] = result.expectedFailures
        assert_that(actualCase, equal_to(expectedCase))

        # Match the strings used in the test we ran.
        assert_that(exceptionMessage, equal_to("expected failure"))
        assert_that(todoReason, equal_to(makeTodo("todo1")))

    def test_runError(self) -> None:
        """
        Run a test, and encounter an error.
        """
        expectedCase = pyunitcases.PyUnitTest("test_error")
        result = self.workerRunTest(expectedCase)
        assert_that(result, matches_result(errors=has_length(1)))
        [(actualCase, failure)] = result.errors
        assert_that(expectedCase, equal_to(actualCase))
        assert_that(
            failure,
            isFailure(
                type=equal_to(Exception),
                value=equal_to(WorkerException("pyunit error")),
                frames=has_item(similarFrame("test_error", "pyunitcases.py")),  # type: ignore[arg-type]
            ),
        )

    def test_runFailure(self) -> None:
        """
        Run a test, and fail.
        """
        expectedCase = pyunitcases.PyUnitTest("test_fail")
        result = self.workerRunTest(expectedCase)
        assert_that(result, matches_result(failures=has_length(1)))
        [(actualCase, failure)] = result.failures
        assert_that(expectedCase, equal_to(actualCase))
        assert_that(
            failure,
            isFailure(
                # AssertionError is the type raised by TestCase.fail
                type=equal_to(AssertionError),
                value=equal_to(WorkerException("pyunit failure")),
            ),
        )

    def test_runSkip(self) -> None:
        """
        Run a test, but skip it.
        """
        expectedCase = pyunitcases.PyUnitTest("test_skip")
        result = self.workerRunTest(expectedCase)
        assert_that(result, matches_result(skips=has_length(1)))
        [(actualCase, skip)] = result.skips
        assert_that(expectedCase, equal_to(actualCase))
        assert_that(skip, equal_to("pyunit skip"))

    def test_runUnexpectedSuccesses(self) -> None:
        """
        Run a test, and succeed unexpectedly.
        """
        expectedCase = skipping.SynchronousStrictTodo("test_todo7")
        result = self.workerRunTest(expectedCase)
        assert_that(result, matches_result(unexpectedSuccesses=has_length(1)))
        [(actualCase, unexpectedSuccess)] = result.unexpectedSuccesses
        assert_that(expectedCase, equal_to(actualCase))
        assert_that(unexpectedSuccess, equal_to("todo7"))

    def test_testWrite(self) -> None:
        """
        L{LocalWorkerAMP.testWrite} writes the data received to its test
        stream.
        """
        stream = StringIO()
        self.managerAMP.setTestStream(stream)
        d = self.worker.callRemote(managercommands.TestWrite, out="Some output")
        self.flush()
        self.assertEqual({"success": True}, self.successResultOf(d))
        self.assertEqual("Some output\n", stream.getvalue())

    def test_stopAfterRun(self) -> None:
        """
        L{LocalWorkerAMP.run} calls C{stopTest} on its test result once the
        C{Run} commands has succeeded.
        """
        stopped = []

        class StopTestResult(TestResult):
            def stopTest(self, test: PyUnitTestCase) -> None:
                stopped.append(test)

        case = pyunitcases.PyUnitTest("test_pass")
        self.workerRunTest(case, StopTestResult)
        assert_that(stopped, equal_to([case]))


class SpyDataLocalWorkerAMP(LocalWorkerAMP):
    """
    A fake implementation of L{LocalWorkerAMP} that records the received
    data and doesn't automatically dispatch any command..
    """

    id = 0
    dataString = b""

    def dataReceived(self, data):
        self.dataString += data


class FakeTransport:
    """
    A fake process transport implementation for testing.
    """

    dataString = b""
    calls = 0

    def writeToChild(self, fd, data):
        self.dataString += data

    def loseConnection(self):
        self.calls += 1


class LocalWorkerTests(TestCase):
    """
    Tests for L{LocalWorker} and L{LocalWorkerTransport}.
    """

    def tidyLocalWorker(self, *args, **kwargs):
        """
        Create a L{LocalWorker}, connect it to a transport, and ensure
        its log files are closed.

        @param args: See L{LocalWorker}

        @param kwargs: See L{LocalWorker}

        @return: a L{LocalWorker} instance
        """
        worker = LocalWorker(*args, **kwargs)
        worker.makeConnection(FakeTransport())
        self.addCleanup(worker._outLog.close)
        self.addCleanup(worker._errLog.close)
        return worker

    def test_exitBeforeConnected(self):
        """
        L{LocalWorker.exit} fails with L{NotRunning} if it is called before the
        protocol is connected to a transport.
        """
        worker = LocalWorker(
            SpyDataLocalWorkerAMP(), FilePath(self.mktemp()), StringIO()
        )
        self.failureResultOf(worker.exit(), NotRunning)

    def test_exitAfterDisconnected(self):
        """
        L{LocalWorker.exit} fails with L{NotRunning} if it is called after the the
        protocol is disconnected from its transport.
        """
        worker = self.tidyLocalWorker(
            SpyDataLocalWorkerAMP(), FilePath(self.mktemp()), StringIO()
        )
        worker.processEnded(Failure(ProcessDone(0)))
        # Since we're not calling exit until after the process has ended, it
        # won't consume the ProcessDone failure on the internal `endDeferred`.
        # Swallow it here.
        self.failureResultOf(worker.endDeferred, ProcessDone)

        # Now assert that exit behaves.
        self.failureResultOf(worker.exit(), NotRunning)

    def test_childDataReceived(self):
        """
        L{LocalWorker.childDataReceived} forwards the received data to linked
        L{AMP} protocol if the right file descriptor, otherwise forwards to
        C{ProcessProtocol.childDataReceived}.
        """
        localWorker = self.tidyLocalWorker(
            SpyDataLocalWorkerAMP(), FilePath(self.mktemp()), "test.log"
        )
        localWorker._outLog = BytesIO()
        localWorker.childDataReceived(4, b"foo")
        localWorker.childDataReceived(1, b"bar")
        self.assertEqual(b"foo", localWorker._ampProtocol.dataString)
        self.assertEqual(b"bar", localWorker._outLog.getvalue())

    def test_newlineStyle(self):
        """
        L{LocalWorker} writes the log data with local newlines.
        """
        amp = SpyDataLocalWorkerAMP()
        tempDir = FilePath(self.mktemp())
        tempDir.makedirs()
        logPath = tempDir.child("test.log")

        with open(logPath.path, "wt", encoding="utf-8") as logFile:
            worker = LocalWorker(amp, tempDir, logFile)
            worker.makeConnection(FakeTransport())
            self.addCleanup(worker._outLog.close)
            self.addCleanup(worker._errLog.close)

            expected = "Here comes the \N{sun}!"
            amp.testWrite(expected)

        self.assertEqual(
            # os.linesep is the local newline.
            (expected + os.linesep),
            # getContent reads in binary mode so we'll see the bytes that
            # actually ended up in the file.
            logPath.getContent().decode("utf-8"),
        )

    def test_outReceived(self):
        """
        L{LocalWorker.outReceived} logs the output into its C{_outLog} log
        file.
        """
        localWorker = self.tidyLocalWorker(
            SpyDataLocalWorkerAMP(), FilePath(self.mktemp()), "test.log"
        )
        localWorker._outLog = BytesIO()
        data = b"The quick brown fox jumps over the lazy dog"
        localWorker.outReceived(data)
        self.assertEqual(data, localWorker._outLog.getvalue())

    def test_errReceived(self):
        """
        L{LocalWorker.errReceived} logs the errors into its C{_errLog} log
        file.
        """
        localWorker = self.tidyLocalWorker(
            SpyDataLocalWorkerAMP(), FilePath(self.mktemp()), "test.log"
        )
        localWorker._errLog = BytesIO()
        data = b"The quick brown fox jumps over the lazy dog"
        localWorker.errReceived(data)
        self.assertEqual(data, localWorker._errLog.getvalue())

    def test_write(self):
        """
        L{LocalWorkerTransport.write} forwards the written data to the given
        transport.
        """
        transport = FakeTransport()
        localTransport = LocalWorkerTransport(transport)
        data = b"The quick brown fox jumps over the lazy dog"
        localTransport.write(data)
        self.assertEqual(data, transport.dataString)

    def test_writeSequence(self):
        """
        L{LocalWorkerTransport.writeSequence} forwards the written data to the
        given transport.
        """
        transport = FakeTransport()
        localTransport = LocalWorkerTransport(transport)
        data = (b"The quick ", b"brown fox jumps ", b"over the lazy dog")
        localTransport.writeSequence(data)
        self.assertEqual(b"".join(data), transport.dataString)

    def test_loseConnection(self):
        """
        L{LocalWorkerTransport.loseConnection} forwards the call to the given
        transport.
        """
        transport = FakeTransport()
        localTransport = LocalWorkerTransport(transport)
        localTransport.loseConnection()

        self.assertEqual(transport.calls, 1)

    def test_connectionLost(self):
        """
        L{LocalWorker.connectionLost} closes the per-worker log streams.
        """

        localWorker = self.tidyLocalWorker(
            SpyDataLocalWorkerAMP(), FilePath(self.mktemp()), "test.log"
        )
        localWorker.connectionLost(None)
        self.assertTrue(localWorker._outLog.closed)
        self.assertTrue(localWorker._errLog.closed)

    def test_processEnded(self):
        """
        L{LocalWorker.processEnded} calls C{connectionLost} on itself and on
        the L{AMP} protocol.
        """
        transport = FakeTransport()
        protocol = SpyDataLocalWorkerAMP()
        localWorker = LocalWorker(protocol, FilePath(self.mktemp()), "test.log")
        localWorker.makeConnection(transport)
        localWorker.processEnded(Failure(ProcessDone(0)))
        self.assertTrue(localWorker._outLog.closed)
        self.assertTrue(localWorker._errLog.closed)
        self.assertIdentical(None, protocol.transport)
        return self.assertFailure(localWorker.endDeferred, ProcessDone)

    def test_addresses(self):
        """
        L{LocalWorkerTransport.getPeer} and L{LocalWorkerTransport.getHost}
        return L{IAddress} objects.
        """
        localTransport = LocalWorkerTransport(None)
        self.assertTrue(verifyObject(IAddress, localTransport.getPeer()))
        self.assertTrue(verifyObject(IAddress, localTransport.getHost()))

    def test_transport(self):
        """
        L{LocalWorkerTransport} implements L{ITransport} to be able to be used
        by L{AMP}.
        """
        localTransport = LocalWorkerTransport(None)
        self.assertTrue(verifyObject(ITransport, localTransport))

    def test_startError(self):
        """
        L{LocalWorker} swallows the exceptions returned by the L{AMP} protocol
        start method, as it generates unnecessary errors.
        """

        def failCallRemote(command, directory):
            return fail(RuntimeError("oops"))

        protocol = SpyDataLocalWorkerAMP()
        protocol.callRemote = failCallRemote
        self.tidyLocalWorker(protocol, FilePath(self.mktemp()), "test.log")
        self.assertEqual([], self.flushLoggedErrors(RuntimeError))
