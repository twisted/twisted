# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test for distributed trial worker side.
"""

import os
from cStringIO import StringIO

from zope.interface.verify import verifyObject

from twisted.trial.reporter import TestResult
from twisted.trial.unittest import TestCase
from twisted.trial._dist.worker import (
    LocalWorker, LocalWorkerAMP, LocalWorkerTransport, WorkerProtocol)
from twisted.trial._dist import managercommands, workercommands

from twisted.scripts import trial
from twisted.test.proto_helpers import StringTransport

from twisted.internet.interfaces import ITransport, IAddress
from twisted.internet.defer import fail, succeed
from twisted.internet.main import CONNECTION_DONE
from twisted.internet.error import ConnectionDone
from twisted.python.failure import Failure
from twisted.protocols.amp import AMP



class FakeAMP(AMP):
    """
    A fake amp protocol.
    """



class WorkerProtocolTestCase(TestCase):
    """
    Tests for L{WorkerProtocol}.
    """

    def setUp(self):
        """
        Set up a transport, a result stream and a protocol instance.
        """
        self.serverTransport = StringTransport()
        self.clientTransport = StringTransport()
        self.server = WorkerProtocol()
        self.server.makeConnection(self.serverTransport)
        self.client = FakeAMP()
        self.client.makeConnection(self.clientTransport)


    def test_run(self):
        """
        Calling the L{workercommands.Run} command on the client returns a
        response with C{success} sets to C{True}.
        """
        d = self.client.callRemote(workercommands.Run, testCase="doesntexist")

        def check(result):
            self.assertTrue(result['success'])

        d.addCallback(check)
        self.server.dataReceived(self.clientTransport.value())
        self.clientTransport.clear()
        self.client.dataReceived(self.serverTransport.value())
        self.serverTransport.clear()
        return d


    def test_start(self):
        """
        The C{start} command changes the current path.
        """
        curdir = os.path.realpath(os.path.curdir)
        self.addCleanup(os.chdir, curdir)
        self.server.start('..')
        self.assertNotEqual(os.path.realpath(os.path.curdir), curdir)



class LocalWorkerAMPTestCase(TestCase):
    """
    Test case for distributed trial's manager-side local worker AMP protocol
    """

    def setUp(self):
        self.managerTransport = StringTransport()
        self.managerAMP = LocalWorkerAMP()
        self.managerAMP.makeConnection(self.managerTransport)
        self.result = TestResult()
        self.workerTransport = StringTransport()
        self.worker = AMP()
        self.worker.makeConnection(self.workerTransport)

        config = trial.Options()
        self.testName = "twisted.doesnexist"
        config['tests'].add(self.testName)
        self.testCase = trial._getSuite(config)._tests.pop()

        self.managerAMP.run(self.testCase, self.result)
        self.managerTransport.clear()


    def pumpTransports(self):
        """
        Sends data from C{self.workerTransport} to C{self.managerAMP}, and then
        data from C{self.managerTransport} back to C{self.worker}.
        """
        self.managerAMP.dataReceived(self.workerTransport.value())
        self.workerTransport.clear()
        self.worker.dataReceived(self.managerTransport.value())


    def test_runSuccess(self):
        """
        Run a test, and succeed.
        """
        results = []

        d = self.worker.callRemote(managercommands.AddSuccess,
                                   testName=self.testName)
        d.addCallback(lambda result: results.append(result['success']))
        self.pumpTransports()

        self.assertTrue(results)


    def test_runExpectedFailure(self):
        """
        Run a test, and fail expectedly.
        """
        results = []

        d = self.worker.callRemote(managercommands.AddExpectedFailure,
                                   testName=self.testName, error='error',
                                   todo='todoReason')
        d.addCallback(lambda result: results.append(result['success']))
        self.pumpTransports()

        self.assertEqual(self.testCase, self.result.expectedFailures[0][0])
        self.assertTrue(results)


    def test_runError(self):
        """
        Run a test, and encounter an error.
        """
        results = []

        d = self.worker.callRemote(managercommands.AddError,
                                   testName=self.testName, error='error',
                                   errorClass='exceptions.ValueError',
                                   frames=[])
        d.addCallback(lambda result: results.append(result['success']))
        self.pumpTransports()

        self.assertEqual(self.testCase, self.result.errors[0][0])
        self.assertTrue(results)


    def test_runErrorWithFrames(self):
        """
        L{LocalWorkerAMP._buildFailure} recreates the C{Failure.frames} from
        the C{frames} argument passed to C{AddError}.
        """
        results = []

        d = self.worker.callRemote(managercommands.AddError,
                                   testName=self.testName, error='error',
                                   errorClass='exceptions.ValueError',
                                   frames=["file.py", "invalid code", "3"])
        d.addCallback(lambda result: results.append(result['success']))
        self.pumpTransports()

        self.assertEqual(self.testCase, self.result.errors[0][0])
        self.assertEqual(
            [('file.py', 'invalid code', 3, [], [])],
            self.result.errors[0][1].frames)
        self.assertTrue(results)


    def test_runFailure(self):
        """
        Run a test, and fail.
        """
        results = []

        d = self.worker.callRemote(managercommands.AddFailure,
                                   testName=self.testName, fail='fail',
                                   failClass='exceptions.RuntimeError',
                                   frames=[])
        d.addCallback(lambda result: results.append(result['success']))
        self.pumpTransports()

        self.assertEqual(self.testCase, self.result.failures[0][0])
        self.assertTrue(results)


    def test_runSkip(self):
        """
        Run a test, but skip it.
        """
        results = []

        d = self.worker.callRemote(managercommands.AddSkip,
                                   testName=self.testName, reason='reason')
        d.addCallback(lambda result: results.append(result['success']))
        self.pumpTransports()

        self.assertEqual(self.testCase, self.result.skips[0][0])
        self.assertTrue(results)


    def test_runUnexpectedSuccesses(self):
        """
        Run a test, and succeed unexpectedly.
        """
        results = []

        d = self.worker.callRemote(managercommands.AddUnexpectedSuccess,
                                   testName=self.testName,
                                   todo='todo')
        d.addCallback(lambda result: results.append(result['success']))
        self.pumpTransports()

        self.assertEqual(self.testCase, self.result.unexpectedSuccesses[0][0])
        self.assertTrue(results)


    def test_testWrite(self):
        """
        L{LocalWorkerAMP.testWrite} writes the data received to its test
        stream.
        """
        results = []
        stream = StringIO()
        self.managerAMP.setTestStream(stream)


        d = self.worker.callRemote(managercommands.TestWrite,
                                   out="Some output")
        d.addCallback(lambda result: results.append(result['success']))
        self.pumpTransports()

        self.assertEqual("Some output\n", stream.getvalue())
        self.assertTrue(results)


    def test_stopAfterRun(self):
        """
        L{LocalWorkerAMP.run} calls C{stopTest} on its test result once the
        C{Run} commands has succeeded.
        """
        result = object()
        stopped = []

        def fakeCallRemote(command, testCase):
            return succeed(result)

        self.managerAMP.callRemote = fakeCallRemote

        class StopTestResult(TestResult):

            def stopTest(self, test):
                stopped.append(test)


        d = self.managerAMP.run(self.testCase, StopTestResult())
        self.assertEqual([self.testCase], stopped)
        return d.addCallback(self.assertIdentical, result)



class FakeAMProtocol(AMP):
    """
    A fake implementation of L{AMP} for testing.
    """
    id = 0
    dataString = ""

    def dataReceived(self, data):
        self.dataString += data


    def setTestStream(self, stream):
        self.testStream = stream



class FakeTransport(object):
    """
    A fake process transport implementation for testing.
    """
    dataString = ""
    calls = 0

    def writeToChild(self, fd, data):
        self.dataString += data


    def loseConnection(self):
        self.calls += 1



class LocalWorkerTestCase(TestCase):
    """
    Tests for L{LocalWorker} and L{LocalWorkerTransport}.
    """

    def test_childDataReceived(self):
        """
        L{LocalWorker.childDataReceived} forwards the received data to linked
        L{AMP} protocol if the right file descriptor, otherwise forwards to
        C{ProcessProtocol.childDataReceived}.
        """
        fakeTransport = FakeTransport()
        localWorker = LocalWorker(FakeAMProtocol(), '.', 'test.log')
        localWorker.makeConnection(fakeTransport)
        localWorker._outLog = StringIO()
        localWorker.childDataReceived(4, "foo")
        localWorker.childDataReceived(1, "bar")
        self.assertEqual("foo", localWorker._ampProtocol.dataString)
        self.assertEqual("bar", localWorker._outLog.getvalue())


    def test_outReceived(self):
        """
        L{LocalWorker.outReceived} logs the output into its C{_outLog} log
        file.
        """
        fakeTransport = FakeTransport()
        localWorker = LocalWorker(FakeAMProtocol(), '.', 'test.log')
        localWorker.makeConnection(fakeTransport)
        localWorker._outLog = StringIO()
        data = "The quick brown fox jumps over the lazy dog"
        localWorker.outReceived(data)
        self.assertEqual(data, localWorker._outLog.getvalue())


    def test_errReceived(self):
        """
        L{LocalWorker.errReceived} logs the errors into its C{_errLog} log
        file.
        """
        fakeTransport = FakeTransport()
        localWorker = LocalWorker(FakeAMProtocol(), '.', 'test.log')
        localWorker.makeConnection(fakeTransport)
        localWorker._errLog = StringIO()
        data = "The quick brown fox jumps over the lazy dog"
        localWorker.errReceived(data)
        self.assertEqual(data, localWorker._errLog.getvalue())


    def test_write(self):
        """
        L{LocalWorkerTransport.write} forwards the written data to the given
        transport.
        """
        transport = FakeTransport()
        localTransport = LocalWorkerTransport(transport)
        data = "The quick brown fox jumps over the lazy dog"
        localTransport.write(data)
        self.assertEqual(data, transport.dataString)


    def test_writeSequence(self):
        """
        L{LocalWorkerTransport.writeSequence} forwards the written data to the
        given transport.
        """
        transport = FakeTransport()
        localTransport = LocalWorkerTransport(transport)
        data = ("The quick ", "brown fox jumps ", "over the lazy dog")
        localTransport.writeSequence(data)
        self.assertEqual("".join(data), transport.dataString)


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
        L{LocalWorker.connectionLost} closes the log streams.
        """

        class FakeStream(object):
            callNumber = 0

            def close(self):
                self.callNumber += 1


        transport = FakeTransport()
        localWorker = LocalWorker(FakeAMProtocol(), '.', 'test.log')
        localWorker.makeConnection(transport)
        localWorker._outLog = FakeStream()
        localWorker._errLog = FakeStream()
        localWorker.connectionLost(None)
        self.assertEqual(localWorker._outLog.callNumber, 1)
        self.assertEqual(localWorker._errLog.callNumber, 1)


    def test_processEnded(self):
        """
        L{LocalWorker.processEnded} calls C{connectionLost} on itself and on
        the L{AMP} protocol.
        """

        class FakeStream(object):
            callNumber = 0

            def close(self):
                self.callNumber += 1


        transport = FakeTransport()
        protocol = FakeAMProtocol()
        localWorker = LocalWorker(protocol, '.', 'test.log')
        localWorker.makeConnection(transport)
        localWorker._outLog = FakeStream()
        localWorker.processEnded(Failure(CONNECTION_DONE))
        self.assertEqual(localWorker._outLog.callNumber, 1)
        self.assertIdentical(None, protocol.transport)
        return self.assertFailure(localWorker.endDeferred, ConnectionDone)

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

        transport = FakeTransport()
        protocol = FakeAMProtocol()
        protocol.callRemote = failCallRemote
        localWorker = LocalWorker(protocol, '.', 'test.log')
        localWorker.makeConnection(transport)

        self.assertEqual([], self.flushLoggedErrors(RuntimeError))
