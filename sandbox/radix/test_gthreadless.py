from twisted.internet import defer
from twisted.trial import unittest
from gthreadless import blockOn, deferredGreenlet, GreenletWrapper, CalledFromMain
from twisted.internet import reactor

def laterResult(n, result):
    d = defer.Deferred()
    reactor.callLater(n, d.callback, result)
    return d
    
class GThreadlessTest(unittest.TestCase):
    def _getDeferred(self):
        import greenlet
        #print "getD is", greenlet.getcurrent()
        r = blockOn(laterResult(0.1, 'goofledorf'), desc="_getDeferred")
        #print "GeTD Is DonEnEN"
        return r
    _getDeferred = deferredGreenlet(_getDeferred)

    def testBasic(self):
        d = self._getDeferred()
        d.addCallback(self.assertEquals, 'goofledorf')
        return d

    def _magic(self):
        o = GreenletWrapper(Asynchronous())
        self.assertEquals(o.syncResult(3), 3)
        self.assertEquals(o.asyncResult(0.1, 4), 4)
        self.assertRaises(ZeroDivisionError, o.syncException)
        self.assertRaises(ZeroDivisionError, o.asyncException, 0.1)
        return "hi there"

    def testGreenletWrapper(self):
        d = deferredGreenlet(self._magic)()
        return d.addCallback(self.assertEquals, "hi there")

    def testCallFromMain(self):
        self.assertRaises(CalledFromMain, blockOn, defer.succeed(1))

    def testNestedBlocks(self):
        #print
        #print "++++++++++++"
        def f1():
            import greenlet
            #print "f1 is", greenlet.getcurrent()
            return blockOn(self._getDeferred(), "thingy")
        thingy = deferredGreenlet(f1)
        d = thingy().addCallback(self.assertEquals, "goofledorf")
        return d
    testNestedBlocks.timeout = 2


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
