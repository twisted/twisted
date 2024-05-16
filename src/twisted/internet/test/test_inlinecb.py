# -*- test-case-name: twisted.internet.test.test_inlinecb -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.defer.inlineCallbacks}.

Some tests for inlineCallbacks are defined in L{twisted.test.test_defgen} as
well.
"""


from twisted.internet.defer import (
    CancelledError,
    Deferred,
    inlineCallbacks,
    returnValue,
)
from twisted.trial.unittest import SynchronousTestCase, TestCase


class StopIterationReturnTests(TestCase):
    """
    On Python 3.4 and newer generator functions may use the C{return} statement
    with a value, which is attached to the L{StopIteration} exception that is
    raised.

    L{inlineCallbacks} will use this value when it fires the C{callback}.
    """

    def test_returnWithValue(self):
        """
        If the C{return} statement has a value it is propagated back to the
        L{Deferred} that the C{inlineCallbacks} function returned.
        """
        environ = {"inlineCallbacks": inlineCallbacks}
        exec(
            """
@inlineCallbacks
def f(d):
    yield d
    return 14
        """,
            environ,
        )
        d1 = Deferred()
        d2 = environ["f"](d1)
        d1.callback(None)
        self.assertEqual(self.successResultOf(d2), 14)


class StackedInlineCallbacksTests(TestCase):
    """
    We have an optimization that invokes generators directly when an
    inlineCallbacks-decorated function yields value directly to yield of
    another inlineCallbacks-decorated function.
    """

    def runCallbacksOnDeferreds(self, deferredList):
        """
        Given a list of L{Deferred}, value tuples, invokes each L{Deferred}
        with the corresponding value. Depending on whether value is an
        exception, either callback or errback is called.
        """
        for d, x in deferredList:
            if isinstance(x, Exception):
                d.errback(x)
            else:
                d.callback(x)

    def test_nonCalledDeferredSingleYield(self):
        """
        Tests the case when a chain of L{inlineCallbacks} calls end up
        yielding and blocking on a L{Deferred}.
        """
        expectations = []

        # list of deferred to invoke with what results
        deferredList = []

        @inlineCallbacks
        def f1(x):
            expectations.append(("f1 enter", x))

            d = Deferred()
            deferredList.append((d, x))
            x = yield d
            x += 1

            expectations.append(("f1 exit", x))
            returnValue(x)

        @inlineCallbacks
        def f2(x):
            expectations.append(("f2 enter", x))

            x = yield f1(x)
            x += 2

            expectations.append(("f2 exit", x))
            returnValue(x)

        @inlineCallbacks
        def f3(x):
            expectations.append(("f3 enter", x))

            x = yield f2(x)
            x += 4

            expectations.append(("f3 exit", x))
            returnValue(x)

        res = f3(1)
        self.runCallbacksOnDeferreds(deferredList)

        self.assertEqual(self.successResultOf(res), 8)
        self.assertEqual(
            expectations,
            [
                ("f3 enter", 1),
                ("f2 enter", 1),
                ("f1 enter", 1),
                ("f1 exit", 2),
                ("f2 exit", 4),
                ("f3 exit", 8),
            ],
        )

    def test_nonCalledDeferredMultipleYields(self):
        """
        Tests the case when a chain of L{inlineCallbacks} calls end up yielding
        and blocking on a L{Deferred}. In this case the same decorated function
        is yielded multiple times.
        """
        expectations = []

        # list of deferred to invoke with what results
        deferredList = []

        @inlineCallbacks
        def f1(x):
            expectations.append(("f1 enter", x))

            d = Deferred()
            deferredList.append((d, x))
            x = yield d
            x += 1

            expectations.append(("f1 exit", x))
            returnValue(x)

        @inlineCallbacks
        def f2(x):
            expectations.append(("f2 enter", x))

            x = yield f1(x)
            x = yield f1(x)
            x = yield f1(x)
            x += 2

            expectations.append(("f2 exit", x))
            returnValue(x)

        @inlineCallbacks
        def f3(x):
            expectations.append(("f3 enter", x))

            x = yield f2(x)
            x = yield f2(x)
            x = yield f2(x)
            x += 4

            expectations.append(("f3 exit", x))
            returnValue(x)

        res = f3(1)
        for d, x in deferredList:
            d.callback(x)

        self.assertEqual(self.successResultOf(res), 20)
        self.assertEqual(
            expectations,
            [
                ("f3 enter", 1),
                ("f2 enter", 1),
                ("f1 enter", 1),
                ("f1 exit", 2),
                ("f1 enter", 2),
                ("f1 exit", 3),
                ("f1 enter", 3),
                ("f1 exit", 4),
                ("f2 exit", 6),
                ("f2 enter", 6),
                ("f1 enter", 6),
                ("f1 exit", 7),
                ("f1 enter", 7),
                ("f1 exit", 8),
                ("f1 enter", 8),
                ("f1 exit", 9),
                ("f2 exit", 11),
                ("f2 enter", 11),
                ("f1 enter", 11),
                ("f1 exit", 12),
                ("f1 enter", 12),
                ("f1 exit", 13),
                ("f1 enter", 13),
                ("f1 exit", 14),
                ("f2 exit", 16),
                ("f3 exit", 20),
            ],
        )

    def test_intermediateAddCallbacksAndNoWaiting(self):
        """
        Tests the case when a L{Deferred} produced from L{inlineCallbacks} gets
        a callback added via L{addCallback} and then yielded in a function
        decorated with L{inlineCallbacks}. In this case the initial L{Deferred}
        already has a value.
        """
        expectations = []

        @inlineCallbacks
        def f1(x):
            expectations.append(("f1 enter", x))

            x = yield x
            x += 1

            expectations.append(("f1 exit", x))
            returnValue(x)

        def f2(x):
            expectations.append(("f2 enter", x))
            x += 2
            expectations.append(("f2 exit", x))
            return x

        @inlineCallbacks
        def f3(x):
            expectations.append(("f3 enter", x))

            d = f1(x)
            d.addCallback(f2)
            x = yield d
            x += 4

            expectations.append(("f3 exit", x))
            returnValue(x)

        self.assertEqual(self.successResultOf(f3(1)), 8)
        self.assertEqual(
            expectations,
            [
                ("f3 enter", 1),
                ("f1 enter", 1),
                ("f1 exit", 2),
                ("f2 enter", 2),
                ("f2 exit", 4),
                ("f3 exit", 8),
            ],
        )

    def test_intermediateAddCallbacksAndWithWaitingFirstYield(self):
        """
        Tests the case when a L{Deferred} produced from L{inlineCallbacks} gets
        a callback added via L{addCallback} and then yielded in a function
        decorated with L{inlineCallbacks}. In this case the initial L{Deferred}
        does not have a value and blocks entire callback chain.
        """
        expectations = []

        # list of deferred to invoke with what results
        deferredList = []

        @inlineCallbacks
        def f1(x):
            expectations.append(("f1 enter", x))

            d = Deferred()
            deferredList.append((d, x))
            x = yield d
            x += 1

            expectations.append(("f1 exit", x))
            returnValue(x)

        def f2(x):
            expectations.append(("f2 enter", x))
            x += 2
            expectations.append(("f2 exit", x))
            return x

        @inlineCallbacks
        def f3(x):
            expectations.append(("f3 enter", x))

            d = f1(x)
            d.addCallback(f2)
            x = yield d
            x += 4

            expectations.append(("f3 exit", x))
            returnValue(x)

        res = f3(1)
        self.runCallbacksOnDeferreds(deferredList)

        self.assertEqual(self.successResultOf(res), 8)
        self.assertEqual(
            expectations,
            [
                ("f3 enter", 1),
                ("f1 enter", 1),
                ("f1 exit", 2),
                ("f2 enter", 2),
                ("f2 exit", 4),
                ("f3 exit", 8),
            ],
        )

    def test_intermediateAddCallbacksAndWithWaitingSecondYield(self):
        """
        Tests the case when a L{Deferred} produced from L{inlineCallbacks} gets
        a callback added via L{addCallback} and then yielded in a function
        decorated with L{inlineCallbacks}. In this case the initial L{Deferred}
        does not have a value and blocks the entire callback chain.
        Additionally, a subsequent L{Deferred} blocks the entire callback chain
        again.
        """
        expectations = []

        # list of deferred to invoke with what results
        deferredList = []

        @inlineCallbacks
        def f1(x):
            expectations.append(("f1 enter", x))

            d = Deferred()
            deferredList.append((d, x))
            x = yield d
            x += 1

            expectations.append(("f1 exit", x))
            returnValue(x)

        def f2(x):
            expectations.append(("f2 enter", x))
            x += 2
            expectations.append(("f2 exit", x))
            return x

        @inlineCallbacks
        def f3(x):
            expectations.append(("f3 enter", x))

            x = yield f1(x)
            d = f1(x)
            d.addCallback(f2)
            x = yield d
            x += 4

            expectations.append(("f3 exit", x))
            returnValue(x)

        res = f3(1)
        self.runCallbacksOnDeferreds(deferredList)

        self.assertEqual(self.successResultOf(res), 9)
        self.assertEqual(
            expectations,
            [
                ("f3 enter", 1),
                ("f1 enter", 1),
                ("f1 exit", 2),
                ("f1 enter", 2),
                ("f1 exit", 3),
                ("f2 enter", 3),
                ("f2 exit", 5),
                ("f3 exit", 9),
            ],
        )

    def test_raisesExceptionFromDeferredWithWaitingFirstCallback(self):
        """
        Tests the case when a function decorated with L{inlineCallbacks} yields
        a L{Deferred} that results in a failure.
        """
        expectations = []

        # list of deferred to invoke with what results
        deferredList = []

        class MyException(Exception):
            pass

        @inlineCallbacks
        def f2(x):
            expectations.append(("f2 enter", x))

            d = Deferred()
            deferredList.append((d, MyException()))
            x = yield d

            # Above line throws an exception. The rest of the function will not
            # be executed, but in case it is (error), it should still work so
            # that assertions at the end of the test work.
            expectations.append(("f2 exit", x))  # pragma: no cover
            returnValue(x)  # pragma: no cover

        @inlineCallbacks
        def f3(x):
            expectations.append(("f3 enter", x))

            with self.assertRaises(MyException):
                x = yield f2(x)
            x += 4

            expectations.append(("f3 exit", x))
            returnValue(x)

        res = f3(1)
        self.runCallbacksOnDeferreds(deferredList)
        self.assertEqual(self.successResultOf(res), 5)
        self.assertEqual(
            expectations,
            [
                ("f3 enter", 1),
                ("f2 enter", 1),
                ("f3 exit", 5),
            ],
        )

    def test_raisesExceptionFromDeferredWithWaitingSecondCallback(self):
        """
        Tests the case when a function decorated with L{inlineCallbacks} blocks
        on a L{Deferred} produced by another function decorated with
        L{inlineCallbacks}. Once that unblocks, a L{Deferred} that results
        in an failure is yielded.
        """
        expectations = []

        # list of deferred to invoke with what results
        deferredList = []

        class MyException(Exception):
            pass

        @inlineCallbacks
        def f1(x):
            expectations.append(("f1 enter", x))

            d = Deferred()
            deferredList.append((d, x))
            x = yield d
            x += 1

            expectations.append(("f1 exit", x))
            returnValue(x)

        @inlineCallbacks
        def f2(x):
            expectations.append(("f2 enter", x))

            d = Deferred()
            deferredList.append((d, MyException()))
            x = yield d

            # Above line throws an exception. The rest of the function will not
            # be executed, but in case it is (error), it should still work so
            # that assertions at the end of the test work.
            expectations.append(("f2 exit", x))  # pragma: no cover
            returnValue(x)  # pragma: no cover

        @inlineCallbacks
        def f3(x):
            expectations.append(("f3 enter", x))

            x = yield f1(x)
            with self.assertRaises(MyException):
                x = yield f2(x)
            x += 4

            expectations.append(("f3 exit", x))
            returnValue(x)

        res = f3(1)
        self.runCallbacksOnDeferreds(deferredList)
        self.assertEqual(self.successResultOf(res), 6)
        self.assertEqual(
            expectations,
            [
                ("f3 enter", 1),
                ("f1 enter", 1),
                ("f1 exit", 2),
                ("f2 enter", 2),
                ("f3 exit", 6),
            ],
        )


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
        self.assertEqual(warnings[0]["category"], DeprecationWarning)
        self.assertEqual(
            warnings[0]["message"],
            "returnValue() in 'mistakenMethod' causing 'inline' to exit: "
            "returnValue should only be invoked by functions decorated with "
            "inlineCallbacks",
        )

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
        self.assertEqual(results, [])
        cause.callback(1)
        self.assertMistakenMethodWarning(results)


class ForwardTraceBackTests(SynchronousTestCase):
    def test_forwardTracebacks(self):
        """
        Chained inlineCallbacks are forwarding the traceback information
        from generator to generator.

        A first simple test with a couple of inline callbacks.
        """

        @inlineCallbacks
        def erroring():
            yield "forcing generator"
            raise Exception("Error Marker")

        @inlineCallbacks
        def calling():
            yield erroring()

        d = calling()
        f = self.failureResultOf(d)
        tb = f.getTraceback()
        self.assertIn("in erroring", tb)
        self.assertIn("in calling", tb)
        self.assertIn("Error Marker", tb)

    def test_forwardLotsOfTracebacks(self):
        """
        Several Chained inlineCallbacks gives information about all generators.

        A wider test with a 4 chained inline callbacks.

        Application stack-trace should be reported, and implementation details
        like "throwExceptionIntoGenerator" symbols are omitted from the stack.

        Note that the previous test is testing the simple case, and this one is
        testing the deep recursion case.

        That case needs specific code in failure.py to accomodate to stack
        breakage introduced by throwExceptionIntoGenerator.

        Hence we keep the two tests in order to sort out which code we
        might have regression in.
        """

        @inlineCallbacks
        def erroring():
            yield "forcing generator"
            raise Exception("Error Marker")

        @inlineCallbacks
        def calling3():
            yield erroring()

        @inlineCallbacks
        def calling2():
            yield calling3()

        @inlineCallbacks
        def calling():
            yield calling2()

        d = calling()
        f = self.failureResultOf(d)
        tb = f.getTraceback()
        self.assertIn("in erroring", tb)
        self.assertIn("in calling", tb)
        self.assertIn("in calling2", tb)
        self.assertIn("in calling3", tb)
        self.assertNotIn("throwExceptionIntoGenerator", tb)
        self.assertIn("Error Marker", tb)
        self.assertIn("in erroring", f.getTraceback())


class UntranslatedError(Exception):
    """
    Untranslated exception type when testing an exception translation.
    """


class TranslatedError(Exception):
    """
    Translated exception type when testing an exception translation.
    """


class DontFail(Exception):
    """
    Sample exception type.
    """

    def __init__(self, actual):
        Exception.__init__(self)
        self.actualValue = actual


class CancellationTests(SynchronousTestCase):
    """
    Tests for cancellation of L{Deferred}s returned by L{inlineCallbacks}.
    For each of these tests, let:
        - C{G} be a generator decorated with C{inlineCallbacks}
        - C{D} be a L{Deferred} returned by C{G}
        - C{C} be a L{Deferred} awaited by C{G} with C{yield}
    """

    def setUp(self):
        """
        Set up the list of outstanding L{Deferred}s.
        """
        self.deferredsOutstanding = []

    def tearDown(self):
        """
        If any L{Deferred}s are still outstanding, fire them.
        """
        while self.deferredsOutstanding:
            self.deferredGotten()

    @inlineCallbacks
    def stackedInlineCB(self, getChildDeferred):
        x = yield getChildDeferred()
        returnValue(x)

    @inlineCallbacks
    def sampleInlineCB(self, getChildDeferred=None, stacked=False, firstDeferred=None):
        """
        Generator for testing cascade cancelling cases.

        @param getChildDeferred: Some callable returning L{Deferred} that we
            awaiting (with C{yield})
        """
        if getChildDeferred is None:
            getChildDeferred = self.getDeferred
        try:
            if stacked:
                if firstDeferred:
                    yield firstDeferred
                x = yield self.stackedInlineCB(getChildDeferred)
            else:
                x = yield getChildDeferred()
        except UntranslatedError:
            raise TranslatedError()
        except DontFail as df:
            x = df.actualValue - 2
        returnValue(x + 1)

    def getDeferred(self):
        """
        A sample function that returns a L{Deferred} that can be fired on
        demand, by L{CancellationTests.deferredGotten}.

        @return: L{Deferred} that can be fired on demand.
        """
        self.deferredsOutstanding.append(Deferred())
        return self.deferredsOutstanding[-1]

    def deferredGotten(self, result=None):
        """
        Fire the L{Deferred} returned from the least-recent call to
        L{CancellationTests.getDeferred}.

        @param result: result object to be used when firing the L{Deferred}.
        """
        self.deferredsOutstanding.pop(0).callback(result)

    def doCascadeCancellingOnCancel(self, stacked=False, cancelOnSecondDeferred=False):
        """
        When C{D} cancelled, C{C} will be immediately cancelled too.

        @param stacked: if True, tests stacked inline callbacks

        @param cancelOnSecondDeferred: if True, tests cancellation on the
            second yield in inlineCallbacks
        """
        childResultHolder = ["FAILURE"]

        def getChildDeferred():
            d = Deferred()

            def _eb(result):
                childResultHolder[0] = result.check(CancelledError)
                return result

            d.addErrback(_eb)
            return d

        firstDeferred = None
        if cancelOnSecondDeferred:
            firstDeferred = Deferred()
        d = self.sampleInlineCB(
            getChildDeferred=getChildDeferred,
            stacked=stacked,
            firstDeferred=firstDeferred,
        )
        d.addErrback(lambda result: None)
        if firstDeferred:
            firstDeferred.callback(1)
        d.cancel()
        self.assertEqual(
            childResultHolder[0],
            CancelledError,
            "no cascade cancelling occurs",
        )

    def test_CascadeCancellingOnCancel(self):
        self.doCascadeCancellingOnCancel()

    def test_CascadeCancellingOnCancelStacked(self):
        self.doCascadeCancellingOnCancel(stacked=True)

    def test_CascadeCancellingOnCancelStackedOnSecondDeferred(self):
        self.doCascadeCancellingOnCancel(stacked=True, cancelOnSecondDeferred=True)

    def doErrbackCancelledErrorOnCancel(
        self, stacked=False, cancelOnSecondDeferred=False
    ):
        """
        When C{D} cancelled, CancelledError from C{C} will be errbacked
        through C{D}.

        @param stacked: if True, tests stacked inline callbacks

        @param cancelOnSecondDeferred: if True, tests cancellation on the
            second yield in inlineCallbacks
        """

        firstDeferred = None
        if cancelOnSecondDeferred:
            firstDeferred = Deferred()
        d = self.sampleInlineCB(stacked=stacked, firstDeferred=firstDeferred)
        if firstDeferred:
            firstDeferred.callback(1)
        d.cancel()
        self.assertRaises(CancelledError, self.failureResultOf(d).raiseException)

    def test_ErrbackCancelledErrorOnCancel(self):
        self.doErrbackCancelledErrorOnCancel()

    def test_ErrbackCancelledErrorOnCancelStacked(self):
        self.doErrbackCancelledErrorOnCancel(stacked=True)

    def test_ErrbackCancelledErrorOnCancelStackedOnSecondDeferred(self):
        self.doErrbackCancelledErrorOnCancel(stacked=True, cancelOnSecondDeferred=True)

    def doErrorToErrorTranslation(self, stacked=False, cancelOnSecondDeferred=False):
        """
        When C{D} is cancelled, and C raises a particular type of error, C{G}
        may catch that error at the point of yielding and translate it into
        a different error which may be received by application code.
        """

        def cancel(it):
            it.errback(UntranslatedError())

        firstDeferred = None
        if cancelOnSecondDeferred:
            firstDeferred = Deferred()
        a = Deferred(cancel)
        d = self.sampleInlineCB(lambda: a, stacked=stacked, firstDeferred=firstDeferred)
        if firstDeferred:
            firstDeferred.callback(1)
        d.cancel()
        self.assertRaises(TranslatedError, self.failureResultOf(d).raiseException)

    def test_ErrorToErrorTranslation(self):
        self.doErrorToErrorTranslation()

    def test_ErrorToErrorTranslationStacked(self):
        self.doErrorToErrorTranslation(stacked=True)

    def test_ErrorToErrorTranslationStackedOnSecondDeferred(self):
        self.doErrorToErrorTranslation(stacked=True, cancelOnSecondDeferred=True)

    def doErrorToSuccessTranslation(self, stacked=False, cancelOnSecondDeferred=False):
        """
        When C{D} is cancelled, and C{C} raises a particular type of error,
        C{G} may catch that error at the point of yielding and translate it
        into a result value which may be received by application code.
        """

        def cancel(it):
            it.errback(DontFail(4321))

        firstDeferred = None
        if cancelOnSecondDeferred:
            firstDeferred = Deferred()
        a = Deferred(cancel)
        d = self.sampleInlineCB(lambda: a, stacked=stacked, firstDeferred=firstDeferred)
        results = []
        d.addCallback(results.append)
        if firstDeferred:
            firstDeferred.callback(1)
        d.cancel()
        self.assertEquals(results, [4320])

    def test_ErrorToSuccessTranslation(self):
        self.doErrorToSuccessTranslation()

    def test_ErrorToSuccessTranslationStacked(self):
        self.doErrorToSuccessTranslation(stacked=True)

    def test_ErrorToSuccessTranslationStackedOnSecondDeferred(self):
        self.doErrorToSuccessTranslation(stacked=True, cancelOnSecondDeferred=True)

    def doAsynchronousCancellation(self, stacked=False, cancelOnSecondDeferred=False):
        """
        When C{D} is cancelled, it won't reach the callbacks added to it by
        application code until C{C} reaches the point in its callback chain
        where C{G} awaits it.  Otherwise, application code won't be able to
        track resource usage that C{D} may be using.
        """
        moreDeferred = Deferred()

        def deferMeMore(result):
            result.trap(CancelledError)
            return moreDeferred

        def deferMe():
            d = Deferred()
            d.addErrback(deferMeMore)
            return d

        firstDeferred = None
        if cancelOnSecondDeferred:
            firstDeferred = Deferred()
        d = self.sampleInlineCB(
            getChildDeferred=deferMe, stacked=stacked, firstDeferred=firstDeferred
        )
        if firstDeferred:
            firstDeferred.callback(1)
        d.cancel()
        self.assertNoResult(d)
        moreDeferred.callback(6543)
        self.assertEqual(self.successResultOf(d), 6544)

    def test_AsynchronousCancellation(self):
        self.doAsynchronousCancellation()

    def test_AsynchronousCancellationStacked(self):
        self.doAsynchronousCancellation(stacked=True)

    def test_AsynchronousCancellationStackedOnSecondDeferred(self):
        self.doAsynchronousCancellation(stacked=True, cancelOnSecondDeferred=True)
