from __future__ import generators, nested_scopes

import sys

from twisted.internet import reactor

from twisted.trial import unittest

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

# NOTE: most of the tests in DeferredGeneratorTests are duplicated
# with slightly different syntax for the InlineCallbacksTests below.

class TerminalException(Exception):
    pass

class BaseDefgenTests:
    """
    This class sets up a bunch of test cases which will test both
    deferredGenerator and inlineCallbacks based generators. The subclasses
    DeferredGeneratorTests and InlineCallbacksTests each provide the actual
    generator implementations tested.
    """

    def testBasics(self):
        """
        Test that a normal deferredGenerator works.  Tests yielding a
        deferred which callbacks, as well as a deferred errbacks. Also
        ensures returning a final value works.
        """

        return self._genBasics().addCallback(self.assertEqual, 'WOOSH')

    def testBuggy(self):
        """
        Ensure that a buggy generator properly signals a Failure
        condition on result deferred.
        """
        return self.assertFailure(self._genBuggy(), ZeroDivisionError)

    def testNothing(self):
        """Test that a generator which never yields results in None."""

        return self._genNothing().addCallback(self.assertEqual, None)

    def testHandledTerminalFailure(self):
        """
        Create a Deferred Generator which yields a Deferred which fails and
        handles the exception which results.  Assert that the Deferred
        Generator does not errback its Deferred.
        """
        return self._genHandledTerminalFailure().addCallback(self.assertEqual, None)

    def testHandledTerminalAsyncFailure(self):
        """
        Just like testHandledTerminalFailure, only with a Deferred which fires
        asynchronously with an error.
        """
        d = defer.Deferred()
        deferredGeneratorResultDeferred = self._genHandledTerminalAsyncFailure(d)
        d.errback(TerminalException("Handled Terminal Failure"))
        return deferredGeneratorResultDeferred.addCallback(
            self.assertEqual, None)

    def testStackUsage(self):
        """
        Make sure we don't blow the stack when yielding immediately
        available deferreds.
        """
        return self._genStackUsage().addCallback(self.assertEqual, 0)

    def testStackUsage2(self):
        """
        Make sure we don't blow the stack when yielding immediately
        available values.
        """
        return self._genStackUsage2().addCallback(self.assertEqual, 0)




class DeferredGeneratorTests(BaseDefgenTests, unittest.TestCase):

    # First provide all the generator impls necessary for BaseDefgenTests
    def _genBasics(self):

        x = waitForDeferred(getThing())
        yield x
        x = x.getResult()

        self.assertEqual(x, "hi")

        ow = waitForDeferred(getOwie())
        yield ow
        try:
            ow.getResult()
        except ZeroDivisionError, e:
            self.assertEqual(str(e), 'OMG')
        yield "WOOSH"
        return
    _genBasics = deferredGenerator(_genBasics)

    def _genBuggy(self):
        yield waitForDeferred(getThing())
        1/0
    _genBuggy = deferredGenerator(_genBuggy)


    def _genNothing(self):
        if 0: yield 1
    _genNothing = deferredGenerator(_genNothing)

    def _genHandledTerminalFailure(self):
        x = waitForDeferred(defer.fail(TerminalException("Handled Terminal Failure")))
        yield x
        try:
            x.getResult()
        except TerminalException:
            pass
    _genHandledTerminalFailure = deferredGenerator(_genHandledTerminalFailure)


    def _genHandledTerminalAsyncFailure(self, d):
        x = waitForDeferred(d)
        yield x
        try:
            x.getResult()
        except TerminalException:
            pass
    _genHandledTerminalAsyncFailure = deferredGenerator(_genHandledTerminalAsyncFailure)


    def _genStackUsage(self):
        for x in range(5000):
            # Test with yielding a deferred
            x = waitForDeferred(defer.succeed(1))
            yield x
            x = x.getResult()
        yield 0
    _genStackUsage = deferredGenerator(_genStackUsage)

    def _genStackUsage2(self):
        for x in range(5000):
            # Test with yielding a random value
            yield 1
        yield 0
    _genStackUsage2 = deferredGenerator(_genStackUsage2)

    # Tests unique to deferredGenerator

    def testDeferredYielding(self):
        """
        Ensure that yielding a Deferred directly is trapped as an
        error.
        """
        # See the comment _deferGenerator about d.callback(Deferred).
        def _genDeferred():
            yield getThing()
        _genDeferred = deferredGenerator(_genDeferred)

        return self.assertFailure(_genDeferred(), TypeError)



