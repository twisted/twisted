# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.trial import unittest

from twisted.internet import task, reactor, defer

from twisted.python import failure

class Clock(object):
    rightNow = 0.0

    def __call__(self):
        return self.rightNow

    def install(self):
        # Violation is fun.
        from twisted.internet import base
        self.original = base.seconds
        base.seconds = self

    def uninstall(self):
        from twisted.internet import base
        base.seconds = self.original
    
    def adjust(self, amount):
        self.rightNow += amount

    def pump(self, reactor, timings):
        timings = list(timings)
        timings.reverse()
        self.adjust(timings.pop())
        while timings:
            self.adjust(timings.pop())
            reactor.iterate()
            reactor.iterate()

class TestException(Exception):
    pass

class LoopTestCase(unittest.TestCase):
    def setUpClass(self):
        self.clock = Clock()
        self.clock.install()

    def tearDownClass(self):
        self.clock.uninstall()

    def testBasicFunction(self):
        # Arrange to have time advanced enough so that our function is
        # called a few times.
        timings = [0.05, 0.1, 0.1, 0.1]

        L = []
        def foo(a, b, c=None, d=None):
            L.append((a, b, c, d))

        lc = task.LoopingCall(foo, "a", "b", d="d")
        D = lc.start(0.1)

        self.clock.pump(reactor, timings)

        self.assertEquals(len(L), 3,
                          "got %d iterations, not 3" % (len(L),))

        for (a, b, c, d) in L:
            self.assertEquals(a, "a")
            self.assertEquals(b, "b")
            self.assertEquals(c, None)
            self.assertEquals(d, "d")

        lc.stop()
        self.clock.adjust(10)
        reactor.iterate()
        self.assertEquals(len(L), 3,
                          "got extra iterations after stopping: " + repr(L))
        self.failUnless(D.called)
        self.assertIdentical(D.result, lc)

    def testDelayedStart(self):
        timings = [0.05, 0.1, 0.1, 0.1]

        L = []
        lc = task.LoopingCall(L.append, None)
        d = lc.start(0.1, now=False)

        self.clock.pump(reactor, timings)

        self.assertEquals(len(L), 2,
                          "got %d iterations, not 2" % (len(L),))
        lc.stop()
        self.clock.adjust(10)
        reactor.iterate()
        self.assertEquals(len(L), 2,
                          "got extra iterations after stopping: " + repr(L))
        self.failUnless(d.called)
        self.assertIdentical(d.result, lc)


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
            lc.stop()
            raise TestException(x)

        lc = task.LoopingCall(foo, "bar")
        d = lc.start(0.1)
        err = unittest.deferredError(d)
        err.trap(TestException)

        # catch any possibly lingering issues
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()

    def testBadDelay(self):
        lc = task.LoopingCall(lambda: None)
        self.assertRaises(ValueError, lc.start, -1)

    def testStoppingBeforeDelayedStart(self):
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
        lc.start(0, now=False)
        lc.stop()

        # Just to be extra certain
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()

        self.failUnless(len(ran) == 0)

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
