# Copyright (c) 2010 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for (new code in) L{twisted.application.internet}.
"""


from zope.interface import implements
from zope.interface.verify import verifyClass

from twisted.internet.protocol import Factory
from twisted.trial.unittest import TestCase
from twisted.application.internet import StreamServerEndpointService
from twisted.internet.interfaces import IStreamServerEndpoint, IListeningPort
from twisted.internet.defer import Deferred, CancelledError

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
    """

    implements(IStreamServerEndpoint)

    result = None
    factory = None
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


    def test_startServiceUnstarted(self):
        """
        L{StreamServerEndpointService.startService} sets the C{running} flag,
        and calls its endpoint's C{listen} method with its factory, if it
        has not yet been started.
        """
        self.svc.startService()
        self.assertIdentical(self.factory, self.fakeServer.factory)
        self.assertEquals(self.svc.running, True)


    def test_startServiceStarted(self):
        """
        L{StreamServerEndpointService.startService} sets the C{running} flag,
        but nothing else, if the service has already been started.
        """
        self.test_privilegedStartService()
        self.svc.startService()
        self.assertEquals(self.fakeServer.listenAttempts, 1)
        self.assertEquals(self.svc.running, True)


    def test_stopService(self):
        """
        L{StreamServerEndpointService.stopService} calls C{stopListening} on the
        L{IListeningPort} returned from its endpoint, returns the C{Deferred}
        from stopService, and sets C{running} to C{False}.
        """
        self.svc.privilegedStartService()
        self.fakeServer.startedListening()
        # Ensure running gets set to true
        self.svc.startService()
        result = self.svc.stopService()
        l = []
        result.addCallback(l.append)
        self.assertEquals(len(l), 0)
        self.fakeServer.stoppedListening()
        self.assertEquals(len(l), 1)
        self.assertFalse(self.svc.running)


    def test_stopServiceBeforeStartFinished(self):
        """
        L{StreamServerEndpointService.stopService} cancels the L{Deferred}
        returned by C{listen}.
        """
        listeningErrors = []
        def catchCancel(failure):
            listeningErrors.append(failure.type)
            return failure
        self.svc.privilegedStartService()
        self.fakeServer.result.addErrback(catchCancel)
        self.assertEquals(listeningErrors, [])
        result = self.svc.stopService()
        self.assertEquals(listeningErrors, [CancelledError])
        l = []
        result.addCallback(l.append)
        self.assertEquals(l, [None])


    def test_stopServiceCancelStartError(self):
        """
        L{StreamServerEndpointService.stopService} cancels the L{Deferred}
        returned by C{listen}, but will propagate errors other than
        L{CancelledError}.
        """
        self.fakeServer.cancelException = ZeroDivisionError()
        listeningErrors = []
        def catchCancel(failure):
            listeningErrors.append(failure.type)
            return failure
        self.svc.privilegedStartService()
        self.fakeServer.result.addErrback(catchCancel)
        self.assertEquals(listeningErrors, [])
        result = self.svc.stopService()
        self.assertEquals(listeningErrors, [ZeroDivisionError])
        stoppingErrors = []
        result.addErrback(lambda f: stoppingErrors.append(f.type))
        self.assertEquals(stoppingErrors,
                          [ZeroDivisionError])