## This has to be in a string so the new yield syntax doesn't cause a
## syntax error in Python 2.4 and before.
inlineCallbacksTestsSource = '''
from twisted.internet.defer import inlineCallbacks, returnValue

class InlineCallbacksTests(BaseDefgenTests, unittest.TestCase):
    # First provide all the generator impls necessary for BaseDefgenTests

    def _genBasics(self):

        x = yield getThing()

        self.assertEqual(x, "hi")

        try:
            ow = yield getOwie()
        except ZeroDivisionError, e:
            self.assertEqual(str(e), 'OMG')
        returnValue("WOOSH")
    _genBasics = inlineCallbacks(_genBasics)

    def _genBuggy(self):
        yield getThing()
        1/0
    _genBuggy = inlineCallbacks(_genBuggy)


    def _genNothing(self):
        if 0: yield 1
    _genNothing = inlineCallbacks(_genNothing)


    def _genHandledTerminalFailure(self):
        try:
            x = yield defer.fail(TerminalException("Handled Terminal Failure"))
        except TerminalException:
            pass
    _genHandledTerminalFailure = inlineCallbacks(_genHandledTerminalFailure)


    def _genHandledTerminalAsyncFailure(self, d):
        try:
            x = yield d
        except TerminalException:
            pass
    _genHandledTerminalAsyncFailure = inlineCallbacks(
        _genHandledTerminalAsyncFailure)


    def _genStackUsage(self):
        for x in range(5000):
            # Test with yielding a deferred
            x = yield defer.succeed(1)
        returnValue(0)
    _genStackUsage = inlineCallbacks(_genStackUsage)

    def _genStackUsage2(self):
        for x in range(5000):
            # Test with yielding a random value
            yield 1
        returnValue(0)
    _genStackUsage2 = inlineCallbacks(_genStackUsage2)

    # Tests unique to inlineCallbacks

    def testYieldNonDeferrred(self):
        """
        Ensure that yielding a non-deferred passes it back as the
        result of the yield expression.
        """
        def _test():
            x = yield 5
            returnValue(5)
        _test = inlineCallbacks(_test)

        return _test().addCallback(self.assertEqual, 5)

    def testReturnNoValue(self):
        """Ensure a standard python return results in a None result."""
        def _noReturn():
            yield 5
            return
        _noReturn = inlineCallbacks(_noReturn)

        return _noReturn().addCallback(self.assertEqual, None)

    def testReturnValue(self):
        """Ensure that returnValue works."""
        def _return():
            yield 5
            returnValue(6)
        _return = inlineCallbacks(_return)

        return _return().addCallback(self.assertEqual, 6)


    def test_nonGeneratorReturn(self):
        """
        Ensure that C{TypeError} with a message about L{inlineCallbacks} is
        raised when a non-generator returns something other than a generator.
        """
        def _noYield():
            return 5
        _noYield = inlineCallbacks(_noYield)

        self.assertIn("inlineCallbacks",
            str(self.assertRaises(TypeError, _noYield)))


    def test_nonGeneratorReturnValue(self):
        """
        Ensure that C{TypeError} with a message about L{inlineCallbacks} is
        raised when a non-generator calls L{returnValue}.
        """
        def _noYield():
            returnValue(5)
        _noYield = inlineCallbacks(_noYield)

        self.assertIn("inlineCallbacks",
            str(self.assertRaises(TypeError, _noYield)))

'''

if sys.version_info > (2, 5):
    # Load tests
    exec inlineCallbacksTestsSource
else:
    # Make a placeholder test case
    class InlineCallbacksTests(unittest.TestCase):
        skip = "defer.defgen doesn't run on python < 2.5."
        def test_everything(self):
            pass
