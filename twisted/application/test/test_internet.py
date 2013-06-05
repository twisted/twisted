# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for (new code in) L{twisted.application.internet}.
"""


from zope.interface import implements
from zope.interface.verify import verifyClass

from twisted.internet.protocol import Factory, Protocol
from twisted.trial.unittest import TestCase
from twisted.application.internet import StreamServerEndpointService, \
    PersistentClientSerivce
from twisted.internet.interfaces import IStreamServerEndpoint, IListeningPort, IStreamClientEndpoint
from twisted.internet.defer import Deferred, CancelledError, succeed


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

    implements(IStreamServerEndpoint)

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



class FakePort(object):
    """
    Fake L{IListeningPort} implementation.

    @ivar deferred: The L{Deferred} returned by C{stopListening}.
    """

    implements(IListeningPort)

    deferred = None

    def stopListening(self):
        self.deferred = Deferred()
        return self.deferred

verifyClass(IStreamServerEndpoint, FakeServer)



class TestEndpointService(TestCase):
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
        since L{IStreamServerEndpoint.listen} may fail asynchronously, it is
        a bad idea to rely on this behavior.
        """
        self.fakeServer.failImmediately = ZeroDivisionError()
        self.svc._raiseSynchronously = True
        self.assertRaises(ZeroDivisionError, thunk or self.svc.startService)


    def test_synchronousRaisePrivileged(self):
        """
        L{StreamServerEndpointService.privilegedStartService} should behave the
        same as C{startService} with respect to
        L{TestEndpointService.test_synchronousRaiseRaisesSynchronously}.
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


class FakeClientEndpoint(object):

    implements(IStreamClientEndpoint)

    def __init__(self, transport):
        self.transport = transport
        self.connectCount = 0

    def connect(self, protocolFactory):
        protocol = protocolFactory.buildProtocol("addr.of.lies")
        protocol.makeConnection(self.transport)
        self.connectCount += 1
        return succeed(protocol)


verifyClass(IStreamClientEndpoint, FakeClientEndpoint)


class CountingProtocolFactory(Factory):
    def __init__(self, protocol):
        self.protocol = protocol
        self.serialNumber = 0

    def buildProtocol(self, addr):
        protocol = Factory.buildProtocol(self, addr)
        protocol.serialNumber = self.serialNumber
        self.serialNumber += 1
        return protocol


class LoserProtocol(Protocol):
    def __init__(self):
        self._loserReasons = []

    def connectionLost(self, reason):
        self._loserReasons.append(reason)


class TestPersistentClientService(TestCase):

    def setUp(self):
        self.transport = "fake.transport"
        self.endpoint = FakeClientEndpoint(self.transport)
        self.factory = CountingProtocolFactory(Protocol)
        self.reactor = "REACTOR"
        self.nextDelay = lambda now, lastSuccess, lastFailure: 5
        self.pcs = PersistentClientSerivce(
            self.endpoint, self.factory, self.reactor, self.nextDelay)


    def test_constructor(self):
        self.assertIdentical(self.endpoint, self.pcs.endpoint)
        self.assertIdentical(self.factory, self.pcs.factory)


    def test_startService(self):
        """Connection happens upon service start."""
        result = []
        self.pcs._onConnect = lambda protocol: result.append(protocol)
        self.assertEqual(self.endpoint.connectCount, 0)
        self.pcs.startService()
        self.assertEqual(self.endpoint.connectCount, 1)

        self.assertEqual(len(result), 1)
        protocol = result[0]

        self.assertIsInstance(protocol, self.factory.protocol)

        # the transport is connected to the endpoint
        self.assertEqual(protocol.connected, 1)
        self.assertEqual(protocol.transport, self.transport)
        self.assertEqual(protocol.serialNumber, 0)


    def test_connectedProtocolWithoutCurrentConnection(self):
        """connectedProtocol returns a protocol connected to our endpoint"""
        # connectedProtocol does not have a result before startService
        dProtocol = self.pcs.connectedProtocol()
        self.assertNoResult(dProtocol)
        # TODO: the assert eats dProtocol, until we merge forward to get #6291

        dProtocol = self.pcs.connectedProtocol()
        dProtocol2 = self.pcs.connectedProtocol()
        self.assertNotIdentical(dProtocol, dProtocol2,
            "multiple callers should get independent deferreds")

        # trigger connection callback, as done by startService
        expectedProtocol = object()
        self.pcs._onConnect(expectedProtocol)

        protocol = self.successResultOf(dProtocol)
        protocol2 = self.successResultOf(dProtocol2)
        self.assertIdentical(protocol, expectedProtocol)
        self.assertIdentical(protocol2, expectedProtocol)


    def test_connectedProtocolAlreadyConnected(self):
        """connectedProtocol returns immediately with existing value"""
        # set us up as if we already have an active protocol
        expectedProtocol = object()
        self.pcs._currentProtocol = expectedProtocol
        protocol = self.successResultOf(self.pcs.connectedProtocol())
        self.assertIdentical(protocol, expectedProtocol)


    def test_hookConnectionLost(self):
        """Modify the given Protocol so PCS._onConnectionLost is called."""
        results = []
        protocol = LoserProtocol()
        proto2 = self.pcs._hookConnectionLost(protocol)
        self.assertIdentical(protocol, proto2)
        self.pcs._onConnectionLost = lambda reason: results.append(reason)
        protocol.connectionLost("obvious")

        # check the original implementation still fired
        self.assertEqual(protocol._loserReasons, ["obvious"])
        # as well as our hook
        self.assertEqual(results, ["obvious"])


    def test_lostConnectionMakesNewConnection(self):
        """
        After the first connection is lost, connectedProtocol returns a
        new protocol instance.
        """
        self.pcs.startService()
        protocol = self.successResultOf(self.pcs.connectedProtocol())
        self.assertEqual(protocol.serialNumber, 0)
        protocol.connectionLost("reasons")
        protocol = self.successResultOf(self.pcs.connectedProtocol())
        self.assertEqual(protocol.serialNumber, 1)


    def test_endpointConnectionError(self):
        # TODO: when endpoint.connect results in ConnectError, what then?
        raise NotImplementedError()


    def test_nextDelayInputs(self):
        # TODO nextDelay receives times of previous success and failure.
        raise NotImplementedError()


    def test_stopService(self):
        # TODO: test stopService while connection is up
        # TODO: test stopService during reconnect delay
        raise NotImplementedError()


    test_endpointConnectionError.todo = "TODO"
    test_nextDelayInputs.todo = "TODO"
    test_stopService.todo = "TODO"
