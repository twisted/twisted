# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for (new code in) L{twisted.application.internet}.
"""

import pickle
import random

from zope.interface import implements, implementer
from zope.interface.verify import verifyClass

from twisted.internet.protocol import Factory, Protocol
from twisted.internet.task import Clock
from twisted.trial.unittest import TestCase
from twisted.application import internet
from twisted.application.internet import (
        StreamServerEndpointService, TimerService, ReconnectingClientService)
from twisted.internet.interfaces import IStreamServerEndpoint, IListeningPort
from twisted.internet.defer import Deferred, CancelledError
from twisted.internet.interfaces import (
        IStreamServerEndpoint, IStreamClientEndpoint, IListeningPort,
        ITransport)
from twisted.internet.defer import Deferred, CancelledError, inlineCallbacks
from twisted.internet import task
from twisted.python.failure import Failure
from twisted.python import log


def fakeTargetFunction():
    """
    A fake target function for testing TimerService which does nothing.
    """
    pass



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



class TestTimerService(TestCase):
    """
    Tests for L{twisted.application.internet.TimerService}.

    @type timer: L{TimerService}
    @ivar timer: service to test

    @type clock: L{task.Clock}
    @ivar clock: source of time

    @type deferred: L{Deferred}
    @ivar deferred: deferred returned by L{TestTimerService.call}.
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



@implementer(IStreamClientEndpoint)
class ClientTestEndpoint(object):
    def __init__(self):
        self.connect_called = Deferred()
        self.connected = Deferred()

    def connect(self, factory):
        self.connect_called.callback(factory)
        return self.connected



class MockRecorder(object):
    def __init__(self, test_case, result=None):
        self._test_case = test_case
        self._calls = []
        self._result = result

    def assertCalledOnce(self, *args, **kw):
        self._test_case.assertEqual(self._calls, [(args, kw)])

    def assertNotCalled(self):
        self._test_case.assertEqual(self._calls, [])

    def __call__(self, *args, **kw):
        self._calls.append((args, kw))
        return self._result



class DummyProtocol(Protocol):
    pass



@implementer(ITransport)
class DummyTransport(object):

    def __init__(self):
        self.lose_connection_called = Deferred()

    def loseConnection(self):
        self.lose_connection_called.callback(None)


class LogCatcher(object):
    def __init__(self, test_case):
        self.logs = []
        self.attach()
        test_case.addCleanup(self.detach)

    def messages(self):
        return [msg['format'] % msg for msg in self.logs
                if not msg["isError"]]

    def _gather_logs(self, event_dict):
        self.logs.append(event_dict)

    def attach(self):
        log.theLogPublisher.addObserver(self._gather_logs)

    def detach(self):
        log.theLogPublisher.removeObserver(self._gather_logs)


