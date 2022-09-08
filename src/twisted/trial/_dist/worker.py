# -*- test-case-name: twisted.trial._dist.test.test_worker -*-
#
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This module implements the worker classes.

@since: 12.3
"""

import os
from typing import Awaitable, Callable, Dict, List, Optional, TextIO, TypeVar

from zope.interface import implementer

from attrs import frozen
from typing_extensions import Protocol

from twisted.internet.defer import Deferred
from twisted.internet.error import ProcessDone
from twisted.internet.interfaces import IAddress, ITransport
from twisted.internet.protocol import ProcessProtocol
from twisted.protocols.amp import AMP
from twisted.python.failure import Failure
from twisted.python.filepath import FilePath
from twisted.python.reflect import namedObject
from twisted.trial._dist import (
    _WORKER_AMP_STDIN,
    _WORKER_AMP_STDOUT,
    managercommands,
    workercommands,
)
from twisted.trial._dist.workerreporter import WorkerReporter
from twisted.trial.reporter import TestResult
from twisted.trial.runner import TestLoader, TrialSuite
from twisted.trial.unittest import TestCase, Todo


@frozen(auto_exc=False)
class WorkerException(Exception):
    """
    An exception was reported by a test running in a worker process.

    :ivar message: An error message describing the exception.
    """

    message: str


class Worker(Protocol):
    """
    An object that can run actions.
    """

    async def run(self, case: TestCase, result: TestResult) -> None:
        """
        Run a test case.
        """


_T = TypeVar("_T")
WorkerAction = Callable[[Worker], Awaitable[_T]]


class WorkerProtocol(AMP):
    """
    The worker-side trial distributed protocol.
    """

    def __init__(self, forceGarbageCollection=False):
        self._loader = TestLoader()
        self._result = WorkerReporter(self)
        self._forceGarbageCollection = forceGarbageCollection

    @workercommands.Run.responder
    def run(self, testCase):
        """
        Run a test case by name.
        """
        case = self._loader.loadByName(testCase)
        suite = TrialSuite([case], self._forceGarbageCollection)
        suite.run(self._result)
        return {"success": True}

    @workercommands.Start.responder
    def start(self, directory):
        """
        Set up the worker, moving into given directory for tests to run in
        them.
        """
        os.chdir(directory)
        return {"success": True}


class LocalWorkerAMP(AMP):
    """
    Local implementation of the manager commands.
    """

    @managercommands.AddSuccess.responder
    def addSuccess(self, testName):
        """
        Add a success to the reporter.
        """
        self._result.addSuccess(self._testCase)
        return {"success": True}

    def _buildFailure(
        self,
        error: WorkerException,
        errorClass: str,
        frames: List[str],
    ) -> Failure:
        """
        Helper to build a C{Failure} with some traceback.

        @param error: An C{Exception} instance.

        @param errorClass: The class name of the C{error} class.

        @param frames: A flat list of strings representing the information need
            to approximatively rebuild C{Failure} frames.

        @return: A L{Failure} instance with enough information about a test
           error.
        """
        errorType = namedObject(errorClass)
        failure = Failure(error, errorType)
        for i in range(0, len(frames), 3):
            failure.frames.append(
                (frames[i], frames[i + 1], int(frames[i + 2]), [], [])
            )
        return failure

    @managercommands.AddError.responder
    def addError(
        self,
        testName: str,
        error: str,
        errorClass: str,
        frames: List[str],
    ) -> Dict[str, bool]:
        """
        Add an error to the reporter.

        :param error: A message describing the error.
        """
        # Wrap the error message in ``WorkerException`` because it is not
        # possible to transfer arbitrary exception values over the AMP
        # connection to the main process but we must give *some* Exception
        # (not a str) to the test result object.
        failure = self._buildFailure(WorkerException(error), errorClass, frames)
        self._result.addError(self._testCase, failure)
        return {"success": True}

    @managercommands.AddFailure.responder
    def addFailure(
        self,
        testName: str,
        fail: str,
        failClass: str,
        frames: List[str],
    ) -> Dict[str, bool]:
        """
        Add a failure to the reporter.
        """
        # See addError for info about use of WorkerException here.
        failure = self._buildFailure(WorkerException(fail), failClass, frames)
        self._result.addFailure(self._testCase, failure)
        return {"success": True}

    @managercommands.AddSkip.responder
    def addSkip(self, testName, reason):
        """
        Add a skip to the reporter.
        """
        self._result.addSkip(self._testCase, reason)
        return {"success": True}

    @managercommands.AddExpectedFailure.responder
    def addExpectedFailure(
        self, testName: str, error: str, todo: Optional[None]
    ) -> Dict[str, bool]:
        """
        Add an expected failure to the reporter.
        """
        _todo = Todo("<unknown>" if todo is None else todo)
        self._result.addExpectedFailure(self._testCase, error, _todo)
        return {"success": True}

    @managercommands.AddUnexpectedSuccess.responder
    def addUnexpectedSuccess(self, testName, todo):
        """
        Add an unexpected success to the reporter.
        """
        self._result.addUnexpectedSuccess(self._testCase, todo)
        return {"success": True}

    @managercommands.TestWrite.responder
    def testWrite(self, out):
        """
        Print test output from the worker.
        """
        self._testStream.write(out + "\n")
        self._testStream.flush()
        return {"success": True}

    def _stopTest(self, result):
        """
        Stop the current running test case, forwarding the result.
        """
        self._result.stopTest(self._testCase)
        return result

    def run(self, testCase, result):
        """
        Run a test.
        """
        self._testCase = testCase
        self._result = result
        self._result.startTest(testCase)
        testCaseId = testCase.id()
        d = self.callRemote(workercommands.Run, testCase=testCaseId)
        return d.addCallback(self._stopTest)

    def setTestStream(self, stream):
        """
        Set the stream used to log output from tests.
        """
        self._testStream = stream


@implementer(IAddress)
class LocalWorkerAddress:
    """
    A L{IAddress} implementation meant to provide stub addresses for
    L{ITransport.getPeer} and L{ITransport.getHost}.
    """


@implementer(ITransport)
class LocalWorkerTransport:
    """
    A stub transport implementation used to support L{AMP} over a
    L{ProcessProtocol} transport.
    """

    def __init__(self, transport):
        self._transport = transport

    def write(self, data):
        """
        Forward data to transport.
        """
        self._transport.writeToChild(_WORKER_AMP_STDIN, data)

    def writeSequence(self, sequence):
        """
        Emulate C{writeSequence} by iterating data in the C{sequence}.
        """
        for data in sequence:
            self._transport.writeToChild(_WORKER_AMP_STDIN, data)

    def loseConnection(self):
        """
        Closes the transport.
        """
        self._transport.loseConnection()

    def getHost(self):
        """
        Return a L{LocalWorkerAddress} instance.
        """
        return LocalWorkerAddress()

    def getPeer(self):
        """
        Return a L{LocalWorkerAddress} instance.
        """
        return LocalWorkerAddress()


class NotRunning(Exception):
    """
    An operation was attempted on a worker process which is not running.
    """


class LocalWorker(ProcessProtocol):
    """
    Local process worker protocol. This worker runs as a local process and
    communicates via stdin/out.

    @ivar _ampProtocol: The L{AMP} protocol instance used to communicate with
        the worker.

    @ivar _logDirectory: The directory where logs will reside.

    @ivar _logFile: The main log file for tests output.
    """

    def __init__(
        self,
        ampProtocol: LocalWorkerAMP,
        logDirectory: FilePath,
        logFile: TextIO,
    ):
        self._ampProtocol = ampProtocol
        self._logDirectory = logDirectory
        self._logFile = logFile
        self.endDeferred: Deferred = Deferred()

    async def exit(self) -> None:
        """
        Cause the worker process to exit.
        """
        if self.transport is None:
            raise NotRunning()

        endDeferred = self.endDeferred
        self.transport.closeChildFD(_WORKER_AMP_STDIN)
        try:
            await endDeferred
        except ProcessDone:
            pass

    def connectionMade(self):
        """
        When connection is made, create the AMP protocol instance.
        """
        self._ampProtocol.makeConnection(LocalWorkerTransport(self.transport))
        self._logDirectory.makedirs(ignoreExistingDirectory=True)
        self._outLog = self._logDirectory.child("out.log").open("w")
        self._errLog = self._logDirectory.child("err.log").open("w")
        self._ampProtocol.setTestStream(self._logFile)
        d = self._ampProtocol.callRemote(
            workercommands.Start,
            directory=self._logDirectory.path,
        )
        # Ignore the potential errors, the test suite will fail properly and it
        # would just print garbage.
        d.addErrback(lambda x: None)

    def connectionLost(self, reason):
        """
        On connection lost, close the log files that we're managing for stdin
        and stdout.
        """
        self._outLog.close()
        self._errLog.close()
        self.transport = None

    def processEnded(self, reason):
        """
        When the process closes, call C{connectionLost} for cleanup purposes
        and forward the information to the C{_ampProtocol}.
        """
        self.connectionLost(reason)
        self._ampProtocol.connectionLost(reason)
        self.endDeferred.callback(reason)

    def outReceived(self, data):
        """
        Send data received from stdout to log.
        """

        self._outLog.write(data)

    def errReceived(self, data):
        """
        Write error data to log.
        """
        self._errLog.write(data)

    def childDataReceived(self, childFD, data):
        """
        Handle data received on the specific pipe for the C{_ampProtocol}.
        """
        if childFD == _WORKER_AMP_STDOUT:
            self._ampProtocol.dataReceived(data)
        else:
            ProcessProtocol.childDataReceived(self, childFD, data)
