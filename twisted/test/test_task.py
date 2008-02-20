# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.python.compat import set

from twisted.trial import unittest

from twisted.internet import interfaces, task, reactor, defer, error

# Be compatible with any jerks who used our private stuff
Clock = task.Clock

from twisted.python import failure


class TestableLoopingCall(task.LoopingCall):
    def __init__(self, clock, *a, **kw):
        super(TestableLoopingCall, self).__init__(*a, **kw)
        self.clock = clock



class TestException(Exception):
    pass



class ClockTestCase(unittest.TestCase):
    """
    Test the non-wallclock based clock implementation.
    """
    def testSeconds(self):
        """
        Test that the L{seconds} method of the fake clock returns fake time.
        """
        c = task.Clock()
        self.assertEquals(c.seconds(), 0)


    def testCallLater(self):
        """
        Test that calls can be scheduled for later with the fake clock and
        hands back an L{IDelayedCall}.
        """
        c = task.Clock()
        call = c.callLater(1, lambda a, b: None, 1, b=2)
        self.failUnless(interfaces.IDelayedCall.providedBy(call))
        self.assertEquals(call.getTime(), 1)
        self.failUnless(call.active())


    def testCallLaterCancelled(self):
        """
        Test that calls can be cancelled.
        """
        c = task.Clock()
        call = c.callLater(1, lambda a, b: None, 1, b=2)
        call.cancel()
        self.failIf(call.active())


    def test_callLaterOrdering(self):
        """
        Test that the DelayedCall returned is not one previously
        created.
        """
        c = task.Clock()
        call1 = c.callLater(10, lambda a, b: None, 1, b=2)
        call2 = c.callLater(1, lambda a, b: None, 3, b=4)
        self.failIf(call1 is call2)


    def testAdvance(self):
        """
        Test that advancing the clock will fire some calls.
        """
        events = []
        c = task.Clock()
        call = c.callLater(2, lambda: events.append(None))
        c.advance(1)
        self.assertEquals(events, [])
        c.advance(1)
        self.assertEquals(events, [None])
        self.failIf(call.active())


    def testAdvanceCancel(self):
        """
        Test attemping to cancel the call in a callback.

        AlreadyCalled should be raised, not for example a ValueError from
        removing the call from Clock.calls. This requires call.called to be
        set before the callback is called.
        """
        c = task.Clock()
        def cb():
            self.assertRaises(error.AlreadyCalled, call.cancel)
        call = c.callLater(1, cb)
        c.advance(1)


    def testCallLaterDelayed(self):
        """
        Test that calls can be delayed.
        """
        events = []
        c = task.Clock()
        call = c.callLater(1, lambda a, b: events.append((a, b)), 1, b=2)
        call.delay(1)
        self.assertEquals(call.getTime(), 2)
        c.advance(1.5)
        self.assertEquals(events, [])
        c.advance(1.0)
        self.assertEquals(events, [(1, 2)])


    def testCallLaterResetLater(self):
        """
        Test that calls can have their time reset to a later time.
        """
        events = []
        c = task.Clock()
        call = c.callLater(2, lambda a, b: events.append((a, b)), 1, b=2)
        c.advance(1)
        call.reset(3)
        self.assertEquals(call.getTime(), 4)
        c.advance(2)
        self.assertEquals(events, [])
        c.advance(1)
        self.assertEquals(events, [(1, 2)])


    def testCallLaterResetSooner(self):
        """
        Test that calls can have their time reset to an earlier time.
        """
        events = []
        c = task.Clock()
        call = c.callLater(4, lambda a, b: events.append((a, b)), 1, b=2)
        call.reset(3)
        self.assertEquals(call.getTime(), 3)
        c.advance(3)
        self.assertEquals(events, [(1, 2)])


    def test_getDelayedCalls(self):
        """
        Test that we can get a list of all delayed calls
        """
        c = task.Clock()
        call = c.callLater(1, lambda x: None)
        call2 = c.callLater(2, lambda x: None)

        calls = c.getDelayedCalls()

        self.assertEquals(set([call, call2]), set(calls))


    def test_getDelayedCallsEmpty(self):
        """
        Test that we get an empty list from getDelayedCalls on a newly
        constructed Clock.
        """
        c = task.Clock()
        self.assertEquals(c.getDelayedCalls(), [])


    def test_providesIReactorTime(self):
        c = task.Clock()
        self.failUnless(interfaces.IReactorTime.providedBy(c),
                        "Clock does not provide IReactorTime")