class ReconnectingClientServiceTestCase(TestCase):
    def make_reconnector(self, continueTrying=None, **kw):
        endpoint = ClientTestEndpoint()
        factory = object()
        service = ReconnectingClientService(endpoint, factory, **kw)
        if continueTrying is not None:
            service.continueTrying = continueTrying

        def stop():
            service._protocol = None
            return service.stopService()

        self.addCleanup(stop)

        return service


    def patch_reconnector(self, service, method):
        mock = MockRecorder(self)
        setattr(service, method, mock)
        return mock


    def test_startService(self):
        """
        When the service is started, continueTrying is set to True and retry
        is called.
        """
        service = self.make_reconnector()
        retry = self.patch_reconnector(service, 'retry')
        service.startService()
        self.assertTrue(service.continueTrying)
        retry.assertCalledOnce(delay=0.0)


    @inlineCallbacks
    def test_stopService(self):
        """
        When the service is stopped, continueTrying is set to False.
        """
        service = self.make_reconnector(continueTrying=True)
        yield service.stopService()
        self.assertEqual(service.continueTrying, False)


    @inlineCallbacks
    def test_stopServiceWhileRetrying(self):
        """
        When the service is stopped while retrying, the retry is cancelled.
        """
        service = self.make_reconnector()
        clock = Clock()
        r = service._delayedRetry = clock.callLater(1.0, lambda: None)
        yield service.stopService()
        self.assertTrue(r.cancelled)
        self.assertIdentical(service._delayedRetry, None)


    @inlineCallbacks
    def test_stopServiceWhileConnecting(self):
        """
        When the service is stopped while connecting, the connection
        attempt is cancelled.
        """
        service = self.make_reconnector()
        connectingDeferred = service._connectingDeferred = Deferred()
        lc = LogCatcher(self)
        yield service.stopService()
        self.assertEqual(self.successResultOf(connectingDeferred), None)
        self.assertEqual(service._connectingDeferred, None)
        [msg] = lc.messages()
        self.assertSubstring(
            "Cancelling connection attempt to endpoint <twisted.application"
            ".test.test_internet.ClientTestEndpoint object",
            msg)

    @inlineCallbacks
    def test_stopServiceWhileConnected(self):
        """
        When the service is stopped while connected, the connections is
        closed.
        """
        service = self.make_reconnector()
        service._protocol = DummyProtocol()
        service._protocol.transport = DummyTransport()
        d = service.stopService()
        self.assertFalse(d.called)
        self.assertTrue(
            service._protocol.transport.lose_connection_called.called)
        service.clientConnectionLost(Failure(Exception()))
        yield d


    def test_clientConnected(self):
        """
        When a client connects, the service keeps a reference to the new
        protocol and resets the delay.
        """
        service = self.make_reconnector()
        reset = self.patch_reconnector(service, 'resetDelay')
        protocol = DummyProtocol()
        protocol.transport = DummyTransport()
        service.clientConnected(protocol)
        self.assertIdentical(service._protocol, protocol)
        reset.assertCalledOnce()


    def test_clientConnectionFailed(self):
        """
        When a client connection fails, the service removes its reference
        to the protocol and calls retry.
        """
        service = self.make_reconnector()
        retry = self.patch_reconnector(service, 'retry')
        service.clientConnectionFailed(Failure(Exception()))
        self.assertIdentical(service._protocol, None)
        retry.assertCalledOnce()


    def test_clientConnectionLost(self):
        """
        When a client connection is lost, the service removes its reference
        to the protocol and calls retry.
        """
        service = self.make_reconnector()
        retry = self.patch_reconnector(service, 'retry')
        service.clientConnectionLost(Failure(Exception()))
        self.assertIdentical(service._protocol, None)
        retry.assertCalledOnce()


    def test_clientConnectionLostWhileStopping(self):
        """
        When a client connection is lost while the service is stopping, the
        protocol stopping deferred is called and the reference to the protocol
        is removed.
        """
        service = self.make_reconnector()
        retry = self.patch_reconnector(service, 'retry')
        d = service._protocolStoppingDeferred = Deferred()
        service.clientConnectionLost(Failure(Exception()))
        self.assertIdentical(service._protocol, None)
        self.assertIdentical(service._protocolStoppingDeferred, None)
        retry.assertCalledOnce()
        self.assertTrue(d.called)


    def test_retryAbortsWhenStopping(self):
        """
        When retry is called while stopping the service, no retry occurs.
        """
        service = self.make_reconnector(continueTrying=False)
        service.retry()
        self.assertEqual(service.retries, 0)


    def test_noisyRetryAbortsWhenStopping(self):
        """
        When retry is called while stopping the service and the service
        is noisy, no retry occurs and the lack of retry is logged.
        """
        service = self.make_reconnector(noisy=True, continueTrying=False)
        lc = LogCatcher(self)
        service.retry()
        [msg] = lc.messages()
        self.assertEqual(service.retries, 0)
        self.assertSubstring("Abandoning <twisted.application.test"
                             ".test_internet.ClientTestEndpoint object at",
                             msg)
        self.assertSubstring("on explicit request", msg)


    def test_retryAbortsWhenMaxRetriesExceeded(self):
        """
        When retry is called after the maximum number of retries has been
        reached, no retry occours.
        """
        service = self.make_reconnector(maxRetries=5, continueTrying=True)
        service.retries = 5
        service.retry()
        self.assertEqual(service.retries, 5)


    def test_noisyRetryAbortsWhenMaxRetriesExceeded(self):
        """
        When retry is called after the maximum number of retries has been
        reached and the service is noisy, no retry occours and the lack of
        retry is logged.
        """
        service = self.make_reconnector(noisy=True, maxRetries=5,
                                        continueTrying=True)
        service.retries = 5
        lc = LogCatcher(self)
        service.retry()
        [msg] = lc.messages()
        self.assertEqual(service.retries, 5)
        self.assertSubstring("Abandoning <twisted.application.test"
                             ".test_internet.ClientTestEndpoint object at",
                             msg)
        self.assertSubstring("after 5 retries", msg)


    def test_retryWithExplicitDelay(self):
        """
        When retry is called with an explicit delay, the retry is scheduled
        with the specified delay.
        """
        service = self.make_reconnector(continueTrying=True, clock=Clock())
        service.retry(delay=1.5)
        [delayed] = service.clock.calls
        self.assertEqual(delayed.time, 1.5)


    def test_noisyRetryWithExplicitDelay(self):
        """
        When retry is called with an explicit delay and the service is noisy,
        the retry is scheduled with the specified delay and the scheduling of
        the retry is logged.
        """
        service = self.make_reconnector(noisy=True, continueTrying=True,
                                        clock=Clock())
        lc = LogCatcher(self)
        service.retry(delay=1.5)
        [msg] = lc.messages()
        [delayed] = service.clock.calls
        self.assertEqual(delayed.time, 1.5)
        self.assertSubstring("Will retry <twisted.application.test"
                             ".test_internet.ClientTestEndpoint object at",
                             msg)
        self.assertSubstring("in 1.5 seconds", msg)


    def test_retryDelayAdvances(self):
        """
        When retry is called, the current delay amount is updated.
        """
        service = self.make_reconnector(jitter=None, continueTrying=True,
                                        clock=Clock())
        service.retry()
        [delayed] = service.clock.calls
        self.assertAlmostEqual(delayed.time, service.factor)
        self.assertAlmostEqual(service.delay, service.factor)


    def test_retryDelayIsCappedByMaxDelay(self):
        """
        When retry is called after the maximum delay is reached, the
        current delay amount is capped at the maximum delay.
        """
        service = self.make_reconnector(jitter=None, continueTrying=True,
                                        clock=Clock(), maxDelay=1.5)
        service.retry()
        [delayed] = service.clock.calls
        self.assertAlmostEqual(delayed.time, 1.5)
        self.assertAlmostEqual(service.delay, 1.5)


    def test_retryWithJitter(self):
        """
        When retry is called, jitter is applied to the delay.
        """
        normal = MockRecorder(self, result=2.0)
        self.patch(random, 'normalvariate', normal)
        service = self.make_reconnector(continueTrying=True, clock=Clock())
        service.retry()
        [delayed] = service.clock.calls
        self.assertAlmostEqual(delayed.time, 2.0)
        self.assertAlmostEqual(service.delay, 2.0)
        normal.assertCalledOnce(
            service.factor, service.factor * service.jitter)


    @inlineCallbacks
    def test_retryWhenConnectionSucceeds(self):
        """
        When a reconnect attempt succeeds, clientConnected is called.
        """
        service = self.make_reconnector(continueTrying=True, clock=Clock())
        connected = self.patch_reconnector(service, 'clientConnected')

        service.retry(delay=1.0)
        connected.assertNotCalled()

        service.clock.advance(1.0)
        wrapped_f = yield service.endpoint.connect_called
        self.assertEqual(wrapped_f.protocolFactory, service.factory)
        connected.assertNotCalled()

        p = DummyProtocol()
        service.endpoint.connected.callback(p)
        connected.assertCalledOnce(p)


    @inlineCallbacks
    def test_retryWhenConnectionFails(self):
        """
        When a reconnect attempt fails, clientConnectionFailed is called.
        """
        service = self.make_reconnector(continueTrying=True, clock=Clock())
        connection_failed = self.patch_reconnector(
            service, 'clientConnectionFailed')

        service.retry(delay=1.0)
        connection_failed.assertNotCalled()

        service.clock.advance(1.0)
        wrapped_f = yield service.endpoint.connect_called
        self.assertEqual(wrapped_f.protocolFactory, service.factory)
        connection_failed.assertNotCalled()

        failure = Failure(Exception())
        service.endpoint.connected.errback(failure)
        connection_failed.assertCalledOnce(failure)


    def test_resetDelay(self):
        """
        When resetDelay is called, the delay is reset.
        """
        service = self.make_reconnector()
        initial_delay = 1.0
        service.delay, service.retries = initial_delay + 1, 5
        service.resetDelay()
        self.assertEqual(service.delay, initial_delay)
        self.assertEqual(service.retries, 0)


    def test_parametrizedClock(self):
        """
        The clock used by L{ReconnectingClientFactory} can be parametrized, so
        that one can cleanly test reconnections.
        """
        clock = Clock()
        service = self.make_reconnector()
        service.clock = clock
        service.startService()
        self.assertEqual(len(clock.calls), 1)
