# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.defer.deferredGenerator} and related APIs.
"""

from twisted.internet import defer, reactor
from twisted.internet.defer import Deferred, deferredGenerator, waitForDeferred
from twisted.python.util import runWithWarningsSuppressed
from twisted.trial import unittest
from twisted.trial.util import suppress as SUPPRESS


def getThing():
    d = Deferred()
    reactor.callLater(0, d.callback, "hi")
    return d


def getOwie():
    d = Deferred()

    def CRAP():
        d.errback(ZeroDivisionError("OMG"))

    reactor.callLater(0, CRAP)
    return d


class TerminalException(Exception):
    pass


def deprecatedDeferredGenerator(f):
    """
    Calls L{deferredGenerator} while suppressing the deprecation warning.

    @param f: Function to call
    @return: Return value of function.
    """
    return runWithWarningsSuppressed(
        [
            SUPPRESS(
                message="twisted.internet.defer.deferredGenerator was " "deprecated"
            )
        ],
        deferredGenerator,
        f,
    )


class DeferredGeneratorTests(unittest.TestCase):
    def testBasics(self):
        """
        Test that a normal deferredGenerator works.  Tests yielding a
        deferred which callbacks, as well as a deferred errbacks. Also
        ensures returning a final value works.
        """

        @deprecatedDeferredGenerator
        def _genBasics():
            x = waitForDeferred(getThing())
            yield x
            x = x.getResult()

            self.assertEqual(x, "hi")

            ow = waitForDeferred(getOwie())
            yield ow
            try:
                ow.getResult()
            except ZeroDivisionError as e:
                self.assertEqual(str(e), "OMG")
            yield "WOOSH"
            return

        return _genBasics().addCallback(self.assertEqual, "WOOSH")

    def testProducesException(self):
        """
        Ensure that a generator that produces an exception signals
        a Failure condition on result deferred by converting the exception to
        a L{Failure}.
        """

        @deprecatedDeferredGenerator
        def _genProduceException():
            yield waitForDeferred(getThing())
            1 // 0

        return self.assertFailure(_genProduceException(), ZeroDivisionError)

    def testNothing(self):
        """Test that a generator which never yields results in None."""

        @deprecatedDeferredGenerator
        def _genNothing():
            if False:
                yield 1  # pragma: no cover

        return _genNothing().addCallback(self.assertEqual, None)

    def testHandledTerminalFailure(self):
        """
        Create a Deferred Generator which yields a Deferred which fails and
        handles the exception which results.  Assert that the Deferred
        Generator does not errback its Deferred.
        """

        @deprecatedDeferredGenerator
        def _genHandledTerminalFailure():
            x = waitForDeferred(
                defer.fail(TerminalException("Handled Terminal Failure"))
            )
            yield x
            try:
                x.getResult()
            except TerminalException:
                pass

        return _genHandledTerminalFailure().addCallback(self.assertEqual, None)

    def testHandledTerminalAsyncFailure(self):
        """
        Just like testHandledTerminalFailure, only with a Deferred which fires
        asynchronously with an error.
        """

        @deprecatedDeferredGenerator
        def _genHandledTerminalAsyncFailure(d):
            x = waitForDeferred(d)
            yield x
            try:
                x.getResult()
            except TerminalException:
                pass

        d = defer.Deferred()
        deferredGeneratorResultDeferred = _genHandledTerminalAsyncFailure(d)
        d.errback(TerminalException("Handled Terminal Failure"))
        return deferredGeneratorResultDeferred.addCallback(self.assertEqual, None)

    def testStackUsage(self):
        """
        Make sure we don't blow the stack when yielding immediately
        available deferreds.
        """

        @deprecatedDeferredGenerator
        def _genStackUsage():
            for x in range(5000):
                # Test with yielding a deferred
                x = waitForDeferred(defer.succeed(1))
                yield x
                x = x.getResult()
            yield 0

        return _genStackUsage().addCallback(self.assertEqual, 0)

    def testStackUsage2(self):
        """
        Make sure we don't blow the stack when yielding immediately
        available values.
        """

        @deprecatedDeferredGenerator
        def _genStackUsage2():
            for x in range(5000):
                # Test with yielding a random value
                yield 1
            yield 0

        return _genStackUsage2().addCallback(self.assertEqual, 0)

    def testDeferredYielding(self):
        """
        Ensure that yielding a Deferred directly is trapped as an
        error.
        """

        # See the comment _deferGenerator about d.callback(Deferred).
        def _genDeferred():
            yield getThing()

        _genDeferred = deprecatedDeferredGenerator(_genDeferred)

        return self.assertFailure(_genDeferred(), TypeError)

    suppress = [
        SUPPRESS(message="twisted.internet.defer.waitForDeferred was " "deprecated")
    ]


class DeprecateDeferredGeneratorTests(unittest.SynchronousTestCase):
    """
    Tests that L{DeferredGeneratorTests} and L{waitForDeferred} are
    deprecated.
    """

    def test_deferredGeneratorDeprecated(self):
        """
        L{deferredGenerator} is deprecated.
        """

        @deferredGenerator
        def decoratedFunction():
            yield None

        warnings = self.flushWarnings([self.test_deferredGeneratorDeprecated])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["category"], DeprecationWarning)
        self.assertEqual(
            warnings[0]["message"],
            "twisted.internet.defer.deferredGenerator was deprecated in "
            "Twisted 15.0.0; please use "
            "twisted.internet.defer.inlineCallbacks instead",
        )

    def test_waitForDeferredDeprecated(self):
        """
        L{waitForDeferred} is deprecated.
        """
        d = Deferred()
        waitForDeferred(d)

        warnings = self.flushWarnings([self.test_waitForDeferredDeprecated])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["category"], DeprecationWarning)
        self.assertEqual(
            warnings[0]["message"],
            "twisted.internet.defer.waitForDeferred was deprecated in "
            "Twisted 15.0.0; please use "
            "twisted.internet.defer.inlineCallbacks instead",
        )
