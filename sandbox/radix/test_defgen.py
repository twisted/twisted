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
    def _genWoosh(self):

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
    _genWoosh = deferredGenerator(_genWoosh)


    def testBasics(self):
        self.assertEquals(util.wait(self._genWoosh()), "WOOSH")


    def testBuggyGen(self):
        def _genError():
            yield waitForDeferred(getThing())
            1/0
        _genError = deferredGenerator(_genError)

        self.assertRaises(ZeroDivisionError, util.wait, _genError())


    def testNothing(self):
        def _genNothing():
            if 0: yield 1
        _genNothing = deferredGenerator(_genNothing)

        self.assertEquals(util.wait(_genNothing()), None)

    def testDeferredYielding(self):
        # See the comment _deferGenerator about d.callback(Deferred).        
        def _genDeferred():
            yield getThing()
        _genDeferred = deferredGenerator(_genDeferred)

        self.assertRaises(TypeError, util.wait, _genDeferred())
