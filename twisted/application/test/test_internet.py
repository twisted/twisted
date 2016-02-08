# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for (new code in) L{twisted.application.internet}.
"""

from __future__ import absolute_import, division

import pickle

from zope.interface import implementer
from zope.interface.verify import verifyClass

from twisted.internet.protocol import Factory, Protocol
from twisted.internet.task import Clock
from twisted.trial.unittest import TestCase
from twisted.application import internet
from twisted.application.internet import (
    StreamServerEndpointService, TimerService, ReconnectingClientService)
from twisted.internet.defer import Deferred, CancelledError
from twisted.internet.interfaces import (
    IStreamServerEndpoint, IStreamClientEndpoint, IListeningPort
)
from twisted.internet import task
from twisted.python.failure import Failure
from twisted.logger import globalLogPublisher, formatEvent
from twisted.test.proto_helpers import StringTransport


def fakeTargetFunction():
    """
    A fake target function for testing TimerService which does nothing.
    """
    pass



@implementer(IStreamServerEndpoint)
class FakeServer(object):
    """
    In-memory implementation of L{IStreamServerEndpoint}.

    @ivar result: The L{Deferred} resulting from the call to C{listen}, after
        C{listen} has been called.

    @ivar factory: The factory passed to C{listen}.

    @ivar cancelException: The exception to errback C{self.result} when it is
        cancelled.

    @ivar port: The L{IListeningPort} which C{listen}'s L{Deferred} will fire
        with.

    @ivar listenAttempts: The number of times C{listen} has been invoked.

    @ivar failImmediately: If set, the exception to fail the L{Deferred}
        returned from C{listen} before it is returned.
    """
    result = None
    factory = None
    failImmediately = None
    cancelException = CancelledError()
    listenAttempts = 0

    def __init__(self):
        self.port = FakePort()


    def listen(self, factory):
        """
        Return a Deferred and store it for future use.  (Implementation of
        L{IStreamServerEndpoint}).

        @param factory: the factory to listen with

        @return: a L{Deferred} stored in L{FakeServer.result}
        """
        self.listenAttempts += 1
        self.factory = factory
        self.result = Deferred(
            canceller=lambda d: d.errback(self.cancelException))
        if self.failImmediately is not None:
            self.result.errback(self.failImmediately)
        return self.result


    def startedListening(self):
        """
        Test code should invoke this method after causing C{listen} to be
        invoked in order to fire the L{Deferred} previously returned from
        C{listen}.
        """
        self.result.callback(self.port)


    def stoppedListening(self):
        """
        Test code should invoke this method after causing C{stopListening} to
        be invoked on the port fired from the L{Deferred} returned from
        C{listen} in order to cause the L{Deferred} returned from
        C{stopListening} to fire.
        """
        self.port.deferred.callback(None)

verifyClass(IStreamServerEndpoint, FakeServer)



@implementer(IListeningPort)
class FakePort(object):
    """
    Fake L{IListeningPort} implementation.

    @ivar deferred: The L{Deferred} returned by C{stopListening}.
    """
    deferred = None

    def stopListening(self):
        """
        Stop listening.

        @return: a L{Deferred} stored in L{FakePort.deferred}
        """
        self.deferred = Deferred()
        return self.deferred

verifyClass(IStreamServerEndpoint, FakeServer)



class EndpointServiceTests(TestCase):
    """
    Tests for L{twisted.application.internet}.
    """

    def setUp(self):
        """
        Construct a stub server, a stub factory, and a
        L{StreamServerEndpointService} to test.
        """
        self.fakeServer = FakeServer()
        self.factory = Factory()
        self.svc = StreamServerEndpointService(self.fakeServer, self.factory)


    def test_privilegedStartService(self):
        """
        L{StreamServerEndpointService.privilegedStartService} calls its
        endpoint's C{listen} method with its factory.
        """
        self.svc.privilegedStartService()
        self.assertIdentical(self.factory, self.fakeServer.factory)


    def test_synchronousRaiseRaisesSynchronously(self, thunk=None):
        """
        L{StreamServerEndpointService.startService} should raise synchronously
        if the L{Deferred} returned by its wrapped
        L{IStreamServerEndpoint.listen} has already fired with an errback and
        the L{StreamServerEndpointService}'s C{_raiseSynchronously} flag has
        been set.  This feature is necessary to preserve compatibility with old
        behavior of L{twisted.internet.strports.service}, which is to return a
        service which synchronously raises an exception from C{startService}
        (so that, among other things, twistd will not start running).  However,
        since L{IStreamServerEndpoint.listen} may fail asynchronously, it is a
        bad idea to rely on this behavior.

        @param thunk: If specified, a callable to execute in place of
            C{startService}.
        """
        self.fakeServer.failImmediately = ZeroDivisionError()
        self.svc._raiseSynchronously = True
        self.assertRaises(ZeroDivisionError, thunk or self.svc.startService)


    def test_synchronousRaisePrivileged(self):
        """
        L{StreamServerEndpointService.privilegedStartService} should behave the
        same as C{startService} with respect to
        L{EndpointServiceTests.test_synchronousRaiseRaisesSynchronously}.
        """
        self.test_synchronousRaiseRaisesSynchronously(
            self.svc.privilegedStartService)


    def test_failReportsError(self):
        """
        L{StreamServerEndpointService.startService} and
        L{StreamServerEndpointService.privilegedStartService} should both log
        an exception when the L{Deferred} returned from their wrapped
        L{IStreamServerEndpoint.listen} fails.
        """
        self.svc.startService()
        self.fakeServer.result.errback(ZeroDivisionError())
        logged = self.flushLoggedErrors(ZeroDivisionError)
        self.assertEqual(len(logged), 1)


    def test_synchronousFailReportsError(self):
        """
        Without the C{_raiseSynchronously} compatibility flag, failing
        immediately has the same behavior as failing later; it logs the error.
        """
        self.fakeServer.failImmediately = ZeroDivisionError()
        self.svc.startService()
        logged = self.flushLoggedErrors(ZeroDivisionError)
        self.assertEqual(len(logged), 1)


    def test_startServiceUnstarted(self):
        """
        L{StreamServerEndpointService.startService} sets the C{running} flag,
        and calls its endpoint's C{listen} method with its factory, if it
        has not yet been started.
        """
        self.svc.startService()
        self.assertIdentical(self.factory, self.fakeServer.factory)
        self.assertEqual(self.svc.running, True)


    def test_startServiceStarted(self):
        """
        L{StreamServerEndpointService.startService} sets the C{running} flag,
        but nothing else, if the service has already been started.
        """
        self.test_privilegedStartService()
        self.svc.startService()
        self.assertEqual(self.fakeServer.listenAttempts, 1)
        self.assertEqual(self.svc.running, True)


    def test_stopService(self):
        """
        L{StreamServerEndpointService.stopService} calls C{stopListening} on
        the L{IListeningPort} returned from its endpoint, returns the
        C{Deferred} from stopService, and sets C{running} to C{False}.
        """
        self.svc.privilegedStartService()
        self.fakeServer.startedListening()
        # Ensure running gets set to true
        self.svc.startService()
        result = self.svc.stopService()
        l = []
        result.addCallback(l.append)
        self.assertEqual(len(l), 0)
        self.fakeServer.stoppedListening()
        self.assertEqual(len(l), 1)
        self.assertFalse(self.svc.running)


    def test_stopServiceBeforeStartFinished(self):
        """
        L{StreamServerEndpointService.stopService} cancels the L{Deferred}
        returned by C{listen} if it has not yet fired.  No error will be logged
        about the cancellation of the listen attempt.
        """
        self.svc.privilegedStartService()
        result = self.svc.stopService()
        l = []
        result.addBoth(l.append)
        self.assertEqual(l, [None])
        self.assertEqual(self.flushLoggedErrors(CancelledError), [])


    def test_stopServiceCancelStartError(self):
        """
        L{StreamServerEndpointService.stopService} cancels the L{Deferred}
        returned by C{listen} if it has not fired yet.  An error will be logged
        if the resulting exception is not L{CancelledError}.
        """
        self.fakeServer.cancelException = ZeroDivisionError()
        self.svc.privilegedStartService()
        result = self.svc.stopService()
        l = []
        result.addCallback(l.append)
        self.assertEqual(l, [None])
        stoppingErrors = self.flushLoggedErrors(ZeroDivisionError)
        self.assertEqual(len(stoppingErrors), 1)



class TimerServiceTests(TestCase):
    """
    Tests for L{twisted.application.internet.TimerService}.

    @type timer: L{TimerService}
    @ivar timer: service to test

    @type clock: L{task.Clock}
    @ivar clock: source of time

    @type deferred: L{Deferred}
    @ivar deferred: deferred returned by L{TimerServiceTests.call}.
    """

    def setUp(self):
        self.timer = TimerService(2, self.call)
        self.clock = self.timer.clock = task.Clock()
        self.deferred = Deferred()


    def call(self):
        """
        Function called by L{TimerService} being tested.

        @returns: C{self.deferred}
        @rtype: L{Deferred}
        """
        return self.deferred


    def test_startService(self):
        """
        When L{TimerService.startService} is called, it marks itself
        as running, creates a L{task.LoopingCall} and starts it.
        """
        self.timer.startService()
        self.assertTrue(self.timer.running, "Service is started")
        self.assertIsInstance(self.timer._loop, task.LoopingCall)
        self.assertIdentical(self.clock, self.timer._loop.clock)
        self.assertTrue(self.timer._loop.running, "LoopingCall is started")


    def test_startServiceRunsCallImmediately(self):
        """
        When L{TimerService.startService} is called, it calls the function
        immediately.
        """
        result = []
        self.timer.call = (result.append, (None,), {})
        self.timer.startService()
        self.assertEqual([None], result)


    def test_startServiceUsesGlobalReactor(self):
        """
        L{TimerService.startService} uses L{internet._maybeGlobalReactor} to
        choose the reactor to pass to L{task.LoopingCall}
        uses the global reactor.
        """
        otherClock = task.Clock()
        def getOtherClock(maybeReactor):
            return otherClock
        self.patch(internet, "_maybeGlobalReactor", getOtherClock)
        self.timer.startService()
        self.assertIdentical(otherClock, self.timer._loop.clock)


    def test_stopServiceWaits(self):
        """
        When L{TimerService.stopService} is called while a call is in progress.
        the L{Deferred} returned doesn't fire until after the call finishes.
        """
        self.timer.startService()
        d = self.timer.stopService()
        self.assertNoResult(d)
        self.assertEqual(True, self.timer.running)
        self.deferred.callback(object())
        self.assertIdentical(self.successResultOf(d), None)


    def test_stopServiceImmediately(self):
        """
        When L{TimerService.stopService} is called while a call isn't in progress.
        the L{Deferred} returned has already been fired.
        """
        self.timer.startService()
        self.deferred.callback(object())
        d = self.timer.stopService()
        self.assertIdentical(self.successResultOf(d), None)


    def test_failedCallLogsError(self):
        """
        When function passed to L{TimerService} returns a deferred that errbacks,
        the exception is logged, and L{TimerService.stopService} doesn't raise an error.
        """
        self.timer.startService()
        self.deferred.errback(Failure(ZeroDivisionError()))
        errors = self.flushLoggedErrors(ZeroDivisionError)
        self.assertEqual(1, len(errors))
        d = self.timer.stopService()
        self.assertIdentical(self.successResultOf(d), None)


    def test_pickleTimerServiceNotPickleLoop(self):
        """
        When pickling L{internet.TimerService}, it won't pickle
        L{internet.TimerService._loop}.
        """
        # We need a pickleable callable to test pickling TimerService. So we
        # can't use self.timer
        timer = TimerService(1, fakeTargetFunction)
        timer.startService()
        dumpedTimer = pickle.dumps(timer)
        timer.stopService()
        loadedTimer = pickle.loads(dumpedTimer)
        nothing = object()
        value = getattr(loadedTimer, "_loop", nothing)
        self.assertIdentical(nothing, value)


    def test_pickleTimerServiceNotPickleLoopFinished(self):
        """
        When pickling L{internet.TimerService}, it won't pickle
        L{internet.TimerService._loopFinished}.
        """
        # We need a pickleable callable to test pickling TimerService. So we
        # can't use self.timer
        timer = TimerService(1, fakeTargetFunction)
        timer.startService()
        dumpedTimer = pickle.dumps(timer)
        timer.stopService()
        loadedTimer = pickle.loads(dumpedTimer)
        nothing = object()
        value = getattr(loadedTimer, "_loopFinished", nothing)
        self.assertIdentical(nothing, value)



class ConnectInformation(object):
    """
    Information about C{endpointForTesting}

    @ivar connectQueue: a L{list} of L{Deferred} returned from C{connect}.  If
        these are not already fired, you can fire them with no value and they
        will trigger building a factory.

    @ivar constructedProtocols: a L{list} of protocols constructed.
    """
    def __init__(self):
        self.connectQueue = []
        self.constructedProtocols = []



def endpointForTesting(fireImmediately=False):
    """
    Make a sample endpoint for testing.

    @param fireImmediately: If true, fire all L{Deferred}s returned from
        C{connect} immedaitely.

    @return: a 2-tuple of C{(information, endpoint)}, where C{information} is a
        L{ConnectInformation} describing the operations in progress on
        C{endpoint}.
    """
    @implementer(IStreamClientEndpoint)
    class ClientTestEndpoint(object):
        def connect(self, factory):
            result = Deferred()
            @result.addCallback
            def createProtocol(ignored):
                protocol = factory.buildProtocol(None)
                info.constructedProtocols.append(protocol)
                transport = StringTransport()
                protocol.makeConnection(transport)
                return protocol
            info.connectQueue.append(result)
            if fireImmediately:
                result.callback(None)
            return result
    info = ConnectInformation()
    return info, ClientTestEndpoint()



def catchLogs(testCase, logPublisher=globalLogPublisher):
    """
    Catch the global log stream.

    @param testCase: The test case to add a cleanup to.

    @param logPublisher: the log publisher to add and remove observers for.

    @return: a 0-argument callable that returns a list of textual log messages
        for comparison.
    @rtype: L{list} of L{unicode}
    """
    logs = []
    logPublisher.addObserver(logs.append)
    testCase.addCleanup(lambda: logPublisher.removeObserver(logs.append))
    return lambda: [formatEvent(event) for event in logs]



class ReconnectingClientServiceTests(TestCase):
    """
    Tests for L{ReconnectingClientService}.
    """

    def makeReconnector(self, fireImmediately=True, startService=True, **kw):
        """
        Create a L{ReconnectingClientService} along with a
        L{ConnectInformation} indicating the connections in progress on its
        endpoint.
        """
        nkw = {}
        nkw.update(clock=Clock())
        nkw.update(kw)
        cq, endpoint = endpointForTesting(fireImmediately=fireImmediately)
        factory = Factory.forProtocol(Protocol)
        service = ReconnectingClientService(endpoint, factory, **nkw)
        def stop():
            service._protocol = None
            if service.running:
                service.stopService()
        self.addCleanup(stop)
        if startService:
            service.startService()
        return cq, service


    def test_startService(self):
        """
        When the service is started, a connection attempt is made.
        """
        cq, service = self.makeReconnector(fireImmediately=False)
        self.assertEqual(len(cq.connectQueue), 1)


    def test_stopServiceWhileConnected(self):
        """
        When the service is stopped, no further connect attempts are made.  The
        returned L{Deferred} fires when all outstanding connections have been
        stopped.
        """
        cq, service = self.makeReconnector()
        d = service.stopService()
        self.assertNoResult(d)
        protocol = cq.constructedProtocols[0]
        self.assertEqual(protocol.transport.disconnecting, True)
        protocol.connectionLost(Failure(Exception()))
        self.successResultOf(d)


    def test_stopServiceWhileRetrying(self):
        """
        When the service is stopped while retrying, the retry is cancelled.
        """
        clock = Clock()
        cq, service = self.makeReconnector(fireImmediately=False, clock=clock)
        cq.connectQueue[0].errback(Exception())
        clock.advance(100)
        self.assertEqual(len(cq.connectQueue), 2)
        d = service.stopService()
        cq.connectQueue[1].errback(Exception())
        self.successResultOf(d)


    def test_stopServiceWhileConnecting(self):
        """
        When the service is stopped while initially connecting, the connection
        attempt is cancelled.
        """
        clock = Clock()
        cq, service = self.makeReconnector(fireImmediately=False, clock=clock)
        self.assertEqual(len(cq.connectQueue), 1)
        self.assertNoResult(cq.connectQueue[0])
        messages = catchLogs(self)
        d = service.stopService()
        self.successResultOf(d)
        [msg] = messages()
        self.assertSubstring(
            "Cancelling connection attempt to endpoint <twisted.application"
            ".test.test_internet.ClientTestEndpoint object",
            msg
        )


    def test_clientConnected(self):
        """
        When a client connects, the service keeps a reference to the new
        protocol and resets the delay.
        """
        clock = Clock()
        cq, service = self.makeReconnector(clock=clock)
        self.assertEqual(clock.getDelayedCalls(), [])
        self.assertIdentical(service._protocol, cq.constructedProtocols[0])


    def test_clientConnectionFailed(self):
        """
        When a client connection fails, the service removes its reference
        to the protocol and tries again after a timeout.
        """
        clock = Clock()
        cq, service = self.makeReconnector(fireImmediately=False,
                                           clock=clock)
        self.assertEqual(len(cq.connectQueue), 1)
        cq.connectQueue[0].errback(Failure(Exception()))
        self.assertIdentical(service._protocol, None)
        clock.advance(100.)
        self.assertEqual(len(cq.connectQueue), 2)


    def test_clientConnectionLost(self):
        """
        When a client connection is lost, the service removes its reference
        to the protocol and calls retry.
        """
        cq, service = self.makeReconnector()
        service.startService()
        cq.constructedProtocols[0].connectionLost(Failure(Exception()))
        self.assertIdentical(service._protocol, None)


    def test_clientConnectionLostWhileStopping(self):
        """
        When a client connection is lost while the service is stopping, the
        protocol stopping deferred is called and the reference to the protocol
        is removed.
        """
        cq, service = self.makeReconnector()
        d = service.stopService()
        cq.constructedProtocols[0].connectionLost(Failure(Exception()))
        self.assertIdentical(service._protocol, None)
        self.assertIdentical(service._protocolStoppingDeferred, None)
        self.assertTrue(d.called)
