from twisted.internet import defer
from twisted.trial import unittest
import gthreadless

class GThreadlessTest(unittest.TestCase):
    def testBasic(self):
        from twisted.internet import reactor
        def getDeferred():
            d = defer.Deferred()
            reactor.callLater(0.1, d.callback, 'goofledorf')
            r = gthreadless.blockOn(d)
            return r
        getDeferred = gthreadless.deferredGreenlet(getDeferred)
        d = getDeferred()
        d.addCallback(self.assertEquals, 'goofledorf')
        return d

    def _magic(self):
        o = gthreadless.GreenletWrapper(Asynchronous())
        self.assertEquals(o.syncResult(3), 3)
        self.assertEquals(o.asyncResult(0.1, 4), 4)
        self.assertRaises(ZeroDivisionError, o.syncException)
        self.assertRaises(ZeroDivisionError, o.asyncException, 0.1)
        return "hi there"

    def testGreenletWrapper(self):
        d = gthreadless.deferredGreenlet(self._magic)()
        return d.addCallback(self.assertEquals, "hi there")

    def testCallFromMain(self):
        self.assertRaises(gthreadless.CalledFromMain, gthreadless.blockOn, defer.succeed(1))

class Asynchronous(object):
    def syncResult(self, v):
        return v

    def asyncResult(self, n, v):
        from twisted.internet import reactor
        d = defer.Deferred()
        reactor.callLater(n, d.callback, v)
        return d
    
    def syncException(self):
        1/0
    
    def asyncException(self, n):
        from twisted.internet import reactor
        def fail():
            try:
                1/0
            except:
                d.errback()
        d = defer.Deferred()
        reactor.callLater(n, fail)
        return d
