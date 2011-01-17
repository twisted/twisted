# -*- test-case-name: twisted.internet.test.test_inlinecb -*-
# Copyright (c) 2009-2010 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.defer.inlineCallbacks}.

These tests are defined in a non-C{test_*} module because they are
syntactically invalid on python < 2.5.  test_inlinecb will conditionally import
these tests on python 2.5 and greater.

Some tests for inlineCallbacks are defined in L{twisted.test.test_defgen} as
well: see U{http://twistedmatrix.com/trac/ticket/4182}.
"""

from twisted.trial.unittest import TestCase
from twisted.internet.defer import (
    Deferred, returnValue, inlineCallbacks, CancelledError)
from twisted.test.test_defgen import getThing


class NonLocalExitTests(TestCase):
    """
    It's possible for L{returnValue} to be (accidentally) invoked at a stack
    level below the L{inlineCallbacks}-decorated function which it is exiting.
    If this happens, L{returnValue} should report useful errors.

    If L{returnValue} is invoked from a function not decorated by
    L{inlineCallbacks}, it will emit a warning if it causes an
    L{inlineCallbacks} function further up the stack to exit.
    """

    def mistakenMethod(self):
        """
        This method mistakenly invokes L{returnValue}, despite the fact that it
        is not decorated with L{inlineCallbacks}.
        """
        returnValue(1)


    def assertMistakenMethodWarning(self, resultList):
        """
        Flush the current warnings and assert that we have been told that
        C{mistakenMethod} was invoked, and that the result from the Deferred
        that was fired (appended to the given list) is C{mistakenMethod}'s
        result.  The warning should indicate that an inlineCallbacks function
        called 'inline' was made to exit.
        """
        self.assertEqual(resultList, [1])
        warnings = self.flushWarnings(offendingFunctions=[self.mistakenMethod])
        self.assertEqual(len(warnings), 1)
        self.assertEquals(warnings[0]['category'], DeprecationWarning)
        self.assertEquals(
            warnings[0]['message'],
            "returnValue() in 'mistakenMethod' causing 'inline' to exit: "
            "returnValue should only be invoked by functions decorated with "
            "inlineCallbacks")


    def test_returnValueNonLocalWarning(self):
        """
        L{returnValue} will emit a non-local exit warning in the simplest case,
        where the offending function is invoked immediately.
        """
        @inlineCallbacks
        def inline():
            self.mistakenMethod()
            returnValue(2)
            yield 0
        d = inline()
        results = []
        d.addCallback(results.append)
        self.assertMistakenMethodWarning(results)


    def test_returnValueNonLocalDeferred(self):
        """
        L{returnValue} will emit a non-local warning in the case where the
        L{inlineCallbacks}-decorated function has already yielded a Deferred
        and therefore moved its generator function along.
        """
        cause = Deferred()
        @inlineCallbacks
        def inline():
            yield cause
            self.mistakenMethod()
            returnValue(2)
        effect = inline()
        results = []
        effect.addCallback(results.append)
        self.assertEquals(results, [])
        cause.callback(1)
        self.assertMistakenMethodWarning(results)


class CancellationTests(TestCase):
    def _genCascadeCancellingTesting(
        self, resultHolder=[None], getChildThing=getThing):
        """
        Generator for testing cascade cancelling cases

        @param resultHolder: A placeholder to report about C{GeneratorExit}
            exception

        @param getChildThing: Some callable returning L{defer.Deferred} that we
            awaiting (with C{yield})
        """
        try:
            x = yield getChildThing()
        except GeneratorExit:
            # Report about GeneratorExit exception
            resultHolder[0] = 'GeneratorExit'
            # Stop generator with GeneratorExit reraising
            raise
        returnValue(x)
    _genCascadeCancellingTesting = inlineCallbacks(_genCascadeCancellingTesting)


    def test_cascadeCancellingOnCancel(self):
        """
        Let:
            - G be a generator decorated with C{inlineCallbacks}
            - D be a L{Deferred} returned by G
            - C be a L{Deferred} awaited by G with C{yield}

        When D cancelled, C will be immediately cancelled too.
        """
        childResultHolder = ['FAILURE']
        def getChildThing():
            d = Deferred()
            def _eb(result):
                if result.check(CancelledError):
                    childResultHolder[0] = 'SUCCESS'
                return result
            d.addErrback(_eb)
            return d
        d = self._genCascadeCancellingTesting(getChildThing=getChildThing)
        d.addErrback(lambda result: None)
        d.cancel()
        self.assertEqual(
            childResultHolder[0], 'SUCCESS', "no cascade cancelling occurs"
        )


    def test_trapChildCancelledErrorOnCascadeCancelling(self):
        """
        Let:
            - G be a generator decorated with C{inlineCallbacks}
            - D be a L{defer.Deferred} returned by G
            - C be a L{defer.Deferred} awaited by G with C{yield}

        When D cancelled, CancelledError from cascade cancelled C will be
        trapped
        """
        d = self._genCascadeCancellingTesting()
        d.addErrback(lambda fail: None)
        d.cancel()
        errors = self.flushLoggedErrors(CancelledError)
        self.assertEquals(len(errors), 0, "CancelledError not trapped")


    def test_dontTrapChildFailureOnCascadeCancelling(self):
        """
        Let:
            - G be a generator decorated with C{inlineCallbacks}
            - D be a L{defer.Deferred} returned by G
            - C be a L{defer.Deferred} awaited by G with C{yield}

        When D cancelled and some failure (F) occurs during cascade cancelling,
        it (F) will be not trapped (in contrast with CancelledError).
        """
        class MyError(ValueError):
            pass
        def getChildThing():
            d = Deferred()
            def _eb(result):
                raise MyError()
            d.addErrback(_eb)
            return d
        d = self._genCascadeCancellingTesting(getChildThing=getChildThing)
        d.addErrback(lambda fail: None)
        d.cancel()
        def check_errors():
            errors = self.flushLoggedErrors(MyError)
            self.assertEquals(len(errors), 1, "exception consumed")
            errors[0].trap(MyError)
        from twisted.internet import reactor
        reactor.callLater(0, check_errors)


    def test_generatorStopsWhenCancelling(self):
        """
        Let:
            - G be a generator decorated with C{inlineCallbacks}
            - D be a L{defer.Deferred} returned by G
            - C be a L{defer.Deferred} awaited by G with C{yield}

        When D cancelled, G will be immediately stopped
        """
        resultHolder = [None]
        d = self._genCascadeCancellingTesting(resultHolder=resultHolder)
        d.addErrback(lambda fail: None)
        d.cancel()
        self.assertEqual(
            resultHolder[0], 'GeneratorExit',
            "generator does not stop with GeneratorExit"
        )
