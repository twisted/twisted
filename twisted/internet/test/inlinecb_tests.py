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



class TranslateMe(Exception):
    """
    Sample exception type.
    """



class TranslateResult(Exception):
    """
    Sample exception type.
    """



class DontFail(Exception):
    """
    Sample exception type.
    """

    def __init__(self, actual):
        Exception.__init__(self)
        self.actualValue = actual



class CancellationTests(TestCase):
    """
    Tests for cancellation of L{Deferred}s returned by L{inlineCallbacks}.

    For each of these tests, let:

        - G be a generator decorated with C{inlineCallbacks}
        - D be a L{Deferred} returned by G
        - C be a L{Deferred} awaited by G with C{yield}
    """

    def setUp(self):
        """
        Set up the list of outstanding L{Deferred}s.
        """
        self.thingsOutstanding = []


    def tearDown(self):
        """
        If any L{Deferred}s are still outstanding, fire them.
        """
        while self.thingsOutstanding:
            self.thingGotten()


    @inlineCallbacks
    def sampleInlineCB(self, getChildThing=None):
        """
        Generator for testing cascade cancelling cases.

        @param getChildThing: Some callable returning L{Deferred} that we
            awaiting (with C{yield})
        """
        if getChildThing is None:
            getChildThing = self.getThing
        try:
            x = yield getChildThing()
        except TranslateMe:
            raise TranslateResult()
        except DontFail, df:
            returnValue(df.actualValue)
        returnValue(x)


    def getThing(self):
        """
        A sample function that returns a L{Deferred} that can be fired on
        demand, by L{CancellationTests.thingGotten}.
        """
        self.thingsOutstanding.append(Deferred())
        return self.thingsOutstanding[-1]


    def thingGotten(self, result=None):
        """
        Fire the L{Deferred} returned from the least-recent call to
        L{CancellationTests.getThing}.
        """
        self.thingsOutstanding.pop(0).callback(result)


    def test_cascadeCancellingOnCancel(self):
        """
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
        d = self.sampleInlineCB(getChildThing=getChildThing)
        d.addErrback(lambda result: None)
        d.cancel()
        self.assertEqual(
            childResultHolder[0], 'SUCCESS', "no cascade cancelling occurs"
        )


    def test_trapChildCancelledErrorOnCascadeCancelling(self):
        """
        When D cancelled, CancelledError from cascade cancelled C will be
        trapped
        """
        d = self.sampleInlineCB()
        d.addErrback(lambda fail: None)
        d.cancel()
        errors = self.flushLoggedErrors(CancelledError)
        self.assertEquals(len(errors), 0, "CancelledError not trapped")


    def test_dontTrapChildFailureOnCascadeCancelling(self):
        """
        When D is cancelled and some failure (F) occurs during cascade
        cancelling, it (F) will be not trapped (in contrast with
        CancelledError).
        """
        class MyError(ValueError):
            pass
        def getChildThing():
            d = Deferred()
            def _eb(result):
                raise MyError()
            d.addErrback(_eb)
            return d
        d = self.sampleInlineCB(getChildThing=getChildThing)
        d.addErrback(lambda fail: None)
        d.cancel()
        errors = self.flushLoggedErrors(MyError)
        self.assertEquals(len(errors), 1, "exception consumed")
        errors[0].trap(MyError)


    def test_errorToErrorTranslation(self):
        """
        When D is cancelled, and C raises a particular type of error, G may
        catch that error at the point of yielding and translate it into
        something else which may be received by application code.
        """
        def cancel(it):
            it.errback(TranslateMe())
        a = Deferred(cancel)
        d = self.sampleInlineCB(lambda : a)
        d.cancel()
        self.failUnlessFailure(d, TranslateResult)


    def test_errorToSuccessTranslation(self):
        """
        When D is cancelled, and C raises a particular type of error, G may
        catch that error at the point of yielding and translate it into
        something else which may be received by application code.
        """
        def cancel(it):
            it.errback(DontFail(4321))
        a = Deferred(cancel)
        d = self.sampleInlineCB(lambda : a)
        results = []
        d.addCallback(results.append)
        d.cancel()
        self.assertEquals(results, [4321])


    def test_asynchronousCancellation(self):
        """
        When D is cancelled, it won't reach the callbacks added to it by
        application code until C reaches the point in its callback chain where G
        awaits it.  Otherwise, application code won't be able to track resource
        usage that D may be using.
        """
        moreDeferred = Deferred()
        def deferMeMore(result):
            result.trap(CancelledError)
            return moreDeferred
        def deferMe():
            d = Deferred()
            d.addErrback(deferMeMore)
            return d
        d = self.sampleInlineCB(getChildThing=deferMe)
        finalResult = []
        d.addBoth(finalResult.append)
        d.cancel()
        self.assertEquals(finalResult, [])
        moreDeferred.callback("some data")

        # moreDeferred is just some random implementation detail in the guts of
        # self.sampleInlineCB().  We don't know how it's going to be used
        # (because we are supposed to stop driving that generator) so we should
        # not give back the final result; given that arbitrary processing may
        # occur after the result is received, it is _not_ the same as a Deferred
        # chain which may give back a successful result after cancellation.  So
        # we always look for a CancelledError rather than a result.
        self.assertEquals(len(finalResult), 1)
        self.failUnlessFailure(finalResult[0], CancelledError)

