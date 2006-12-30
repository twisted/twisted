from __future__ import generators, nested_scopes

from twisted.internet import reactor

from twisted.trial import unittest, util

from twisted.internet.defer import waitForDeferred, deferredGenerator, Deferred
from twisted.internet import defer

def getThing():
    d = Deferred()
    reactor.callLater(0, d.callback, "hi")
    return d

def getOwie():
    d = Deferred()
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
        return self._genWoosh().addCallback(self.assertEqual, 'WOOSH')

    def testBuggyGen(self):
        def _genError():
            yield waitForDeferred(getThing())
            1/0
        _genError = deferredGenerator(_genError)

        return self.assertFailure(_genError(), ZeroDivisionError)


    def testNothing(self):
        def _genNothing():
            if 0: yield 1
        _genNothing = deferredGenerator(_genNothing)

        return _genNothing().addCallback(self.assertEqual, None)

    def testDeferredYielding(self):
        # See the comment _deferGenerator about d.callback(Deferred).
        def _genDeferred():
            yield getThing()
        _genDeferred = deferredGenerator(_genDeferred)

        return self.assertFailure(_genDeferred(), TypeError)


    def testHandledTerminalFailure(self):
        """
        Create a Deferred Generator which yields a Deferred which fails and
        handles the exception which results.  Assert that the Deferred
        Generator does not errback its Deferred.
        """
        class TerminalException(Exception):
            pass

        def _genFailure():
            x = waitForDeferred(defer.fail(TerminalException("Handled Terminal Failure")))
            yield x
            try:
                x.getResult()
            except TerminalException:
                pass
        _genFailure = deferredGenerator(_genFailure)
        return _genFailure().addCallback(self.assertEqual, None)


    def testHandledTerminalAsyncFailure(self):
        """
        Just like testHandledTerminalFailure, only with a Deferred which fires
        asynchronously with an error.
        """
        class TerminalException(Exception):
            pass


        d = defer.Deferred()
        def _genFailure():
            x = waitForDeferred(d)
            yield x
            try:
                x.getResult()
            except TerminalException:
                pass
        _genFailure = deferredGenerator(_genFailure)
        deferredGeneratorResultDeferred = _genFailure()
        d.errback(TerminalException("Handled Terminal Failure"))
        return deferredGeneratorResultDeferred.addCallback(
            self.assertEqual, None)


    def testStackUsage(self):
        # Make sure we don't blow the stack when yielding immediately
        # available values
        def _loop():
            for x in range(5000):
                # Test with yielding a deferred
                x = waitForDeferred(defer.succeed(1))
                yield x
                x = x.getResult()
            yield 0

        _loop = deferredGenerator(_loop)
        return _loop().addCallback(self.assertEqual, 0)

    def testStackUsage2(self):
        def _loop():
            for x in range(5000):
                # Test with yielding a random value
                yield 1
            yield 0

        _loop = deferredGenerator(_loop)
        return _loop().addCallback(self.assertEqual, 0)

