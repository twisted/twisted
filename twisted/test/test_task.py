# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.trial import unittest

from twisted.internet import task, reactor, defer

from twisted.python import failure

class TestException(Exception):
    pass

class LoopTestCase(unittest.TestCase):
    def testBasicFunction(self):
        L = []
        def foo(a, b, c=None, d=None):
            L.append((a, b, c, d))

        lc = task.LoopingCall(foo, "a", "b", d="d")
        d = lc.start(0.1)
        reactor.callLater(1, lc.stop)
        d.addCallback(self._testBasicFunction, lc, L)
        return d

    def _testBasicFunction(self, result, lc, L):
        self.assertIdentical(lc, result)

        # this test will fail if the test process is delayed by more
        # than about .1 seconds
        self.failUnless(9 <= len(L) <= 11,
                        "got %d iterations, not 10" % len(L))

        for (a, b, c, d) in L:
            self.assertEquals(a, "a")
            self.assertEquals(b, "b")
            self.assertEquals(c, None)
            self.assertEquals(d, "d")

    def testFailure(self):
        def foo(x):
            raise TestException(x)

        lc = task.LoopingCall(foo, "bar")
        d = lc.start(0.1)
        d.addCallbacks(self._testFailure_nofailure,
                       self._testFailure_yesfailure)
        return d

    def _testFailure_nofailure(self, res):
        # NOTE: this branch does not work. I think it's a trial
        # bug. Replace the 'raise TestException' above with a 'return
        # 12' and this test will hang.
        self.fail("test did not raise an exception when it was supposed to")

    def _testFailure_yesfailure(self, err):
        err.trap(TestException)

    def testFailAndStop(self):
        def foo(x):
            self.lc.stop()
            raise TestException(x)

        self.lc = lc = task.LoopingCall(foo, "bar")
        d = lc.start(0.1)
        err = unittest.deferredError(d)
        err.trap(TestException)
        reactor.iterate() # catch any issues from scheduled stop()

    def testBadDelay(self):
        lc = task.LoopingCall(lambda: None)
        self.assertRaises(ValueError, lc.start, -1)

    def testDelayedStart(self):
        ran = []
        def foo():
            ran.append(True)

        lc = task.LoopingCall(foo)
        d = lc.start(10, now=False)
        lc.stop()
        self.failIf(ran)

    def testEveryIteration(self):
        ran = []

        def foo():
            ran.append(None)
            if len(ran) > 5:
                lc.stop()

        lc = task.LoopingCall(foo)
        d = lc.start(0)
        x = unittest.wait(d)
        self.assertEquals(len(ran), 6)

    def testStopAtOnce(self):
        # Make sure that LoopingCall.stop() prevents any subsequent
        # calls, period.
        ran = []

        def foo():
            ran.append(None)

        lc = task.LoopingCall(foo)
        lc.start(0)
        lc.stop()

        # Just to be extra certain
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()

        self.failUnless(len(ran) == 0)
    testStopAtOnce.todo = "I need to fix this"

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
