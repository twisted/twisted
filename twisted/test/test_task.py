# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.trial import unittest

from twisted.internet import task
from twisted.internet import reactor

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
        result = unittest.deferredResult(d)
        self.assertIdentical(lc, result)
        
        self.failUnless(9 <= len(L) <= 11)
        
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
        err = unittest.deferredError(d)
        err.trap(TestException)

    def testDelayedStart(self):
        ran = []
        def foo():
            ran.append(True)
        
        lc = task.LoopingCall(foo)
        d = lc.start(10, now=False)
        lc.stop()
        self.failIf(ran)
