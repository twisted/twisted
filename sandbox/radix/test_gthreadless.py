from twisted.internet import defer
from twisted.trial import unittest
from gthreadless import blockOn, deferredGreenlet, GreenletWrapper

class GThreadlessTest(unittest.TestCase):
    def testBasic(self):
        from twisted.internet import reactor
        def getDeferred():
            d = defer.Deferred()
            reactor.callLater(0.1, d.callback, 'goofledorf')
            r = blockOn(d)
            return r
        getDeferred = deferredGreenlet(getDeferred)
        d = getDeferred()
        d.addCallback(self.assertEquals, 'goofledorf')
        return d

    def testGreenletWrapper(self):
        def magic():
            o = GreenletWrapper(Asynchronous())
            print o.syncResult(3), o.asyncResult(0.1, 4)
            self.assertEquals(o.syncResult(3), 3)
            self.assertEquals(o.asyncResult(0.1, 4), 4)
            self.assertRaises(ZeroDivisionError, o.syncException)
            self.assertRaises(ZeroDivisionError, o.asyncException, 0.1)
            return "hi there"
        d = deferredGreenlet(magic)()
        return d.addCallback(self.assertEquals, "hi there")
        

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
