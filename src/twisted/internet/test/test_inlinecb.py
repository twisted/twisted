# -*- test-case-name: twisted.internet.test.test_inlinecb -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.inlineCallbacks}.
"""

import traceback
import unittest as pyunit
import weakref
from typing import Any, Generator, List, Set, Union
import sys
from unittest import skipIf

from twisted.internet import reactor, task
from twisted.internet.defer import (
    CancelledError,
    Deferred,
    Failure,
    fail,
    inlineCallbacks,
    returnValue,
    succeed,
)
from twisted.python.compat import _PYPY
from twisted.trial.unittest import SynchronousTestCase, TestCase


def getThing():
    d = Deferred()
    reactor.callLater(0, d.callback, "hi")
    return d


def getDivisionFailure(msg: Union[str, None] = None) -> Failure:
    """
    Make a L{Failure} of a divide-by-zero error.
    """
    try:
        raise ZeroDivisionError(msg)
    except BaseException:
        f = Failure()
    return f


class TerminalException(Exception):
    """
    Just a specific exception type for use in inlineCallbacks tests in this
    file.
    """

    pass


class BasicTests(TestCase):
    """
    This test suite tests basic use cases of L{inlineCallbacks}. For more
    complex tests see e.g. StackedInlineCallbacksTests.

    Note that it is important to directly call addCallbacks and other
    functions exposed as an API, because both L{inlineCallbacks} and
    L{Deferred} may be optimized in ways that are only exercised in particular
    situations.
    """

    def testBasics(self):
        """
        Test that a normal inlineCallbacks works.  Tests yielding a
        deferred which callbacks, as well as a deferred errbacks. Also
        ensures returning a final value works.
        """

        @inlineCallbacks
        def _genBasics():
            x = yield getThing()

            self.assertEqual(x, "hi")

            try:
                yield getDivisionFailure("OMG")
            except ZeroDivisionError as e:
                self.assertEqual(str(e), "OMG")
            returnValue("WOOSH")

        return _genBasics().addCallback(self.assertEqual, "WOOSH")

    def testProducesException(self):
        """
        Ensure that a generator that produces an exception signals
        a Failure condition on result deferred by converting the exception to
        a L{Failure}.
        """

        @inlineCallbacks
        def _genProduceException():
            yield getThing()
            1 / 0

        return self.assertFailure(_genProduceException(), ZeroDivisionError)

    def testNothing(self):
        """Test that a generator which never yields results in None."""

        @inlineCallbacks
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

        @inlineCallbacks
        def _genHandledTerminalFailure():
            try:
                yield fail(TerminalException("Handled Terminal Failure"))
            except TerminalException:
                pass

        return _genHandledTerminalFailure().addCallback(self.assertEqual, None)

    def testHandledTerminalAsyncFailure(self):
        """
        Just like testHandledTerminalFailure, only with a Deferred which fires
        asynchronously with an error.
        """

        @inlineCallbacks
        def _genHandledTerminalAsyncFailure(d):
            try:
                yield d
            except TerminalException:
                pass

        d = Deferred()
        deferredGeneratorResultDeferred = _genHandledTerminalAsyncFailure(d)
        d.errback(TerminalException("Handled Terminal Failure"))
        return deferredGeneratorResultDeferred.addCallback(self.assertEqual, None)

    def testStackUsage(self):
        """
        Make sure we don't blow the stack when yielding immediately
        available deferreds.
        """

        @inlineCallbacks
        def _genStackUsage():
            for x in range(5000):
                # Test with yielding a deferred
                yield succeed(1)
            returnValue(0)

        return _genStackUsage().addCallback(self.assertEqual, 0)

    def testStackUsage2(self):
        """
        Make sure we don't blow the stack when yielding immediately
        available values.
        """

        @inlineCallbacks
        def _genStackUsage2():
            for x in range(5000):
                # Test with yielding a random value
                yield 1
            returnValue(0)

        return _genStackUsage2().addCallback(self.assertEqual, 0)

    def testYieldNonDeferred(self):
        """
        Ensure that yielding a non-deferred passes it back as the
        result of the yield expression.

        @return: A L{twisted.internet.Deferred}
        @rtype: L{twisted.internet.Deferred}
        """

        def _test():
            yield 5
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

        self.assertIn("inlineCallbacks", str(self.assertRaises(TypeError, _noYield)))

    def test_nonGeneratorReturnValue(self):
        """
        Ensure that C{TypeError} with a message about L{inlineCallbacks} is
        raised when a non-generator calls L{returnValue}.
        """

        def _noYield():
            returnValue(5)

        _noYield = inlineCallbacks(_noYield)

        self.assertIn("inlineCallbacks", str(self.assertRaises(TypeError, _noYield)))

    def test_internalDefGenReturnValueDoesntLeak(self):
        """
        When one inlineCallbacks calls another, the internal L{_DefGen_Return}
        flow control exception raised by calling L{defer.returnValue} doesn't
        leak into tracebacks captured in the caller.
        """
        clock = task.Clock()

        @inlineCallbacks
        def _returns():
            """
            This is the inner function using returnValue.
            """
            yield task.deferLater(clock, 0)
            returnValue("actual-value-not-used-for-the-test")

        @inlineCallbacks
        def _raises():
            try:
                yield _returns()
                raise TerminalException("boom returnValue")
            except TerminalException:
                return traceback.format_exc()

        d = _raises()
        clock.advance(0)
        tb = self.successResultOf(d)

        # The internal exception is not in the traceback.
        self.assertNotIn("_DefGen_Return", tb)
        # No other extra exception is in the traceback.
        self.assertNotIn(
            "During handling of the above exception, another exception occurred", tb
        )
        # Our targeted exception is in the traceback
        self.assertIn("test_inlinecb.TerminalException: boom returnValue", tb)

    def test_internalStopIterationDoesntLeak(self):
        """
        When one inlineCallbacks calls another, the internal L{StopIteration}
        flow control exception generated when the inner generator returns
        doesn't leak into tracebacks captured in the caller.

        This is similar to C{test_internalDefGenReturnValueDoesntLeak} but the
        inner function uses the "normal" return statemement rather than the
        C{returnValue} helper.
        """
        clock = task.Clock()

        @inlineCallbacks
        def _returns():
            yield task.deferLater(clock, 0)
            return 6

        @inlineCallbacks
        def _raises():
            try:
                yield _returns()
                raise TerminalException("boom normal return")
            except TerminalException:
                return traceback.format_exc()

        d = _raises()
        clock.advance(0)
        tb = self.successResultOf(d)

        # The internal exception is not in the traceback.
        self.assertNotIn("StopIteration", tb)
        # No other extra exception is in the traceback.
        self.assertNotIn(
            "During handling of the above exception, another exception occurred", tb
        )
        # Our targeted exception is in the traceback
        self.assertIn("test_inlinecb.TerminalException: boom normal return", tb)

    @pyunit.skipIf(_PYPY, "GC works differently on PyPy.")
    def test_inlineCallbacksNoCircularReference(self) -> None:
        """
        When using L{defer.inlineCallbacks}, after the function exits, it will
        not keep references to the function itself or the arguments.

        This ensures that the machinery gets deallocated immediately rather than
        waiting for a GC, on CPython.

        The GC on PyPy works differently (del doesn't immediately deallocate the
        object), so we skip the test.
        """

        # Create an object and weak reference to track if its gotten freed.
        obj: Set[Any] = set()
        objWeakRef = weakref.ref(obj)

        @inlineCallbacks
        def func(a: Any) -> Any:
            yield a
            return a

        # Run the function
        funcD = func(obj)
        self.assertEqual(obj, self.successResultOf(funcD))

        funcDWeakRef = weakref.ref(funcD)

        # Delete the local references to obj and funcD.
        del obj
        del funcD

        # The object has been freed if the weak reference returns None.
        self.assertIsNone(objWeakRef())
        self.assertIsNone(funcDWeakRef())


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
    @skipIf(sys.version_info > (3, 12), "Needs Python 3.12 or older")
    def test_forwardTracebacks_312(self):
        """
        Chained inlineCallbacks are forwarding the traceback information
        from generator to generator.

        A first simple test with a couple of inline callbacks for Python 3.12 and older.
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
        self.assertIn("erroring", tb)
        self.assertIn("in calling", tb)
        self.assertIn("Error Marker", tb)

    @skipIf(sys.version_info < (3, 13), "Needs Python 3.13 or newer")
    def test_forwardTracebacks_313(self):
        """
        Chained inlineCallbacks are forwarding the traceback information
        from generator to generator.

        A first simple test with a couple of inline callbacks for Python 3.13 and later.
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
        self.assertIn("yield erroring", tb)
        self.assertIn("in calling", tb)
        self.assertIn("Error Marker", tb)

    @skipIf(sys.version_info > (3, 12), "Needs Python 3.12 or older")
    def test_forwardLotsOfTracebacks_312(self):
        """
        Several Chained inlineCallbacks gives information about all generators.

        A wider test with 4 chained inline callbacks.

        Application stack-trace should not be reported.

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

    @skipIf(sys.version_info < (3, 13), "Needs Python 3.13 or newer")
    def test_forwardLotsOfTracebacks_313(self):
        """
        Several Chained inlineCallbacks gives information about all generators.

        A wider test with 4 chained inline callbacks.

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

    def test_reraiseTracebacksFromDeferred(self) -> None:
        """
        L{defer.inlineCallbacks} that receives tracebacks from a regular Deferred and
        re-raise tracebacks into their deferred should not lose their tracebacks.
        """
        f = getDivisionFailure("msg")
        d: Deferred[None] = Deferred()
        try:
            f.raiseException()
        except BaseException:
            d.errback()

        def ic(d: object) -> Generator[Any, Any, None]:
            """
            This is never called.
            It is only used as the decorated function.
            The resulting function is never called in this test.
            This is used to make sure that if we wrap
            an already failed deferred, inlineCallbacks
            will not add any extra traceback frames.
            """
            yield d  # pragma: no cover

        inlineCallbacks(ic)
        newFailure = self.failureResultOf(d)
        tb = traceback.extract_tb(newFailure.getTracebackObject())

        self.assertEqual(len(tb), 3)
        self.assertIn("test_inlinecb", tb[2][0])
        self.assertEqual("getDivisionFailure", tb[2][2])
        self.assertEqual("raise ZeroDivisionError(msg)", tb[2][3])

        self.assertIn("test_inlinecb", tb[0][0])
        self.assertEqual("test_reraiseTracebacksFromDeferred", tb[0][2])
        self.assertEqual("f.raiseException()", tb[0][3])

    @skipIf(sys.version_info < (3, 13), 'new in Python 3.13')
    def test_forwardLotsOfTracebacks313(self):
        """
        Several Chained inlineCallbacks gives information about all generators.

        A wider test with a 4 chained inline callbacks.
        Application stack-trace should be reported for Python 3.13, but not
        earlier versions.

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
        self.assertIn("in calling", tb)
        self.assertIn("yield calling2", tb)
        self.assertIn("throwExceptionIntoGenerator", tb)
        self.assertIn("Error Marker", tb)


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

    def test_inlineCallbacksCancelCaptured(self) -> None:
        """
        Cancelling an L{defer.inlineCallbacks} correctly handles the function
        catching the L{defer.CancelledError}.

        The desired behavior is:
            1. If the function is waiting on an inner deferred, that inner
               deferred is cancelled, and a L{defer.CancelledError} is raised
               within the function.
            2. If the function catches that exception, execution continues, and
               the deferred returned by the function is not resolved.
            3. Cancelling the deferred again cancels any deferred the function
               is waiting on, and the exception is raised.
        """
        canceller1Calls: List[Deferred[object]] = []
        canceller2Calls: List[Deferred[object]] = []
        d1: Deferred[object] = Deferred(canceller1Calls.append)
        d2: Deferred[object] = Deferred(canceller2Calls.append)

        @inlineCallbacks
        def testFunc() -> Generator[Deferred[object], object, None]:
            try:
                yield d1
            except Exception:
                pass

            yield d2

        # Call the function, and ensure that none of the deferreds have
        # completed or been cancelled yet.
        funcD = testFunc()

        self.assertNoResult(d1)
        self.assertNoResult(d2)
        self.assertNoResult(funcD)
        self.assertEqual(canceller1Calls, [])
        self.assertEqual(canceller1Calls, [])

        # Cancel the deferred returned by the function, and check that the first
        # inner deferred has been cancelled, but the returned deferred has not
        # completed (as the function catches the raised exception).
        funcD.cancel()

        self.assertEqual(canceller1Calls, [d1])
        self.assertEqual(canceller2Calls, [])
        self.assertNoResult(funcD)

        # Cancel the returned deferred again, this time the returned deferred
        # should have a failure result, as the function did not catch the cancel
        # exception raised by `d2`.
        funcD.cancel()
        failure = self.failureResultOf(funcD)
        self.assertEqual(failure.type, CancelledError)
        self.assertEqual(canceller2Calls, [d2])
