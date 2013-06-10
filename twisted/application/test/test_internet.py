# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for (new code in) L{twisted.application.internet}.
"""

import random

from zope.interface import implements, implementer
from zope.interface.verify import verifyClass

from twisted.internet.protocol import Factory, Protocol
from twisted.internet.task import Clock
from twisted.trial.unittest import TestCase
from twisted.application import internet
from twisted.application.internet import (
        StreamServerEndpointService, TimerService, ReconnectingClientService)
from twisted.internet.interfaces import (
        IStreamServerEndpoint, IStreamClientEndpoint, IListeningPort,
        ITransport)
from twisted.internet.defer import Deferred, CancelledError, inlineCallbacks
from twisted.internet import task
from twisted.python.failure import Failure
from twisted.python import log

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
        return [" ".join(msg['message']) for msg in self.logs
                if not msg["isError"]]

    def _gather_logs(self, event_dict):
        self.logs.append(event_dict)

    def attach(self):
        log.theLogPublisher.addObserver(self._gather_logs)

    def detach(self):
        log.theLogPublisher.removeObserver(self._gather_logs)


class ReconnectingClientServiceTestCase(TestCase):
    def make_reconnector(self, **kw):
        e = ClientTestEndpoint()
        f = object()
        s = ReconnectingClientService(e, f)
        for key, value in kw.items():
            setattr(s, key, value)
        self.addCleanup(s.stopService)
        return s, e, f


    def patch_reconnector(self, method):
        mock = MockRecorder(self)
        self.patch(ReconnectingClientService, method, mock)
        return mock


    def test_startService(self):
        retry = self.patch_reconnector('retry')
        s = ReconnectingClientService(object(), object())
        s.startService()
        self.assertTrue(s.continueTrying)
        retry.assertCalledOnce(delay=0.0)


    @inlineCallbacks
    def test_stopService(self):
        s, e, f = self.make_reconnector(continueTrying=True)
        yield s.stopService()
        self.assertEqual(s.continueTrying, False)


    @inlineCallbacks
    def test_stopServiceWhileRetrying(self):
        s, e, f = self.make_reconnector()
        clock = Clock()
        r = s._delayedRetry = clock.callLater(1.0, lambda: None)
        yield s.stopService()
        self.assertTrue(r.cancelled)
        self.assertIdentical(s._delayedRetry, None)


    @inlineCallbacks
    def test_stopServiceWhileConnecting(self):
        errs = []
        s, e, f = self.make_reconnector()
        s._connectingDeferred = Deferred().addErrback(errs.append)
        yield s.stopService()
        [failure] = errs
        self.assertTrue(failure.check(CancelledError))


    @inlineCallbacks
    def test_stopServiceWhileConnected(self):
        s, e, f = self.make_reconnector()
        s._protocol = DummyProtocol()
        s._protocol.transport = DummyTransport()
        d = s.stopService()
        self.assertFalse(d.called)
        self.assertTrue(s._protocol.transport.lose_connection_called.called)
        s.clientConnectionLost(Failure(Exception()))
        yield d


    def test_clientConnected(self):
        reset = self.patch_reconnector('resetDelay')
        s = ReconnectingClientService(object(), object())
        p = object()
        s.clientConnected(p)
        self.assertIdentical(s._protocol, p)
        reset.assertCalledOnce()


    def test_clientConnectionFailed(self):
        retry = self.patch_reconnector('retry')
        s = ReconnectingClientService(object(), object())
        s.clientConnectionFailed(Failure(Exception()))
        self.assertIdentical(s._protocol, None)
        retry.assertCalledOnce()


    def test_clientConnectionLost(self):
        retry = self.patch_reconnector('retry')
        s = ReconnectingClientService(object(), object())
        s.clientConnectionLost(Failure(Exception()))
        self.assertIdentical(s._protocol, None)
        retry.assertCalledOnce()


    def test_clientConnectionLostWhileStopping(self):
        retry = self.patch_reconnector('retry')
        s = ReconnectingClientService(object(), object())
        d = s._protocolStoppingDeferred = Deferred()
        s.clientConnectionLost(Failure(Exception()))
        self.assertIdentical(s._protocol, None)
        self.assertIdentical(s._protocolStoppingDeferred, None)
        retry.assertCalledOnce()
        self.assertTrue(d.called)


    def test_retryAbortsWhenStopping(self):
        s, e, f = self.make_reconnector(continueTrying=False)
        s.retry()
        self.assertEqual(s.retries, 0)


    def test_noisyRetryAbortsWhenStopping(self):
        s, e, f = self.make_reconnector(noisy=True, continueTrying=False)
        lc = LogCatcher(self)
        s.retry()
        [msg] = lc.messages()
        self.assertEqual(s.retries, 0)
        self.assertSubstring("Abandoning <twisted.application.test"
                             ".test_internet.ClientTestEndpoint object at",
                             msg)
        self.assertSubstring("on explicit request", msg)


    def test_retryAbortsWhenMaxRetriesExceeded(self):
        s, e, f = self.make_reconnector(maxRetries=5, continueTrying=True)
        s.retries = 5
        s.retry()
        self.assertEqual(s.retries, 5)


    def test_noisyRetryAbortsWhenMaxRetriesExceeded(self):
        s, e, f = self.make_reconnector(noisy=True, maxRetries=5,
                                        continueTrying=True)
        s.retries = 5
        lc = LogCatcher(self)
        s.retry()
        [msg] = lc.messages()
        self.assertEqual(s.retries, 5)
        self.assertSubstring("Abandoning <twisted.application.test"
                             ".test_internet.ClientTestEndpoint object at",
                             msg)
        self.assertSubstring("after 5 retries", msg)


    def test_retryWithExplicitDelay(self):
        s, e, f = self.make_reconnector(continueTrying=True, clock=Clock())
        s.retry(delay=1.5)
        [delayed] = s.clock.calls
        self.assertEqual(delayed.time, 1.5)


    def test_noisyRetryWithExplicitDelay(self):
        s, e, f = self.make_reconnector(noisy=True, continueTrying=True,
                                        clock=Clock())
        lc = LogCatcher(self)
        s.retry(delay=1.5)
        [msg] = lc.messages()
        [delayed] = s.clock.calls
        self.assertEqual(delayed.time, 1.5)
        self.assertSubstring("Will retry <twisted.application.test"
                             ".test_internet.ClientTestEndpoint object at",
                             msg)
        self.assertSubstring("in 1.5 seconds", msg)


    def test_retryDelayAdvances(self):
        s, e, f = self.make_reconnector(jitter=None, continueTrying=True,
                                        clock=Clock())
        s.retry()
        [delayed] = s.clock.calls
        self.assertAlmostEqual(delayed.time, s.factor)
        self.assertAlmostEqual(s.delay, s.factor)


    def test_retryDelayIsCappedByMaxDelay(self):
        s, e, f = self.make_reconnector(jitter=None, continueTrying=True,
                                        clock=Clock(), maxDelay=1.5)
        s.retry()
        [delayed] = s.clock.calls
        self.assertAlmostEqual(delayed.time, 1.5)
        self.assertAlmostEqual(s.delay, 1.5)


    def test_retryWithJitter(self):
        normal = MockRecorder(self, result=2.0)
        self.patch(random, 'normalvariate', normal)
        s, e, f = self.make_reconnector(continueTrying=True, clock=Clock())
        s.retry()
        [delayed] = s.clock.calls
        self.assertAlmostEqual(delayed.time, 2.0)
        self.assertAlmostEqual(s.delay, 2.0)
        normal.assertCalledOnce(s.factor, s.factor * s.jitter)


    @inlineCallbacks
    def test_retryWhenConnectionSucceeds(self):
        connected = self.patch_reconnector('clientConnected')
        s, e, f = self.make_reconnector(continueTrying=True, clock=Clock())

        s.retry(delay=1.0)
        connected.assertNotCalled()

        s.clock.advance(1.0)
        wrapped_f = yield e.connect_called
        self.assertEqual(wrapped_f.protocolFactory, f)
        connected.assertNotCalled()

        p = DummyProtocol()
        e.connected.callback(p)
        connected.assertCalledOnce(p)


    @inlineCallbacks
    def test_retryWhenConnectionFails(self):
        connection_failed = self.patch_reconnector('clientConnectionFailed')
        s, e, f = self.make_reconnector(continueTrying=True, clock=Clock())

        s.retry(delay=1.0)
        connection_failed.assertNotCalled()

        s.clock.advance(1.0)
        wrapped_f = yield e.connect_called
        self.assertEqual(wrapped_f.protocolFactory, f)
        connection_failed.assertNotCalled()

        failure = Failure(Exception())
        e.connected.errback(failure)
        connection_failed.assertCalledOnce(failure)


    def test_resetDelay(self):
        initial_delay = ReconnectingClientService.initialDelay
        s = ReconnectingClientService(object(), object())
        s.delay, s.retries = initial_delay + 1, 5
        s.resetDelay()
        self.assertEqual(s.delay, initial_delay)
        self.assertEqual(s.retries, 0)


    def test_parametrizedClock(self):
        """
        The clock used by L{ReconnectingClientFactory} can be parametrized, so
        that one can cleanly test reconnections.
        """
        clock = Clock()
        s, e, f = self.make_reconnector()
        s.clock = clock
        s.startService()
        self.assertEqual(len(clock.calls), 1)
