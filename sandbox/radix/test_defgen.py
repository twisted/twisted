from twisted.internet import reactor, defer

from twisted.trial import unittest, util

from defgen import waitForDeferred, deferredGenerator

def getThing():
    d = defer.Deferred()
    reactor.callLater(0, d.callback, "hi")
    return d

def getOwie():
    d = defer.Deferred()
    def CRAP():
        d.errback(ZeroDivisionError('OMG'))
    reactor.callLater(0, CRAP)
    return d

class DefGenTests(unittest.TestCase):
    def _gen(self):

        x = waitForDeferred(getThing())
        yield x
        x = x.getResult()

        self.assertEquals(x, "hi")

        ow = waitForDeferred(getOwie())
        yield ow
        try:
            ow.getResult()
        except ZeroDivisionError, e:
            self.assertEquals(str(e), 'OMG')
        yield "WOOSH"
        return
    _gen = deferredGenerator(_gen)


    def testGen(self):
        self.assertEquals(util.wait(self._gen()), "WOOSH")