class LoopTestCase(unittest.TestCase):
    """
    Tests for L{task.LoopingCall} based on a fake L{IReactorTime}
    implementation.
    """
    def test_defaultClock(self):
        """
        L{LoopingCall}'s default clock should be the reactor.
        """
        call = task.LoopingCall(lambda: None)
        self.assertEqual(call.clock, reactor)


    def test_callbackTimeSkips(self):
        """
        When more time than the defined interval passes during the execution
        of a callback, L{LoopingCall} should schedule the next call for the
        next interval which is still in the future.
        """
        times = []
        callDuration = None
        clock = task.Clock()
        def aCallback():
            times.append(clock.seconds())
            clock.advance(callDuration)
        call = task.LoopingCall(aCallback)
        call.clock = clock

        callDuration = 2
        call.start(0.5)
        self.assertEqual(times, [0])
        self.assertEqual(clock.seconds(), 2)

        # An iteration should have occurred at 2, but since 2 is the present
        # and not the future, it is skipped.
        clock.advance(0)
        self.assertEqual(times, [0])

        # 2.5 is in the future, and is not skipped.
        callDuration = 1
        clock.advance(0.5)
        self.assertEqual(times, [0, 2.5])
        self.assertEqual(clock.seconds(), 3.5)

        # Another iteration should have occurred, but it is again the
        # present and not the future, so it is skipped as well.
        clock.advance(0)
        self.assertEqual(times, [0, 2.5])

        # 4 is in the future, and is not skipped.
        callDuration = 0
        clock.advance(0.5)
        self.assertEqual(times, [0, 2.5, 4])
        self.assertEqual(clock.seconds(), 4)


    def test_reactorTimeSkips(self):
        """
        When more time than the defined interval passes between when
        L{LoopingCall} schedules itself to run again and when it actually
        runs again, it should schedule the next call for the next interval
        which is still in the future.
        """
        times = []
        clock = task.Clock()
        def aCallback():
            times.append(clock.seconds())

        call = task.LoopingCall(aCallback)
        call.clock = clock

        call.start(0.5)
        self.assertEqual(times, [0])

        clock.advance(2)
        self.assertEqual(times, [0, 2])

        clock.advance(1)
        self.assertEqual(times, [0, 2, 3])

        clock.advance(0)
        self.assertEqual(times, [0, 2, 3])


    def testBasicFunction(self):
        # Arrange to have time advanced enough so that our function is
        # called a few times.
        # Only need to go to 2.5 to get 3 calls, since the first call
        # happens before any time has elapsed.
        timings = [0.05, 0.1, 0.1]

        clock = task.Clock()

        L = []
        def foo(a, b, c=None, d=None):
            L.append((a, b, c, d))

        lc = TestableLoopingCall(clock, foo, "a", "b", d="d")
        D = lc.start(0.1)

        theResult = []
        def saveResult(result):
            theResult.append(result)
        D.addCallback(saveResult)

        clock.pump(timings)

        self.assertEquals(len(L), 3,
                          "got %d iterations, not 3" % (len(L),))

        for (a, b, c, d) in L:
            self.assertEquals(a, "a")
            self.assertEquals(b, "b")
            self.assertEquals(c, None)
            self.assertEquals(d, "d")

        lc.stop()
        self.assertIdentical(theResult[0], lc)

        # Make sure it isn't planning to do anything further.
        self.failIf(clock.calls)


    def testDelayedStart(self):
        timings = [0.05, 0.1, 0.1]

        clock = task.Clock()

        L = []
        lc = TestableLoopingCall(clock, L.append, None)
        d = lc.start(0.1, now=False)

        theResult = []
        def saveResult(result):
            theResult.append(result)
        d.addCallback(saveResult)

        clock.pump(timings)

        self.assertEquals(len(L), 2,
                          "got %d iterations, not 2" % (len(L),))
        lc.stop()
        self.assertIdentical(theResult[0], lc)

        self.failIf(clock.calls)


    def testBadDelay(self):
        lc = task.LoopingCall(lambda: None)
        self.assertRaises(ValueError, lc.start, -1)


    # Make sure that LoopingCall.stop() prevents any subsequent calls.
    def _stoppingTest(self, delay):
        ran = []
        def foo():
            ran.append(None)

        clock = task.Clock()
        lc = TestableLoopingCall(clock, foo)
        d = lc.start(delay, now=False)
        lc.stop()
        self.failIf(ran)
        self.failIf(clock.calls)


    def testStopAtOnce(self):
        return self._stoppingTest(0)


    def testStoppingBeforeDelayedStart(self):
        return self._stoppingTest(10)



