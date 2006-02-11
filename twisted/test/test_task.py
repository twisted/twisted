# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.trial import unittest

from twisted.internet import task, reactor, defer

from twisted.python import failure

class TestableLoopingCall(task.LoopingCall):
    def __init__(self, clock, *a, **kw):
        super(TestableLoopingCall, self).__init__(*a, **kw)
        self._callLater = lambda delay: clock.callLater(delay, self)
        self._seconds = clock.seconds



class FakeDelayedCall(object):
    def __init__(self, when, clock, what, a, kw):
        self.clock = clock
        self.when = when
        self.what = what
        self.a = a
        self.kw = kw


    def __call__(self):
        return self.what(*self.a, **self.kw)


    def cancel(self):
        self.clock.calls.remove((self.when, self))



class Clock(object):
    rightNow = 0.0

    def __init__(self):
        self.calls = []

    def seconds(self):
        return self.rightNow

    def callLater(self, when, what, *a, **kw):
        self.calls.append((self.seconds() + when, FakeDelayedCall(self.seconds() + when, self, what, a, kw)))
        return self.calls[-1][1]

    def adjust(self, amount):
        self.rightNow += amount

    def runUntilCurrent(self):
        while self.calls and self.calls[0][0] < self.seconds():
            when, call = self.calls.pop(0)
            call()

    def pump(self, timings):
        timings = list(timings)
        timings.reverse()
        self.calls.sort()
        while timings:
            self.adjust(timings.pop())
            self.runUntilCurrent()



class TestException(Exception):
    pass



class LoopTestCase(unittest.TestCase):
    def testBasicFunction(self):
        # Arrange to have time advanced enough so that our function is
        # called a few times.
        # Only need to go to 2.5 to get 3 calls, since the first call
        # happens before any time has elapsed.
        timings = [0.05, 0.1, 0.1]

        clock = Clock()

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

        clock = Clock()

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

        clock = Clock()
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