class ReactorLoopTestCase(unittest.TestCase):
    # Slightly inferior tests which exercise interactions with an actual
    # reactor.
    def testFailure(self):
        def foo(x):
            raise TestException(x)

        lc = task.LoopingCall(foo, "bar")
        return self.assertFailure(lc.start(0.1), TestException)


    def testFailAndStop(self):
        def foo(x):
            lc.stop()
            raise TestException(x)

        lc = task.LoopingCall(foo, "bar")
        return self.assertFailure(lc.start(0.1), TestException)


    def testEveryIteration(self):
        ran = []

        def foo():
            ran.append(None)
            if len(ran) > 5:
                lc.stop()

        lc = task.LoopingCall(foo)
        d = lc.start(0)
        def stopped(ign):
            self.assertEquals(len(ran), 6)
        return d.addCallback(stopped)


    def testStopAtOnceLater(self):
        # Ensure that even when LoopingCall.stop() is called from a
        # reactor callback, it still prevents any subsequent calls.
        d = defer.Deferred()
        def foo():
            d.errback(failure.DefaultException(
                "This task also should never get called."))
        self._lc = task.LoopingCall(foo)
        self._lc.start(1, now=False)
        reactor.callLater(0, self._callback_for_testStopAtOnceLater, d)
        return d


    def _callback_for_testStopAtOnceLater(self, d):
        self._lc.stop()
        reactor.callLater(0, d.callback, "success")

    def testWaitDeferred(self):
        # Tests if the callable isn't scheduled again before the returned
        # deferred has fired.
        timings = [0.2, 0.8]
        clock = task.Clock()

        def foo():
            d = defer.Deferred()
            d.addCallback(lambda _: lc.stop())
            clock.callLater(1, d.callback, None)
            return d

        lc = TestableLoopingCall(clock, foo)
        d = lc.start(0.2)
        clock.pump(timings)
        self.failIf(clock.calls)

    def testFailurePropagation(self):
        # Tests if the failure of the errback of the deferred returned by the
        # callable is propagated to the lc errback.
        #
        # To make sure this test does not hang trial when LoopingCall does not
        # wait for the callable's deferred, it also checks there are no
        # calls in the clock's callLater queue.
        timings = [0.3]
        clock = task.Clock()

        def foo():
            d = defer.Deferred()
            clock.callLater(0.3, d.errback, TestException())
            return d

        lc = TestableLoopingCall(clock, foo)
        d = lc.start(1)
        self.assertFailure(d, TestException)

        clock.pump(timings)
        self.failIf(clock.calls)
        return d



class DeferLaterTests(unittest.TestCase):
    """
    Tests for L{task.deferLater}.
    """
    def test_callback(self):
        """
        The L{Deferred} returned by L{task.deferLater} is called back after
        the specified delay with the result of the function passed in.
        """
        results = []
        flag = object()
        def callable(foo, bar):
            results.append((foo, bar))
            return flag

        clock = task.Clock()
        d = task.deferLater(clock, 3, callable, 'foo', bar='bar')
        d.addCallback(self.assertIdentical, flag)
        clock.advance(2)
        self.assertEqual(results, [])
        clock.advance(1)
        self.assertEqual(results, [('foo', 'bar')])
        return d


    def test_errback(self):
        """
        The L{Deferred} returned by L{task.deferLater} is errbacked if the
        supplied function raises an exception.
        """
        def callable():
            raise TestException()

        clock = task.Clock()
        d = task.deferLater(clock, 1, callable)
        clock.advance(1)
        return self.assertFailure(d, TestException)
