# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.internet.defer}.
"""


import warnings
import gc
import functools
import traceback
import re

from asyncio import new_event_loop, Future, CancelledError

from twisted.python.reflect import requireModule
from twisted.python import failure, log
from twisted.trial import unittest
from twisted.internet import defer, reactor
from twisted.internet.task import Clock


contextvars = requireModule('contextvars')
if contextvars:
    contextvarsSkip = None
else:
    contextvarsSkip = "contextvars is not available"



def ensuringDeferred(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        result = f(*args, **kwargs)
        return defer.ensureDeferred(result)
    return wrapper



class GenericError(Exception):
    pass



def getDivisionFailure(*args, **kwargs):
    """
    Make a L{failure.Failure} of a divide-by-zero error.

    @param args: Any C{*args} are passed to Failure's constructor.
    @param kwargs: Any C{**kwargs} are passed to Failure's constructor.
    """
    try:
        1/0
    except:
        f = failure.Failure(*args, **kwargs)
    return f



def fakeCallbackCanceller(deferred):
    """
    A fake L{defer.Deferred} canceller which callbacks the L{defer.Deferred}
    with C{str} "Callback Result" when cancelling it.

    @param deferred: The cancelled L{defer.Deferred}.
    """
    deferred.callback("Callback Result")



class ImmediateFailureMixin(object):
    """
    Add additional assertion methods.
    """

    def assertImmediateFailure(self, deferred, exception):
        """
        Assert that the given Deferred current result is a Failure with the
        given exception.

        @return: The exception instance in the Deferred.
        """
        failures = []
        deferred.addErrback(failures.append)
        self.assertEqual(len(failures), 1)
        self.assertTrue(failures[0].check(exception))
        return failures[0].value



class UtilTests(unittest.TestCase):
    """
    Tests for utility functions.
    """

    def test_logErrorReturnsError(self):
        """
        L{defer.logError} returns the given error.
        """
        error = failure.Failure(RuntimeError())
        result = defer.logError(error)
        self.flushLoggedErrors(RuntimeError)

        self.assertIs(error, result)


    def test_logErrorLogsError(self):
        """
        L{defer.logError} logs the given error.
        """
        error = failure.Failure(RuntimeError())
        defer.logError(error)
        errors = self.flushLoggedErrors(RuntimeError)

        self.assertEqual(errors, [error])


    def test_logErrorLogsErrorNoRepr(self):
        """
        The text logged by L{defer.logError} has no repr of the failure.
        """
        output = []

        def emit(eventDict):
            output.append(log.textFromEventDict(eventDict))

        log.addObserver(emit)

        error = failure.Failure(RuntimeError())
        defer.logError(error)
        self.flushLoggedErrors(RuntimeError)

        self.assertTrue(output[0].startswith("Unhandled Error\nTraceback "))



class DeferredTests(unittest.SynchronousTestCase, ImmediateFailureMixin):

    def setUp(self):
        self.callbackResults = None
        self.errbackResults = None
        self.callback2Results = None
        # Restore the debug flag to its original state when done.
        self.addCleanup(defer.setDebugging, defer.getDebugging())

    def _callback(self, *args, **kw):
        self.callbackResults = args, kw
        return args[0]

    def _callback2(self, *args, **kw):
        self.callback2Results = args, kw

    def _errback(self, *args, **kw):
        self.errbackResults = args, kw

    def testCallbackWithoutArgs(self):
        deferred = defer.Deferred()
        deferred.addCallback(self._callback)
        deferred.callback("hello")
        self.assertIsNone(self.errbackResults)
        self.assertEqual(self.callbackResults, (('hello',), {}))

    def testCallbackWithArgs(self):
        deferred = defer.Deferred()
        deferred.addCallback(self._callback, "world")
        deferred.callback("hello")
        self.assertIsNone(self.errbackResults)
        self.assertEqual(self.callbackResults, (('hello', 'world'), {}))

    def testCallbackWithKwArgs(self):
        deferred = defer.Deferred()
        deferred.addCallback(self._callback, world="world")
        deferred.callback("hello")
        self.assertIsNone(self.errbackResults)
        self.assertEqual(self.callbackResults,
                             (('hello',), {'world': 'world'}))

    def testTwoCallbacks(self):
        deferred = defer.Deferred()
        deferred.addCallback(self._callback)
        deferred.addCallback(self._callback2)
        deferred.callback("hello")
        self.assertIsNone(self.errbackResults)
        self.assertEqual(self.callbackResults,
                             (('hello',), {}))
        self.assertEqual(self.callback2Results,
                             (('hello',), {}))

    def testDeferredList(self):
        defr1 = defer.Deferred()
        defr2 = defer.Deferred()
        defr3 = defer.Deferred()
        dl = defer.DeferredList([defr1, defr2, defr3])
        result = []
        def cb(resultList, result=result):
            result.extend(resultList)
        def catch(err):
            return None
        dl.addCallbacks(cb, cb)
        defr1.callback("1")
        defr2.addErrback(catch)
        # "catch" is added to eat the GenericError that will be passed on by
        # the DeferredList's callback on defr2. If left unhandled, the
        # Failure object would cause a log.err() warning about "Unhandled
        # error in Deferred". Twisted's pyunit watches for log.err calls and
        # treats them as failures. So "catch" must eat the error to prevent
        # it from flunking the test.
        defr2.errback(GenericError("2"))
        defr3.callback("3")
        self.assertEqual([result[0],
                    #result[1][1] is now a Failure instead of an Exception
                              (result[1][0], str(result[1][1].value)),
                              result[2]],

                             [(defer.SUCCESS, "1"),
                              (defer.FAILURE, "2"),
                              (defer.SUCCESS, "3")])

    def testEmptyDeferredList(self):
        result = []
        def cb(resultList, result=result):
            result.append(resultList)

        dl = defer.DeferredList([])
        dl.addCallbacks(cb)
        self.assertEqual(result, [[]])

        result[:] = []
        dl = defer.DeferredList([], fireOnOneCallback=1)
        dl.addCallbacks(cb)
        self.assertEqual(result, [])

    def testDeferredListFireOnOneError(self):
        defr1 = defer.Deferred()
        defr2 = defer.Deferred()
        defr3 = defer.Deferred()
        dl = defer.DeferredList([defr1, defr2, defr3], fireOnOneErrback=1)
        result = []
        dl.addErrback(result.append)

        # consume errors after they pass through the DeferredList (to avoid
        # 'Unhandled error in Deferred'.
        def catch(err):
            return None
        defr2.addErrback(catch)

        # fire one Deferred's callback, no result yet
        defr1.callback("1")
        self.assertEqual(result, [])

        # fire one Deferred's errback -- now we have a result
        defr2.errback(GenericError("from def2"))
        self.assertEqual(len(result), 1)

        # extract the result from the list
        aFailure = result[0]

        # the type of the failure is a FirstError
        self.assertTrue(issubclass(aFailure.type, defer.FirstError),
            'issubclass(aFailure.type, defer.FirstError) failed: '
            "failure's type is %r" % (aFailure.type,)
        )

        firstError = aFailure.value

        # check that the GenericError("2") from the deferred at index 1
        # (defr2) is intact inside failure.value
        self.assertEqual(firstError.subFailure.type, GenericError)
        self.assertEqual(firstError.subFailure.value.args, ("from def2",))
        self.assertEqual(firstError.index, 1)


    def testDeferredListDontConsumeErrors(self):
        d1 = defer.Deferred()
        dl = defer.DeferredList([d1])

        errorTrap = []
        d1.addErrback(errorTrap.append)

        result = []
        dl.addCallback(result.append)

        d1.errback(GenericError('Bang'))
        self.assertEqual('Bang', errorTrap[0].value.args[0])
        self.assertEqual(1, len(result))
        self.assertEqual('Bang', result[0][0][1].value.args[0])

    def testDeferredListConsumeErrors(self):
        d1 = defer.Deferred()
        dl = defer.DeferredList([d1], consumeErrors=True)

        errorTrap = []
        d1.addErrback(errorTrap.append)

        result = []
        dl.addCallback(result.append)

        d1.errback(GenericError('Bang'))
        self.assertEqual([], errorTrap)
        self.assertEqual(1, len(result))
        self.assertEqual('Bang', result[0][0][1].value.args[0])

    def testDeferredListFireOnOneErrorWithAlreadyFiredDeferreds(self):
        # Create some deferreds, and errback one
        d1 = defer.Deferred()
        d2 = defer.Deferred()
        d1.errback(GenericError('Bang'))

        # *Then* build the DeferredList, with fireOnOneErrback=True
        dl = defer.DeferredList([d1, d2], fireOnOneErrback=True)
        result = []
        dl.addErrback(result.append)
        self.assertEqual(1, len(result))

        d1.addErrback(lambda e: None)  # Swallow error

    def testDeferredListWithAlreadyFiredDeferreds(self):
        # Create some deferreds, and err one, call the other
        d1 = defer.Deferred()
        d2 = defer.Deferred()
        d1.errback(GenericError('Bang'))
        d2.callback(2)

        # *Then* build the DeferredList
        dl = defer.DeferredList([d1, d2])

        result = []
        dl.addCallback(result.append)

        self.assertEqual(1, len(result))

        d1.addErrback(lambda e: None)  # Swallow error


    def test_cancelDeferredList(self):
        """
        When cancelling an unfired L{defer.DeferredList}, cancel every
        L{defer.Deferred} in the list.
        """
        deferredOne = defer.Deferred()
        deferredTwo = defer.Deferred()
        deferredList = defer.DeferredList([deferredOne, deferredTwo])
        deferredList.cancel()
        self.failureResultOf(deferredOne, defer.CancelledError)
        self.failureResultOf(deferredTwo, defer.CancelledError)


    def test_cancelDeferredListCallback(self):
        """
        When cancelling an unfired L{defer.DeferredList} without the
        C{fireOnOneCallback} and C{fireOnOneErrback} flags set, the
        L{defer.DeferredList} will be callback with a C{list} of
        (success, result) C{tuple}s.
        """
        deferredOne = defer.Deferred(fakeCallbackCanceller)
        deferredTwo = defer.Deferred()
        deferredList = defer.DeferredList([deferredOne, deferredTwo])
        deferredList.cancel()
        self.failureResultOf(deferredTwo, defer.CancelledError)
        result = self.successResultOf(deferredList)
        self.assertTrue(result[0][0])
        self.assertEqual(result[0][1], "Callback Result")
        self.assertFalse(result[1][0])
        self.assertTrue(result[1][1].check(defer.CancelledError))


    def test_cancelDeferredListWithFireOnOneCallback(self):
        """
        When cancelling an unfired L{defer.DeferredList} with the flag
        C{fireOnOneCallback} set, cancel every L{defer.Deferred} in the list.
        """
        deferredOne = defer.Deferred()
        deferredTwo = defer.Deferred()
        deferredList = defer.DeferredList([deferredOne, deferredTwo],
                                          fireOnOneCallback=True)
        deferredList.cancel()
        self.failureResultOf(deferredOne, defer.CancelledError)
        self.failureResultOf(deferredTwo, defer.CancelledError)


    def test_cancelDeferredListWithFireOnOneCallbackAndDeferredCallback(self):
        """
        When cancelling an unfired L{defer.DeferredList} with the flag
        C{fireOnOneCallback} set, if one of the L{defer.Deferred} callbacks
        in its canceller, the L{defer.DeferredList} will callback with the
        result and the index of the L{defer.Deferred} in a C{tuple}.
        """
        deferredOne = defer.Deferred(fakeCallbackCanceller)
        deferredTwo = defer.Deferred()
        deferredList = defer.DeferredList([deferredOne, deferredTwo],
                                          fireOnOneCallback=True)
        deferredList.cancel()
        self.failureResultOf(deferredTwo, defer.CancelledError)
        result = self.successResultOf(deferredList)
        self.assertEqual(result, ("Callback Result", 0))


    def test_cancelDeferredListWithFireOnOneErrback(self):
        """
        When cancelling an unfired L{defer.DeferredList} with the flag
        C{fireOnOneErrback} set, cancel every L{defer.Deferred} in the list.
        """
        deferredOne = defer.Deferred()
        deferredTwo = defer.Deferred()
        deferredList = defer.DeferredList([deferredOne, deferredTwo],
                                          fireOnOneErrback=True)
        deferredList.cancel()
        self.failureResultOf(deferredOne, defer.CancelledError)
        self.failureResultOf(deferredTwo, defer.CancelledError)
        deferredListFailure = self.failureResultOf(deferredList,
                                                   defer.FirstError)
        firstError = deferredListFailure.value
        self.assertTrue(firstError.subFailure.check(defer.CancelledError))


    def test_cancelDeferredListWithFireOnOneErrbackAllDeferredsCallback(self):
        """
        When cancelling an unfired L{defer.DeferredList} with the flag
        C{fireOnOneErrback} set, if all the L{defer.Deferred} callbacks
        in its canceller, the L{defer.DeferredList} will callback with a
        C{list} of (success, result) C{tuple}s.
        """
        deferredOne = defer.Deferred(fakeCallbackCanceller)
        deferredTwo = defer.Deferred(fakeCallbackCanceller)
        deferredList = defer.DeferredList([deferredOne, deferredTwo],
                                          fireOnOneErrback=True)
        deferredList.cancel()
        result = self.successResultOf(deferredList)
        self.assertTrue(result[0][0])
        self.assertEqual(result[0][1], "Callback Result")
        self.assertTrue(result[1][0])
        self.assertEqual(result[1][1], "Callback Result")


    def test_cancelDeferredListWithOriginalDeferreds(self):
        """
        Cancelling a L{defer.DeferredList} will cancel the original
        L{defer.Deferred}s passed in.
        """
        deferredOne = defer.Deferred()
        deferredTwo = defer.Deferred()
        argumentList = [deferredOne, deferredTwo]
        deferredList = defer.DeferredList(argumentList)
        deferredThree = defer.Deferred()
        argumentList.append(deferredThree)
        deferredList.cancel()
        self.failureResultOf(deferredOne, defer.CancelledError)
        self.failureResultOf(deferredTwo, defer.CancelledError)
        self.assertNoResult(deferredThree)


    def test_cancelDeferredListWithException(self):
        """
        Cancelling a L{defer.DeferredList} will cancel every L{defer.Deferred}
        in the list even exceptions raised from the C{cancel} method of the
        L{defer.Deferred}s.
        """
        def cancellerRaisesException(deferred):
            """
            A L{defer.Deferred} canceller that raises an exception.

            @param deferred: The cancelled L{defer.Deferred}.
            """
            raise RuntimeError("test")
        deferredOne = defer.Deferred(cancellerRaisesException)
        deferredTwo = defer.Deferred()
        deferredList = defer.DeferredList([deferredOne, deferredTwo])
        deferredList.cancel()
        self.failureResultOf(deferredTwo, defer.CancelledError)
        errors = self.flushLoggedErrors(RuntimeError)
        self.assertEqual(len(errors), 1)


    def test_cancelFiredOnOneCallbackDeferredList(self):
        """
        When a L{defer.DeferredList} has fired because one L{defer.Deferred} in
        the list fired with a non-failure result, the cancellation will do
        nothing instead of cancelling the rest of the L{defer.Deferred}s.
        """
        deferredOne = defer.Deferred()
        deferredTwo = defer.Deferred()
        deferredList = defer.DeferredList([deferredOne, deferredTwo],
                                          fireOnOneCallback=True)
        deferredOne.callback(None)
        deferredList.cancel()
        self.assertNoResult(deferredTwo)


    def test_cancelFiredOnOneErrbackDeferredList(self):
        """
        When a L{defer.DeferredList} has fired because one L{defer.Deferred} in
        the list fired with a failure result, the cancellation will do
        nothing instead of cancelling the rest of the L{defer.Deferred}s.
        """
        deferredOne = defer.Deferred()
        deferredTwo = defer.Deferred()
        deferredList = defer.DeferredList([deferredOne, deferredTwo],
                                          fireOnOneErrback=True)
        deferredOne.errback(GenericError("test"))
        deferredList.cancel()
        self.assertNoResult(deferredTwo)
        self.failureResultOf(deferredOne, GenericError)
        self.failureResultOf(deferredList, defer.FirstError)


    def testImmediateSuccess(self):
        l = []
        d = defer.succeed("success")
        d.addCallback(l.append)
        self.assertEqual(l, ["success"])


    def testImmediateFailure(self):
        l = []
        d = defer.fail(GenericError("fail"))
        d.addErrback(l.append)
        self.assertEqual(str(l[0].value), "fail")

    def testPausedFailure(self):
        l = []
        d = defer.fail(GenericError("fail"))
        d.pause()
        d.addErrback(l.append)
        self.assertEqual(l, [])
        d.unpause()
        self.assertEqual(str(l[0].value), "fail")

    def testCallbackErrors(self):
        l = []
        d = defer.Deferred().addCallback(lambda _: 1 // 0).addErrback(l.append)
        d.callback(1)
        self.assertIsInstance(l[0].value, ZeroDivisionError)
        l = []
        d = defer.Deferred().addCallback(
            lambda _: failure.Failure(ZeroDivisionError())).addErrback(l.append)
        d.callback(1)
        self.assertIsInstance(l[0].value, ZeroDivisionError)

    def testUnpauseBeforeCallback(self):
        d = defer.Deferred()
        d.pause()
        d.addCallback(self._callback)
        d.unpause()

    def testReturnDeferred(self):
        d = defer.Deferred()
        d2 = defer.Deferred()
        d2.pause()
        d.addCallback(lambda r, d2=d2: d2)
        d.addCallback(self._callback)
        d.callback(1)
        assert self.callbackResults is None, "Should not have been called yet."
        d2.callback(2)
        assert self.callbackResults is None, "Still should not have been called yet."
        d2.unpause()
        assert self.callbackResults[0][0] == 2, "Result should have been from second deferred:%s" % (self.callbackResults,)


    def test_chainedPausedDeferredWithResult(self):
        """
        When a paused Deferred with a result is returned from a callback on
        another Deferred, the other Deferred is chained to the first and waits
        for it to be unpaused.
        """
        expected = object()
        paused = defer.Deferred()
        paused.callback(expected)
        paused.pause()
        chained = defer.Deferred()
        chained.addCallback(lambda ignored: paused)
        chained.callback(None)

        result = []
        chained.addCallback(result.append)
        self.assertEqual(result, [])
        paused.unpause()
        self.assertEqual(result, [expected])


    def test_pausedDeferredChained(self):
        """
        A paused Deferred encountered while pushing a result forward through a
        chain does not prevent earlier Deferreds from continuing to execute
        their callbacks.
        """
        first = defer.Deferred()
        second = defer.Deferred()
        first.addCallback(lambda ignored: second)
        first.callback(None)
        first.pause()
        second.callback(None)
        result = []
        second.addCallback(result.append)
        self.assertEqual(result, [None])


    def test_gatherResults(self):
        # test successful list of deferreds
        l = []
        defer.gatherResults([defer.succeed(1), defer.succeed(2)]).addCallback(l.append)
        self.assertEqual(l, [[1, 2]])
        # test failing list of deferreds
        l = []
        dl = [defer.succeed(1), defer.fail(ValueError())]
        defer.gatherResults(dl).addErrback(l.append)
        self.assertEqual(len(l), 1)
        self.assertIsInstance(l[0], failure.Failure)
        # get rid of error
        dl[1].addErrback(lambda e: 1)


    def test_gatherResultsWithConsumeErrors(self):
        """
        If a L{Deferred} in the list passed to L{gatherResults} fires with a
        failure and C{consumerErrors} is C{True}, the failure is converted to a
        L{None} result on that L{Deferred}.
        """
        # test successful list of deferreds
        dgood = defer.succeed(1)
        dbad = defer.fail(RuntimeError("oh noes"))
        d = defer.gatherResults([dgood, dbad], consumeErrors=True)
        unconsumedErrors = []
        dbad.addErrback(unconsumedErrors.append)
        gatheredErrors = []
        d.addErrback(gatheredErrors.append)

        self.assertEqual((len(unconsumedErrors), len(gatheredErrors)),
                         (0, 1))
        self.assertIsInstance(gatheredErrors[0].value, defer.FirstError)
        firstError = gatheredErrors[0].value.subFailure
        self.assertIsInstance(firstError.value, RuntimeError)


    def test_cancelGatherResults(self):
        """
        When cancelling the L{defer.gatherResults} call, all the
        L{defer.Deferred}s in the list will be cancelled.
        """
        deferredOne = defer.Deferred()
        deferredTwo = defer.Deferred()
        result = defer.gatherResults([deferredOne, deferredTwo])
        result.cancel()
        self.failureResultOf(deferredOne, defer.CancelledError)
        self.failureResultOf(deferredTwo, defer.CancelledError)
        gatherResultsFailure = self.failureResultOf(result, defer.FirstError)
        firstError = gatherResultsFailure.value
        self.assertTrue(firstError.subFailure.check(defer.CancelledError))


    def test_cancelGatherResultsWithAllDeferredsCallback(self):
        """
        When cancelling the L{defer.gatherResults} call, if all the
        L{defer.Deferred}s callback in their canceller, the L{defer.Deferred}
        returned by L{defer.gatherResults} will be callbacked with the C{list}
        of the results.
        """
        deferredOne = defer.Deferred(fakeCallbackCanceller)
        deferredTwo = defer.Deferred(fakeCallbackCanceller)
        result = defer.gatherResults([deferredOne, deferredTwo])
        result.cancel()
        callbackResult = self.successResultOf(result)
        self.assertEqual(callbackResult[0], "Callback Result")
        self.assertEqual(callbackResult[1], "Callback Result")


    def test_maybeDeferredSync(self):
        """
        L{defer.maybeDeferred} should retrieve the result of a synchronous
        function and pass it to its resulting L{defer.Deferred}.
        """
        S, E = [], []
        d = defer.maybeDeferred((lambda x: x + 5), 10)
        d.addCallbacks(S.append, E.append)
        self.assertEqual(E, [])
        self.assertEqual(S, [15])


    def test_maybeDeferredSyncError(self):
        """
        L{defer.maybeDeferred} should catch exception raised by a synchronous
        function and errback its resulting L{defer.Deferred} with it.
        """
        S, E = [], []
        try:
            '10' + 5
        except TypeError as e:
            expected = str(e)
        d = defer.maybeDeferred((lambda x: x + 5), '10')
        d.addCallbacks(S.append, E.append)
        self.assertEqual(S, [])
        self.assertEqual(len(E), 1)
        self.assertEqual(str(E[0].value), expected)


    def test_maybeDeferredAsync(self):
        """
        L{defer.maybeDeferred} should let L{defer.Deferred} instance pass by
        so that original result is the same.
        """
        d = defer.Deferred()
        d2 = defer.maybeDeferred(lambda: d)
        d.callback('Success')
        result = []
        d2.addCallback(result.append)
        self.assertEqual(result, ['Success'])


    def test_maybeDeferredAsyncError(self):
        """
        L{defer.maybeDeferred} should let L{defer.Deferred} instance pass by
        so that L{failure.Failure} returned by the original instance is the
        same.
        """
        d = defer.Deferred()
        d2 = defer.maybeDeferred(lambda: d)
        d.errback(failure.Failure(RuntimeError()))
        self.assertImmediateFailure(d2, RuntimeError)


    def test_innerCallbacksPreserved(self):
        """
        When a L{Deferred} encounters a result which is another L{Deferred}
        which is waiting on a third L{Deferred}, the middle L{Deferred}'s
        callbacks are executed after the third L{Deferred} fires and before the
        first receives a result.
        """
        results = []
        failures = []
        inner = defer.Deferred()
        def cb(result):
            results.append(('start-of-cb', result))
            d = defer.succeed('inner')
            def firstCallback(result):
                results.append(('firstCallback', 'inner'))
                return inner
            def secondCallback(result):
                results.append(('secondCallback', result))
                return result * 2
            d.addCallback(firstCallback).addCallback(secondCallback)
            d.addErrback(failures.append)
            return d
        outer = defer.succeed('outer')
        outer.addCallback(cb)
        inner.callback('orange')
        outer.addCallback(results.append)
        inner.addErrback(failures.append)
        outer.addErrback(failures.append)
        self.assertEqual([], failures)
        self.assertEqual(
            results,
            [('start-of-cb', 'outer'),
             ('firstCallback', 'inner'),
             ('secondCallback', 'orange'),
             'orangeorange'])


    def test_continueCallbackNotFirst(self):
        """
        The continue callback of a L{Deferred} waiting for another L{Deferred}
        is not necessarily the first one. This is somewhat a whitebox test
        checking that we search for that callback among the whole list of
        callbacks.
        """
        results = []
        failures = []
        a = defer.Deferred()

        def cb(result):
            results.append(('cb', result))
            d = defer.Deferred()

            def firstCallback(ignored):
                results.append(('firstCallback', ignored))
                return defer.gatherResults([a])

            def secondCallback(result):
                results.append(('secondCallback', result))

            d.addCallback(firstCallback)
            d.addCallback(secondCallback)
            d.addErrback(failures.append)
            d.callback(None)
            return d

        outer = defer.succeed('outer')
        outer.addCallback(cb)
        outer.addErrback(failures.append)
        self.assertEqual([('cb', 'outer'), ('firstCallback', None)], results)
        a.callback('withers')
        self.assertEqual([], failures)
        self.assertEqual(
            results,
            [('cb', 'outer'),
             ('firstCallback', None),
             ('secondCallback', ['withers'])])


    def test_callbackOrderPreserved(self):
        """
        A callback added to a L{Deferred} after a previous callback attached
        another L{Deferred} as a result is run after the callbacks of the other
        L{Deferred} are run.
        """
        results = []
        failures = []
        a = defer.Deferred()

        def cb(result):
            results.append(('cb', result))
            d = defer.Deferred()

            def firstCallback(ignored):
                results.append(('firstCallback', ignored))
                return defer.gatherResults([a])

            def secondCallback(result):
                results.append(('secondCallback', result))

            d.addCallback(firstCallback)
            d.addCallback(secondCallback)
            d.addErrback(failures.append)
            d.callback(None)
            return d

        outer = defer.Deferred()
        outer.addCallback(cb)
        outer.addCallback(lambda x: results.append('final'))
        outer.addErrback(failures.append)
        outer.callback('outer')
        self.assertEqual([('cb', 'outer'), ('firstCallback', None)], results)
        a.callback('withers')
        self.assertEqual([], failures)
        self.assertEqual(
            results,
            [('cb', 'outer'),
             ('firstCallback', None),
             ('secondCallback', ['withers']), 'final'])


    def test_reentrantRunCallbacks(self):
        """
        A callback added to a L{Deferred} by a callback on that L{Deferred}
        should be added to the end of the callback chain.
        """
        deferred = defer.Deferred()
        called = []
        def callback3(result):
            called.append(3)
        def callback2(result):
            called.append(2)
        def callback1(result):
            called.append(1)
            deferred.addCallback(callback3)
        deferred.addCallback(callback1)
        deferred.addCallback(callback2)
        deferred.callback(None)
        self.assertEqual(called, [1, 2, 3])


    def test_nonReentrantCallbacks(self):
        """
        A callback added to a L{Deferred} by a callback on that L{Deferred}
        should not be executed until the running callback returns.
        """
        deferred = defer.Deferred()
        called = []
        def callback2(result):
            called.append(2)
        def callback1(result):
            called.append(1)
            deferred.addCallback(callback2)
            self.assertEqual(called, [1])
        deferred.addCallback(callback1)
        deferred.callback(None)
        self.assertEqual(called, [1, 2])


    def test_reentrantRunCallbacksWithFailure(self):
        """
        After an exception is raised by a callback which was added to a
        L{Deferred} by a callback on that L{Deferred}, the L{Deferred} should
        call the first errback with a L{Failure} wrapping that exception.
        """
        exceptionMessage = "callback raised exception"
        deferred = defer.Deferred()
        def callback2(result):
            raise Exception(exceptionMessage)
        def callback1(result):
            deferred.addCallback(callback2)
        deferred.addCallback(callback1)
        deferred.callback(None)
        exception = self.assertImmediateFailure(deferred, Exception)
        self.assertEqual(exception.args, (exceptionMessage,))


    def test_synchronousImplicitChain(self):
        """
        If a first L{Deferred} with a result is returned from a callback on a
        second L{Deferred}, the result of the second L{Deferred} becomes the
        result of the first L{Deferred} and the result of the first L{Deferred}
        becomes L{None}.
        """
        result = object()
        first = defer.succeed(result)
        second = defer.Deferred()
        second.addCallback(lambda ign: first)
        second.callback(None)

        results = []
        first.addCallback(results.append)
        self.assertIsNone(results[0])
        second.addCallback(results.append)
        self.assertIs(results[1], result)


    def test_asynchronousImplicitChain(self):
        """
        If a first L{Deferred} without a result is returned from a callback on
        a second L{Deferred}, the result of the second L{Deferred} becomes the
        result of the first L{Deferred} as soon as the first L{Deferred} has
        one and the result of the first L{Deferred} becomes L{None}.
        """
        first = defer.Deferred()
        second = defer.Deferred()
        second.addCallback(lambda ign: first)
        second.callback(None)

        firstResult = []
        first.addCallback(firstResult.append)
        secondResult = []
        second.addCallback(secondResult.append)

        self.assertEqual(firstResult, [])
        self.assertEqual(secondResult, [])

        result = object()
        first.callback(result)

        self.assertEqual(firstResult, [None])
        self.assertEqual(secondResult, [result])


    def test_synchronousImplicitErrorChain(self):
        """
        If a first L{Deferred} with a L{Failure} result is returned from a
        callback on a second L{Deferred}, the first L{Deferred}'s result is
        converted to L{None} and no unhandled error is logged when it is
        garbage collected.
        """
        first = defer.fail(RuntimeError("First Deferred's Failure"))
        second = defer.Deferred()
        second.addCallback(lambda ign, first=first: first)
        second.callback(None)
        firstResult = []
        first.addCallback(firstResult.append)
        self.assertIsNone(firstResult[0])
        self.assertImmediateFailure(second, RuntimeError)


    def test_asynchronousImplicitErrorChain(self):
        """
        Let C{a} and C{b} be two L{Deferred}s.

        If C{a} has no result and is returned from a callback on C{b} then when
        C{a} fails, C{b}'s result becomes the L{Failure} that was C{a}'s result,
        the result of C{a} becomes L{None} so that no unhandled error is logged
        when it is garbage collected.
        """
        first = defer.Deferred()
        second = defer.Deferred()
        second.addCallback(lambda ign: first)
        second.callback(None)
        secondError = []
        second.addErrback(secondError.append)

        firstResult = []
        first.addCallback(firstResult.append)
        secondResult = []
        second.addCallback(secondResult.append)

        self.assertEqual(firstResult, [])
        self.assertEqual(secondResult, [])

        first.errback(RuntimeError("First Deferred's Failure"))
        self.assertTrue(secondError[0].check(RuntimeError))
        self.assertEqual(firstResult, [None])
        self.assertEqual(len(secondResult), 1)


    def test_doubleAsynchronousImplicitChaining(self):
        """
        L{Deferred} chaining is transitive.

        In other words, let A, B, and C be Deferreds.  If C is returned from a
        callback on B and B is returned from a callback on A then when C fires,
        A fires.
        """
        first = defer.Deferred()
        second = defer.Deferred()
        second.addCallback(lambda ign: first)
        third = defer.Deferred()
        third.addCallback(lambda ign: second)

        thirdResult = []
        third.addCallback(thirdResult.append)

        result = object()
        # After this, second is waiting for first to tell it to continue.
        second.callback(None)
        # And after this, third is waiting for second to tell it to continue.
        third.callback(None)

        # Still waiting
        self.assertEqual(thirdResult, [])

        # This will tell second to continue which will tell third to continue.
        first.callback(result)

        self.assertEqual(thirdResult, [result])


    def test_nestedAsynchronousChainedDeferreds(self):
        """
        L{Deferred}s can have callbacks that themselves return L{Deferred}s.
        When these "inner" L{Deferred}s fire (even asynchronously), the
        callback chain continues.
        """
        results = []
        failures = []

        # A Deferred returned in the inner callback.
        inner = defer.Deferred()

        def cb(result):
            results.append(('start-of-cb', result))
            d = defer.succeed('inner')

            def firstCallback(result):
                results.append(('firstCallback', 'inner'))
                # Return a Deferred that definitely has not fired yet, so we
                # can fire the Deferreds out of order.
                return inner

            def secondCallback(result):
                results.append(('secondCallback', result))
                return result * 2

            d.addCallback(firstCallback).addCallback(secondCallback)
            d.addErrback(failures.append)
            return d

        # Create a synchronous Deferred that has a callback 'cb' that returns
        # a Deferred 'd' that has fired but is now waiting on an unfired
        # Deferred 'inner'.
        outer = defer.succeed('outer')
        outer.addCallback(cb)
        outer.addCallback(results.append)
        # At this point, the callback 'cb' has been entered, and the first
        # callback of 'd' has been called.
        self.assertEqual(
            results, [('start-of-cb', 'outer'), ('firstCallback', 'inner')])

        # Once the inner Deferred is fired, processing of the outer Deferred's
        # callback chain continues.
        inner.callback('orange')

        # Make sure there are no errors.
        inner.addErrback(failures.append)
        outer.addErrback(failures.append)
        self.assertEqual(
            [], failures, "Got errbacks but wasn't expecting any.")

        self.assertEqual(
            results,
            [('start-of-cb', 'outer'),
             ('firstCallback', 'inner'),
             ('secondCallback', 'orange'),
             'orangeorange'])


    def test_nestedAsynchronousChainedDeferredsWithExtraCallbacks(self):
        """
        L{Deferred}s can have callbacks that themselves return L{Deferred}s.
        These L{Deferred}s can have other callbacks added before they are
        returned, which subtly changes the callback chain. When these "inner"
        L{Deferred}s fire (even asynchronously), the outer callback chain
        continues.
        """
        results = []
        failures = []

        # A Deferred returned in the inner callback after a callback is
        # added explicitly and directly to it.
        inner = defer.Deferred()

        def cb(result):
            results.append(('start-of-cb', result))
            d = defer.succeed('inner')

            def firstCallback(ignored):
                results.append(('firstCallback', ignored))
                # Return a Deferred that definitely has not fired yet with a
                # result-transforming callback so we can fire the Deferreds
                # out of order and see how the callback affects the ultimate
                # results.
                return inner.addCallback(lambda x: [x])

            def secondCallback(result):
                results.append(('secondCallback', result))
                return result * 2

            d.addCallback(firstCallback)
            d.addCallback(secondCallback)
            d.addErrback(failures.append)
            return d

        # Create a synchronous Deferred that has a callback 'cb' that returns
        # a Deferred 'd' that has fired but is now waiting on an unfired
        # Deferred 'inner'.
        outer = defer.succeed('outer')
        outer.addCallback(cb)
        outer.addCallback(results.append)
        # At this point, the callback 'cb' has been entered, and the first
        # callback of 'd' has been called.
        self.assertEqual(
            results, [('start-of-cb', 'outer'), ('firstCallback', 'inner')])

        # Once the inner Deferred is fired, processing of the outer Deferred's
        # callback chain continues.
        inner.callback('withers')

        # Make sure there are no errors.
        outer.addErrback(failures.append)
        inner.addErrback(failures.append)
        self.assertEqual(
            [], failures, "Got errbacks but wasn't expecting any.")

        self.assertEqual(
            results,
            [('start-of-cb', 'outer'),
             ('firstCallback', 'inner'),
             ('secondCallback', ['withers']),
             ['withers', 'withers']])


    def test_chainDeferredRecordsExplicitChain(self):
        """
        When we chain a L{Deferred}, that chaining is recorded explicitly.
        """
        a = defer.Deferred()
        b = defer.Deferred()
        b.chainDeferred(a)
        self.assertIs(a._chainedTo, b)


    def test_explicitChainClearedWhenResolved(self):
        """
        Any recorded chaining is cleared once the chaining is resolved, since
        it no longer exists.

        In other words, if one L{Deferred} is recorded as depending on the
        result of another, and I{that} L{Deferred} has fired, then the
        dependency is resolved and we no longer benefit from recording it.
        """
        a = defer.Deferred()
        b = defer.Deferred()
        b.chainDeferred(a)
        b.callback(None)
        self.assertIsNone(a._chainedTo)


    def test_chainDeferredRecordsImplicitChain(self):
        """
        We can chain L{Deferred}s implicitly by adding callbacks that return
        L{Deferred}s. When this chaining happens, we record it explicitly as
        soon as we can find out about it.
        """
        a = defer.Deferred()
        b = defer.Deferred()
        a.addCallback(lambda ignored: b)
        a.callback(None)
        self.assertIs(a._chainedTo, b)


    def test_circularChainWarning(self):
        """
        When a Deferred is returned from a callback directly attached to that
        same Deferred, a warning is emitted.
        """
        d = defer.Deferred()
        def circularCallback(result):
            return d
        d.addCallback(circularCallback)
        d.callback("foo")

        circular_warnings = self.flushWarnings([circularCallback])
        self.assertEqual(len(circular_warnings), 1)
        warning = circular_warnings[0]
        self.assertEqual(warning['category'], DeprecationWarning)
        pattern = "Callback returned the Deferred it was attached to"
        self.assertTrue(
            re.search(pattern, warning['message']),
            "\nExpected match: %r\nGot: %r" % (pattern, warning['message']))


    def test_circularChainException(self):
        """
        If the deprecation warning for circular deferred callbacks is
        configured to be an error, the exception will become the failure
        result of the Deferred.
        """
        self.addCleanup(setattr, warnings, "filters", warnings.filters)
        warnings.filterwarnings("error", category=DeprecationWarning)
        d = defer.Deferred()
        def circularCallback(result):
            return d
        d.addCallback(circularCallback)
        d.callback("foo")
        failure = self.failureResultOf(d)
        failure.trap(DeprecationWarning)


    def test_repr(self):
        """
        The C{repr()} of a L{Deferred} contains the class name and a
        representation of the internal Python ID.
        """
        d = defer.Deferred()
        address = id(d)
        self.assertEqual(
            repr(d), '<Deferred at 0x%x>' % (address,))


    def test_reprWithResult(self):
        """
        If a L{Deferred} has been fired, then its C{repr()} contains its
        result.
        """
        d = defer.Deferred()
        d.callback('orange')
        self.assertEqual(
            repr(d), "<Deferred at 0x%x current result: 'orange'>" % (
                id(d),))


    def test_reprWithChaining(self):
        """
        If a L{Deferred} C{a} has been fired, but is waiting on another
        L{Deferred} C{b} that appears in its callback chain, then C{repr(a)}
        says that it is waiting on C{b}.
        """
        a = defer.Deferred()
        b = defer.Deferred()
        b.chainDeferred(a)
        self.assertEqual(
            repr(a), "<Deferred at 0x%x waiting on Deferred at 0x%x>" % (
                id(a), id(b)))


    def test_boundedStackDepth(self):
        """
        The depth of the call stack does not grow as more L{Deferred} instances
        are chained together.
        """
        def chainDeferreds(howMany):
            stack = []
            def recordStackDepth(ignored):
                stack.append(len(traceback.extract_stack()))

            top = defer.Deferred()
            innerDeferreds = [defer.Deferred() for ignored in range(howMany)]
            originalInners = innerDeferreds[:]
            last = defer.Deferred()

            inner = innerDeferreds.pop()
            top.addCallback(lambda ign, inner=inner: inner)
            top.addCallback(recordStackDepth)

            while innerDeferreds:
                newInner = innerDeferreds.pop()
                inner.addCallback(lambda ign, inner=newInner: inner)
                inner = newInner
            inner.addCallback(lambda ign: last)

            top.callback(None)
            for inner in originalInners:
                inner.callback(None)

            # Sanity check - the record callback is not intended to have
            # fired yet.
            self.assertEqual(stack, [])

            # Now fire the last thing and return the stack depth at which the
            # callback was invoked.
            last.callback(None)
            return stack[0]

        # Callbacks should be invoked at the same stack depth regardless of
        # how many Deferreds are chained.
        self.assertEqual(chainDeferreds(1), chainDeferreds(2))


    def test_resultOfDeferredResultOfDeferredOfFiredDeferredCalled(self):
        """
        Given three Deferreds, one chained to the next chained to the next,
        callbacks on the middle Deferred which are added after the chain is
        created are called once the last Deferred fires.

        This is more of a regression-style test.  It doesn't exercise any
        particular code path through the current implementation of Deferred, but
        it does exercise a broken codepath through one of the variations of the
        implementation proposed as a resolution to ticket #411.
        """
        first = defer.Deferred()
        second = defer.Deferred()
        third = defer.Deferred()
        first.addCallback(lambda ignored: second)
        second.addCallback(lambda ignored: third)
        second.callback(None)
        first.callback(None)
        third.callback(None)
        L = []
        second.addCallback(L.append)
        self.assertEqual(L, [None])


    def test_errbackWithNoArgsNoDebug(self):
        """
        C{Deferred.errback()} creates a failure from the current Python
        exception.  When Deferred.debug is not set no globals or locals are
        captured in that failure.
        """
        defer.setDebugging(False)
        d = defer.Deferred()
        l = []
        exc = GenericError("Bang")
        try:
            raise exc
        except:
            d.errback()
        d.addErrback(l.append)
        fail = l[0]
        self.assertEqual(fail.value, exc)
        localz, globalz = fail.frames[0][-2:]
        self.assertEqual([], localz)
        self.assertEqual([], globalz)


    def test_errbackWithNoArgs(self):
        """
        C{Deferred.errback()} creates a failure from the current Python
        exception.  When Deferred.debug is set globals and locals are captured
        in that failure.
        """
        defer.setDebugging(True)
        d = defer.Deferred()
        l = []
        exc = GenericError("Bang")
        try:
            raise exc
        except:
            d.errback()
        d.addErrback(l.append)
        fail = l[0]
        self.assertEqual(fail.value, exc)
        localz, globalz = fail.frames[0][-2:]
        self.assertNotEqual([], localz)
        self.assertNotEqual([], globalz)


    def test_errorInCallbackDoesNotCaptureVars(self):
        """
        An error raised by a callback creates a Failure.  The Failure captures
        locals and globals if and only if C{Deferred.debug} is set.
        """
        d = defer.Deferred()
        d.callback(None)
        defer.setDebugging(False)
        def raiseError(ignored):
            raise GenericError("Bang")
        d.addCallback(raiseError)
        l = []
        d.addErrback(l.append)
        fail = l[0]
        localz, globalz = fail.frames[0][-2:]
        self.assertEqual([], localz)
        self.assertEqual([], globalz)


    def test_errorInCallbackCapturesVarsWhenDebugging(self):
        """
        An error raised by a callback creates a Failure.  The Failure captures
        locals and globals if and only if C{Deferred.debug} is set.
        """
        d = defer.Deferred()
        d.callback(None)
        defer.setDebugging(True)
        def raiseError(ignored):
            raise GenericError("Bang")
        d.addCallback(raiseError)
        l = []
        d.addErrback(l.append)
        fail = l[0]
        localz, globalz = fail.frames[0][-2:]
        self.assertNotEqual([], localz)
        self.assertNotEqual([], globalz)


    def test_inlineCallbacksTracebacks(self):
        """
        L{defer.inlineCallbacks} that re-raise tracebacks into their deferred
        should not lose their tracebacks.
        """
        f = getDivisionFailure()
        d = defer.Deferred()
        try:
            f.raiseException()
        except:
            d.errback()

        def ic(d):
            yield d
        ic = defer.inlineCallbacks(ic)
        newFailure = self.failureResultOf(d)
        tb = traceback.extract_tb(newFailure.getTracebackObject())

        self.assertEqual(len(tb), 3)
        self.assertIn('test_defer', tb[2][0])
        self.assertEqual('getDivisionFailure', tb[2][2])
        self.assertEqual('1/0', tb[2][3])

        self.assertIn('test_defer', tb[0][0])
        self.assertEqual('test_inlineCallbacksTracebacks', tb[0][2])
        self.assertEqual('f.raiseException()', tb[0][3])



class FirstErrorTests(unittest.SynchronousTestCase):
    """
    Tests for L{FirstError}.
    """
    def test_repr(self):
        """
        The repr of a L{FirstError} instance includes the repr of the value of
        the sub-failure and the index which corresponds to the L{FirstError}.
        """
        exc = ValueError("some text")
        try:
            raise exc
        except:
            f = failure.Failure()

        error = defer.FirstError(f, 3)
        self.assertEqual(
            repr(error),
            "FirstError[#3, %s]" % (repr(exc),))


    def test_str(self):
        """
        The str of a L{FirstError} instance includes the str of the
        sub-failure and the index which corresponds to the L{FirstError}.
        """
        exc = ValueError("some text")
        try:
            raise exc
        except:
            f = failure.Failure()

        error = defer.FirstError(f, 5)
        self.assertEqual(
            str(error),
            "FirstError[#5, %s]" % (str(f),))


    def test_comparison(self):
        """
        L{FirstError} instances compare equal to each other if and only if
        their failure and index compare equal.  L{FirstError} instances do not
        compare equal to instances of other types.
        """
        try:
            1 // 0
        except:
            firstFailure = failure.Failure()

        one = defer.FirstError(firstFailure, 13)
        anotherOne = defer.FirstError(firstFailure, 13)

        try:
            raise ValueError("bar")
        except:
            secondFailure = failure.Failure()

        another = defer.FirstError(secondFailure, 9)

        self.assertTrue(one == anotherOne)
        self.assertFalse(one == another)
        self.assertTrue(one != another)
        self.assertFalse(one != anotherOne)

        self.assertFalse(one == 10)



class AlreadyCalledTests(unittest.SynchronousTestCase):
    def setUp(self):
        self._deferredWasDebugging = defer.getDebugging()
        defer.setDebugging(True)

    def tearDown(self):
        defer.setDebugging(self._deferredWasDebugging)

    def _callback(self, *args, **kw):
        pass
    def _errback(self, *args, **kw):
        pass

    def _call_1(self, d):
        d.callback("hello")
    def _call_2(self, d):
        d.callback("twice")
    def _err_1(self, d):
        d.errback(failure.Failure(RuntimeError()))
    def _err_2(self, d):
        d.errback(failure.Failure(RuntimeError()))

    def testAlreadyCalled_CC(self):
        d = defer.Deferred()
        d.addCallbacks(self._callback, self._errback)
        self._call_1(d)
        self.assertRaises(defer.AlreadyCalledError, self._call_2, d)

    def testAlreadyCalled_CE(self):
        d = defer.Deferred()
        d.addCallbacks(self._callback, self._errback)
        self._call_1(d)
        self.assertRaises(defer.AlreadyCalledError, self._err_2, d)

    def testAlreadyCalled_EE(self):
        d = defer.Deferred()
        d.addCallbacks(self._callback, self._errback)
        self._err_1(d)
        self.assertRaises(defer.AlreadyCalledError, self._err_2, d)

    def testAlreadyCalled_EC(self):
        d = defer.Deferred()
        d.addCallbacks(self._callback, self._errback)
        self._err_1(d)
        self.assertRaises(defer.AlreadyCalledError, self._call_2, d)


    def _count(self, linetype, func, lines, expected):
        count = 0
        for line in lines:
            if (line.startswith(' %s:' % linetype) and
                line.endswith(' %s' % func)):
                count += 1
        self.assertTrue(count == expected)

    def _check(self, e, caller, invoker1, invoker2):
        # make sure the debugging information is vaguely correct
        lines = e.args[0].split("\n")
        # the creator should list the creator (testAlreadyCalledDebug) but not
        # _call_1 or _call_2 or other invokers
        self._count('C', caller, lines, 1)
        self._count('C', '_call_1', lines, 0)
        self._count('C', '_call_2', lines, 0)
        self._count('C', '_err_1', lines, 0)
        self._count('C', '_err_2', lines, 0)
        # invoker should list the first invoker but not the second
        self._count('I', invoker1, lines, 1)
        self._count('I', invoker2, lines, 0)

    def testAlreadyCalledDebug_CC(self):
        d = defer.Deferred()
        d.addCallbacks(self._callback, self._errback)
        self._call_1(d)
        try:
            self._call_2(d)
        except defer.AlreadyCalledError as e:
            self._check(e, "testAlreadyCalledDebug_CC", "_call_1", "_call_2")
        else:
            self.fail("second callback failed to raise AlreadyCalledError")

    def testAlreadyCalledDebug_CE(self):
        d = defer.Deferred()
        d.addCallbacks(self._callback, self._errback)
        self._call_1(d)
        try:
            self._err_2(d)
        except defer.AlreadyCalledError as e:
            self._check(e, "testAlreadyCalledDebug_CE", "_call_1", "_err_2")
        else:
            self.fail("second errback failed to raise AlreadyCalledError")

    def testAlreadyCalledDebug_EC(self):
        d = defer.Deferred()
        d.addCallbacks(self._callback, self._errback)
        self._err_1(d)
        try:
            self._call_2(d)
        except defer.AlreadyCalledError as e:
            self._check(e, "testAlreadyCalledDebug_EC", "_err_1", "_call_2")
        else:
            self.fail("second callback failed to raise AlreadyCalledError")

    def testAlreadyCalledDebug_EE(self):
        d = defer.Deferred()
        d.addCallbacks(self._callback, self._errback)
        self._err_1(d)
        try:
            self._err_2(d)
        except defer.AlreadyCalledError as e:
            self._check(e, "testAlreadyCalledDebug_EE", "_err_1", "_err_2")
        else:
            self.fail("second errback failed to raise AlreadyCalledError")

    def testNoDebugging(self):
        defer.setDebugging(False)
        d = defer.Deferred()
        d.addCallbacks(self._callback, self._errback)
        self._call_1(d)
        try:
            self._call_2(d)
        except defer.AlreadyCalledError as e:
            self.assertFalse(e.args)
        else:
            self.fail("second callback failed to raise AlreadyCalledError")


    def testSwitchDebugging(self):
        # Make sure Deferreds can deal with debug state flipping
        # around randomly.  This is covering a particular fixed bug.
        defer.setDebugging(False)
        d = defer.Deferred()
        d.addBoth(lambda ign: None)
        defer.setDebugging(True)
        d.callback(None)

        defer.setDebugging(False)
        d = defer.Deferred()
        d.callback(None)
        defer.setDebugging(True)
        d.addBoth(lambda ign: None)



class DeferredCancellerTests(unittest.SynchronousTestCase):
    def setUp(self):
        self.callbackResults = None
        self.errbackResults = None
        self.callback2Results = None
        self.cancellerCallCount = 0


    def tearDown(self):
        # Sanity check that the canceller was called at most once.
        self.assertIn(self.cancellerCallCount, (0, 1))


    def _callback(self, data):
        self.callbackResults = data
        return data


    def _callback2(self, data):
        self.callback2Results = data


    def _errback(self, data):
        self.errbackResults = data


    def test_noCanceller(self):
        """
        A L{defer.Deferred} without a canceller must errback with a
        L{defer.CancelledError} and not callback.
        """
        d = defer.Deferred()
        d.addCallbacks(self._callback, self._errback)
        d.cancel()
        self.assertEqual(self.errbackResults.type, defer.CancelledError)
        self.assertIsNone(self.callbackResults)


    def test_raisesAfterCancelAndCallback(self):
        """
        A L{defer.Deferred} without a canceller, when cancelled must allow
        a single extra call to callback, and raise
        L{defer.AlreadyCalledError} if callbacked or errbacked thereafter.
        """
        d = defer.Deferred()
        d.addCallbacks(self._callback, self._errback)
        d.cancel()

        # A single extra callback should be swallowed.
        d.callback(None)

        # But a second call to callback or errback is not.
        self.assertRaises(defer.AlreadyCalledError, d.callback, None)
        self.assertRaises(defer.AlreadyCalledError, d.errback, Exception())


    def test_raisesAfterCancelAndErrback(self):
        """
        A L{defer.Deferred} without a canceller, when cancelled must allow
        a single extra call to errback, and raise
        L{defer.AlreadyCalledError} if callbacked or errbacked thereafter.
        """
        d = defer.Deferred()
        d.addCallbacks(self._callback, self._errback)
        d.cancel()

        # A single extra errback should be swallowed.
        d.errback(Exception())

        # But a second call to callback or errback is not.
        self.assertRaises(defer.AlreadyCalledError, d.callback, None)
        self.assertRaises(defer.AlreadyCalledError, d.errback, Exception())


    def test_noCancellerMultipleCancelsAfterCancelAndCallback(self):
        """
        A L{Deferred} without a canceller, when cancelled and then
        callbacked, ignores multiple cancels thereafter.
        """
        d = defer.Deferred()
        d.addCallbacks(self._callback, self._errback)
        d.cancel()
        currentFailure = self.errbackResults
        # One callback will be ignored
        d.callback(None)
        # Cancel should have no effect.
        d.cancel()
        self.assertIs(currentFailure, self.errbackResults)


    def test_noCancellerMultipleCancelsAfterCancelAndErrback(self):
        """
        A L{defer.Deferred} without a canceller, when cancelled and then
        errbacked, ignores multiple cancels thereafter.
        """
        d = defer.Deferred()
        d.addCallbacks(self._callback, self._errback)
        d.cancel()
        self.assertEqual(self.errbackResults.type, defer.CancelledError)
        currentFailure = self.errbackResults
        # One errback will be ignored
        d.errback(GenericError())
        # I.e., we should still have a CancelledError.
        self.assertEqual(self.errbackResults.type, defer.CancelledError)
        d.cancel()
        self.assertIs(currentFailure, self.errbackResults)


    def test_noCancellerMultipleCancel(self):
        """
        Calling cancel multiple times on a deferred with no canceller
        results in a L{defer.CancelledError}. Subsequent calls to cancel
        do not cause an error.
        """
        d = defer.Deferred()
        d.addCallbacks(self._callback, self._errback)
        d.cancel()
        self.assertEqual(self.errbackResults.type, defer.CancelledError)
        currentFailure = self.errbackResults
        d.cancel()
        self.assertIs(currentFailure, self.errbackResults)


    def test_cancellerMultipleCancel(self):
        """
        Verify that calling cancel multiple times on a deferred with a
        canceller that does not errback results in a
        L{defer.CancelledError} and that subsequent calls to cancel do not
        cause an error and that after all that, the canceller was only
        called once.
        """
        def cancel(d):
            self.cancellerCallCount += 1

        d = defer.Deferred(canceller=cancel)
        d.addCallbacks(self._callback, self._errback)
        d.cancel()
        self.assertEqual(self.errbackResults.type, defer.CancelledError)
        currentFailure = self.errbackResults
        d.cancel()
        self.assertIs(currentFailure, self.errbackResults)
        self.assertEqual(self.cancellerCallCount, 1)


    def test_simpleCanceller(self):
        """
        Verify that a L{defer.Deferred} calls its specified canceller when
        it is cancelled, and that further call/errbacks raise
        L{defer.AlreadyCalledError}.
        """
        def cancel(d):
            self.cancellerCallCount += 1

        d = defer.Deferred(canceller=cancel)
        d.addCallbacks(self._callback, self._errback)
        d.cancel()
        self.assertEqual(self.cancellerCallCount, 1)
        self.assertEqual(self.errbackResults.type, defer.CancelledError)

        # Test that further call/errbacks are *not* swallowed
        self.assertRaises(defer.AlreadyCalledError, d.callback, None)
        self.assertRaises(defer.AlreadyCalledError, d.errback, Exception())


    def test_cancellerArg(self):
        """
        Verify that a canceller is given the correct deferred argument.
        """
        def cancel(d1):
            self.assertIs(d1, d)
        d = defer.Deferred(canceller=cancel)
        d.addCallbacks(self._callback, self._errback)
        d.cancel()


    def test_cancelAfterCallback(self):
        """
        Test that cancelling a deferred after it has been callbacked does
        not cause an error.
        """
        def cancel(d):
            self.cancellerCallCount += 1
            d.errback(GenericError())
        d = defer.Deferred(canceller=cancel)
        d.addCallbacks(self._callback, self._errback)
        d.callback('biff!')
        d.cancel()
        self.assertEqual(self.cancellerCallCount, 0)
        self.assertIsNone(self.errbackResults)
        self.assertEqual(self.callbackResults, 'biff!')


    def test_cancelAfterErrback(self):
        """
        Test that cancelling a L{Deferred} after it has been errbacked does
        not result in a L{defer.CancelledError}.
        """
        def cancel(d):
            self.cancellerCallCount += 1
            d.errback(GenericError())
        d = defer.Deferred(canceller=cancel)
        d.addCallbacks(self._callback, self._errback)
        d.errback(GenericError())
        d.cancel()
        self.assertEqual(self.cancellerCallCount, 0)
        self.assertEqual(self.errbackResults.type, GenericError)
        self.assertIsNone(self.callbackResults)


    def test_cancellerThatErrbacks(self):
        """
        Test a canceller which errbacks its deferred.
        """
        def cancel(d):
            self.cancellerCallCount += 1
            d.errback(GenericError())
        d = defer.Deferred(canceller=cancel)
        d.addCallbacks(self._callback, self._errback)
        d.cancel()
        self.assertEqual(self.cancellerCallCount, 1)
        self.assertEqual(self.errbackResults.type, GenericError)


    def test_cancellerThatCallbacks(self):
        """
        Test a canceller which calls its deferred.
        """
        def cancel(d):
            self.cancellerCallCount += 1
            d.callback('hello!')
        d = defer.Deferred(canceller=cancel)
        d.addCallbacks(self._callback, self._errback)
        d.cancel()
        self.assertEqual(self.cancellerCallCount, 1)
        self.assertEqual(self.callbackResults, 'hello!')
        self.assertIsNone(self.errbackResults)


    def test_cancelNestedDeferred(self):
        """
        Verify that a Deferred, a, which is waiting on another Deferred, b,
        returned from one of its callbacks, will propagate
        L{defer.CancelledError} when a is cancelled.
        """
        def innerCancel(d):
            self.cancellerCallCount += 1
        def cancel(d):
            self.assertTrue(False)

        b = defer.Deferred(canceller=innerCancel)
        a = defer.Deferred(canceller=cancel)
        a.callback(None)
        a.addCallback(lambda data: b)
        a.cancel()
        a.addCallbacks(self._callback, self._errback)
        # The cancel count should be one (the cancellation done by B)
        self.assertEqual(self.cancellerCallCount, 1)
        # B's canceller didn't errback, so defer.py will have called errback
        # with a CancelledError.
        self.assertEqual(self.errbackResults.type, defer.CancelledError)



class LogTests(unittest.SynchronousTestCase):
    """
    Test logging of unhandled errors.
    """

    def setUp(self):
        """
        Add a custom observer to observer logging.
        """
        self.c = []
        log.addObserver(self.c.append)

    def tearDown(self):
        """
        Remove the observer.
        """
        log.removeObserver(self.c.append)


    def _loggedErrors(self):
        return [e for e in self.c if e["isError"]]


    def _check(self):
        """
        Check the output of the log observer to see if the error is present.
        """
        c2 = self._loggedErrors()
        self.assertEqual(len(c2), 2)
        c2[1]["failure"].trap(ZeroDivisionError)
        self.flushLoggedErrors(ZeroDivisionError)

    def test_errorLog(self):
        """
        Verify that when a L{Deferred} with no references to it is fired,
        and its final result (the one not handled by any callback) is an
        exception, that exception will be logged immediately.
        """
        defer.Deferred().addCallback(lambda x: 1 // 0).callback(1)
        gc.collect()
        self._check()

    def test_errorLogWithInnerFrameRef(self):
        """
        Same as L{test_errorLog}, but with an inner frame.
        """
        def _subErrorLogWithInnerFrameRef():
            d = defer.Deferred()
            d.addCallback(lambda x: 1 // 0)
            d.callback(1)

        _subErrorLogWithInnerFrameRef()
        gc.collect()
        self._check()

    def test_errorLogWithInnerFrameCycle(self):
        """
        Same as L{test_errorLogWithInnerFrameRef}, plus create a cycle.
        """
        def _subErrorLogWithInnerFrameCycle():
            d = defer.Deferred()
            d.addCallback(lambda x, d=d: 1 // 0)
            d._d = d
            d.callback(1)

        _subErrorLogWithInnerFrameCycle()
        gc.collect()
        self._check()


    def test_errorLogNoRepr(self):
        """
        Verify that when a L{Deferred} with no references to it is fired,
        the logged message does not contain a repr of the failure object.
        """
        defer.Deferred().addCallback(lambda x: 1 // 0).callback(1)

        gc.collect()
        self._check()

        self.assertEqual(2, len(self.c))
        msg = log.textFromEventDict(self.c[-1])
        expected = "Unhandled Error\nTraceback "
        self.assertTrue(msg.startswith(expected),
                        "Expected message starting with: {0!r}".
                            format(expected))


    def test_errorLogDebugInfo(self):
        """
        Verify that when a L{Deferred} with no references to it is fired,
        the logged message includes debug info if debugging on the deferred
        is enabled.
        """
        def doit():
            d = defer.Deferred()
            d.debug = True
            d.addCallback(lambda x: 1 // 0)
            d.callback(1)

        doit()
        gc.collect()
        self._check()

        self.assertEqual(2, len(self.c))
        msg = log.textFromEventDict(self.c[-1])
        expected = "(debug:  I"
        self.assertTrue(msg.startswith(expected),
                        "Expected message starting with: {0!r}".
                            format(expected))


    def test_chainedErrorCleanup(self):
        """
        If one Deferred with an error result is returned from a callback on
        another Deferred, when the first Deferred is garbage collected it does
        not log its error.
        """
        d = defer.Deferred()
        d.addCallback(lambda ign: defer.fail(RuntimeError("zoop")))
        d.callback(None)

        # Sanity check - this isn't too interesting, but we do want the original
        # Deferred to have gotten the failure.
        results = []
        errors = []
        d.addCallbacks(results.append, errors.append)
        self.assertEqual(results, [])
        self.assertEqual(len(errors), 1)
        errors[0].trap(Exception)

        # Get rid of any references we might have to the inner Deferred (none of
        # these should really refer to it, but we're just being safe).
        del results, errors, d
        # Force a collection cycle so that there's a chance for an error to be
        # logged, if it's going to be logged.
        gc.collect()
        # And make sure it is not.
        self.assertEqual(self._loggedErrors(), [])


    def test_errorClearedByChaining(self):
        """
        If a Deferred with a failure result has an errback which chains it to
        another Deferred, the initial failure is cleared by the errback so it is
        not logged.
        """
        # Start off with a Deferred with a failure for a result
        bad = defer.fail(Exception("oh no"))
        good = defer.Deferred()
        # Give it a callback that chains it to another Deferred
        bad.addErrback(lambda ignored: good)
        # That's all, clean it up.  No Deferred here still has a failure result,
        # so nothing should be logged.
        good = bad = None
        gc.collect()
        self.assertEqual(self._loggedErrors(), [])



class DeferredListEmptyTests(unittest.SynchronousTestCase):
    def setUp(self):
        self.callbackRan = 0

    def testDeferredListEmpty(self):
        """Testing empty DeferredList."""
        dl = defer.DeferredList([])
        dl.addCallback(self.cb_empty)

    def cb_empty(self, res):
        self.callbackRan = 1
        self.assertEqual([], res)

    def tearDown(self):
        self.assertTrue(self.callbackRan, "Callback was never run.")



class OtherPrimitivesTests(unittest.SynchronousTestCase, ImmediateFailureMixin):
    def _incr(self, result):
        self.counter += 1

    def setUp(self):
        self.counter = 0

    def testLock(self):
        lock = defer.DeferredLock()
        lock.acquire().addCallback(self._incr)
        self.assertTrue(lock.locked)
        self.assertEqual(self.counter, 1)

        lock.acquire().addCallback(self._incr)
        self.assertTrue(lock.locked)
        self.assertEqual(self.counter, 1)

        lock.release()
        self.assertTrue(lock.locked)
        self.assertEqual(self.counter, 2)

        lock.release()
        self.assertFalse(lock.locked)
        self.assertEqual(self.counter, 2)

        self.assertRaises(TypeError, lock.run)

        firstUnique = object()
        secondUnique = object()

        controlDeferred = defer.Deferred()
        def helper(self, b):
            self.b = b
            return controlDeferred

        resultDeferred = lock.run(helper, self=self, b=firstUnique)
        self.assertTrue(lock.locked)
        self.assertEqual(self.b, firstUnique)

        resultDeferred.addCallback(lambda x: setattr(self, 'result', x))

        lock.acquire().addCallback(self._incr)
        self.assertTrue(lock.locked)
        self.assertEqual(self.counter, 2)

        controlDeferred.callback(secondUnique)
        self.assertEqual(self.result, secondUnique)
        self.assertTrue(lock.locked)
        self.assertEqual(self.counter, 3)

        d = lock.acquire().addBoth(lambda x: setattr(self, 'result', x))
        d.cancel()
        self.assertEqual(self.result.type, defer.CancelledError)

        lock.release()
        self.assertFalse(lock.locked)


    def test_cancelLockAfterAcquired(self):
        """
        When canceling a L{Deferred} from a L{DeferredLock} that already
        has the lock, the cancel should have no effect.
        """
        def _failOnErrback(_):
            self.fail("Unexpected errback call!")
        lock = defer.DeferredLock()
        d = lock.acquire()
        d.addErrback(_failOnErrback)
        d.cancel()


    def test_cancelLockBeforeAcquired(self):
        """
        When canceling a L{Deferred} from a L{DeferredLock} that does not
        yet have the lock (i.e., the L{Deferred} has not fired), the cancel
        should cause a L{defer.CancelledError} failure.
        """
        lock = defer.DeferredLock()
        lock.acquire()
        d = lock.acquire()
        d.cancel()
        self.assertImmediateFailure(d, defer.CancelledError)


    def testSemaphore(self):
        N = 13
        sem = defer.DeferredSemaphore(N)

        controlDeferred = defer.Deferred()
        def helper(self, arg):
            self.arg = arg
            return controlDeferred

        results = []
        uniqueObject = object()
        resultDeferred = sem.run(helper, self=self, arg=uniqueObject)
        resultDeferred.addCallback(results.append)
        resultDeferred.addCallback(self._incr)
        self.assertEqual(results, [])
        self.assertEqual(self.arg, uniqueObject)
        controlDeferred.callback(None)
        self.assertIsNone(results.pop())
        self.assertEqual(self.counter, 1)

        self.counter = 0
        for i in range(1, 1 + N):
            sem.acquire().addCallback(self._incr)
            self.assertEqual(self.counter, i)


        success = []
        def fail(r):
            success.append(False)
        def succeed(r):
            success.append(True)
        d = sem.acquire().addCallbacks(fail, succeed)
        d.cancel()
        self.assertEqual(success, [True])

        sem.acquire().addCallback(self._incr)
        self.assertEqual(self.counter, N)

        sem.release()
        self.assertEqual(self.counter, N + 1)

        for i in range(1, 1 + N):
            sem.release()
            self.assertEqual(self.counter, N + 1)


    def test_semaphoreInvalidTokens(self):
        """
        If the token count passed to L{DeferredSemaphore} is less than one
        then L{ValueError} is raised.
        """
        self.assertRaises(ValueError, defer.DeferredSemaphore, 0)
        self.assertRaises(ValueError, defer.DeferredSemaphore, -1)


    def test_cancelSemaphoreAfterAcquired(self):
        """
        When canceling a L{Deferred} from a L{DeferredSemaphore} that
        already has the semaphore, the cancel should have no effect.
        """
        def _failOnErrback(_):
            self.fail("Unexpected errback call!")

        sem = defer.DeferredSemaphore(1)
        d = sem.acquire()
        d.addErrback(_failOnErrback)
        d.cancel()


    def test_cancelSemaphoreBeforeAcquired(self):
        """
        When canceling a L{Deferred} from a L{DeferredSemaphore} that does
        not yet have the semaphore (i.e., the L{Deferred} has not fired),
        the cancel should cause a L{defer.CancelledError} failure.
        """
        sem = defer.DeferredSemaphore(1)
        sem.acquire()
        d = sem.acquire()
        d.cancel()
        self.assertImmediateFailure(d, defer.CancelledError)


    def testQueue(self):
        N, M = 2, 2
        queue = defer.DeferredQueue(N, M)

        gotten = []

        for i in range(M):
            queue.get().addCallback(gotten.append)
        self.assertRaises(defer.QueueUnderflow, queue.get)

        for i in range(M):
            queue.put(i)
            self.assertEqual(gotten, list(range(i + 1)))
        for i in range(N):
            queue.put(N + i)
            self.assertEqual(gotten, list(range(M)))
        self.assertRaises(defer.QueueOverflow, queue.put, None)

        gotten = []
        for i in range(N):
            queue.get().addCallback(gotten.append)
            self.assertEqual(gotten, list(range(N, N + i + 1)))

        queue = defer.DeferredQueue()
        gotten = []
        for i in range(N):
            queue.get().addCallback(gotten.append)
        for i in range(N):
            queue.put(i)
        self.assertEqual(gotten, list(range(N)))

        queue = defer.DeferredQueue(size=0)
        self.assertRaises(defer.QueueOverflow, queue.put, None)

        queue = defer.DeferredQueue(backlog=0)
        self.assertRaises(defer.QueueUnderflow, queue.get)


    def test_cancelQueueAfterSynchronousGet(self):
        """
        When canceling a L{Deferred} from a L{DeferredQueue} that already has
        a result, the cancel should have no effect.
        """
        def _failOnErrback(_):
            self.fail("Unexpected errback call!")

        queue = defer.DeferredQueue()
        d = queue.get()
        d.addErrback(_failOnErrback)
        queue.put(None)
        d.cancel()


    def test_cancelQueueAfterGet(self):
        """
        When canceling a L{Deferred} from a L{DeferredQueue} that does not
        have a result (i.e., the L{Deferred} has not fired), the cancel
        causes a L{defer.CancelledError} failure. If the queue has a result
        later on, it doesn't try to fire the deferred.
        """
        queue = defer.DeferredQueue()
        d = queue.get()
        d.cancel()
        self.assertImmediateFailure(d, defer.CancelledError)
        def cb(ignore):
            # If the deferred is still linked with the deferred queue, it will
            # fail with an AlreadyCalledError
            queue.put(None)
            return queue.get().addCallback(self.assertIs, None)
        d.addCallback(cb)
        done = []
        d.addCallback(done.append)
        self.assertEqual(len(done), 1)



class DeferredFilesystemLockTests(unittest.TestCase):
    """
    Test the behavior of L{DeferredFilesystemLock}
    """

    def setUp(self):
        self.clock = Clock()
        self.lock = defer.DeferredFilesystemLock(self.mktemp(),
                                                 scheduler=self.clock)


    def test_waitUntilLockedWithNoLock(self):
        """
        Test that the lock can be acquired when no lock is held
        """
        d = self.lock.deferUntilLocked(timeout=1)

        return d


    def test_waitUntilLockedWithTimeoutLocked(self):
        """
        Test that the lock can not be acquired when the lock is held
        for longer than the timeout.
        """
        self.assertTrue(self.lock.lock())

        d = self.lock.deferUntilLocked(timeout=5.5)
        self.assertFailure(d, defer.TimeoutError)

        self.clock.pump([1] * 10)

        return d


    def test_waitUntilLockedWithTimeoutUnlocked(self):
        """
        Test that a lock can be acquired while a lock is held
        but the lock is unlocked before our timeout.
        """
        def onTimeout(f):
            f.trap(defer.TimeoutError)
            self.fail("Should not have timed out")

        self.assertTrue(self.lock.lock())

        self.clock.callLater(1, self.lock.unlock)
        d = self.lock.deferUntilLocked(timeout=10)
        d.addErrback(onTimeout)

        self.clock.pump([1] * 10)

        return d


    def test_defaultScheduler(self):
        """
        Test that the default scheduler is set up properly.
        """
        lock = defer.DeferredFilesystemLock(self.mktemp())

        self.assertEqual(lock._scheduler, reactor)


    def test_concurrentUsage(self):
        """
        Test that an appropriate exception is raised when attempting
        to use deferUntilLocked concurrently.
        """
        self.lock.lock()
        self.clock.callLater(1, self.lock.unlock)

        d = self.lock.deferUntilLocked()
        d2 = self.lock.deferUntilLocked()

        self.assertFailure(d2, defer.AlreadyTryingToLockError)

        self.clock.advance(1)

        return d


    def test_multipleUsages(self):
        """
        Test that a DeferredFilesystemLock can be used multiple times
        """
        def lockAquired(ign):
            self.lock.unlock()
            d = self.lock.deferUntilLocked()
            return d

        self.lock.lock()
        self.clock.callLater(1, self.lock.unlock)

        d = self.lock.deferUntilLocked()
        d.addCallback(lockAquired)

        self.clock.advance(1)

        return d


    def test_cancelDeferUntilLocked(self):
        """
        When cancelling a L{defer.Deferred} returned by
        L{defer.DeferredFilesystemLock.deferUntilLocked}, the
        L{defer.DeferredFilesystemLock._tryLockCall} is cancelled.
        """
        self.lock.lock()
        deferred = self.lock.deferUntilLocked()
        tryLockCall = self.lock._tryLockCall
        deferred.cancel()
        self.assertFalse(tryLockCall.active())
        self.assertIsNone(self.lock._tryLockCall)
        self.failureResultOf(deferred, defer.CancelledError)


    def test_cancelDeferUntilLockedWithTimeout(self):
        """
        When cancel a L{defer.Deferred} returned by
        L{defer.DeferredFilesystemLock.deferUntilLocked}, if the timeout is
        set, the timeout call will be cancelled.
        """
        self.lock.lock()
        deferred = self.lock.deferUntilLocked(timeout=1)
        timeoutCall = self.lock._timeoutCall
        deferred.cancel()
        self.assertFalse(timeoutCall.active())
        self.assertIsNone(self.lock._timeoutCall)
        self.failureResultOf(deferred, defer.CancelledError)



def _overrideFunc(v, t):
    """
    Private function to be used to pass as an alternate onTimeoutCancel value
    to timeoutDeferred
    """
    return "OVERRIDDEN"



class DeferredAddTimeoutTests(unittest.SynchronousTestCase):
    """
    Tests for the function L{Deferred.addTimeout}
    """
    def test_timeoutChainable(self):
        """
        L{defer.Deferred.addTimeout} returns its own L{defer.Deferred} so it
        can be called in a callback chain.
        """
        d = defer.Deferred().addTimeout(5, Clock()).addCallback(lambda _: "done")
        d.callback(None)
        self.assertEqual("done", self.successResultOf(d))


    def test_successResultBeforeTimeout(self):
        """
        The L{defer.Deferred} callbacks with the result if it succeeds before
        the timeout. No cancellation happens after the callback either,
        which could also cancel inner deferreds.
        """
        clock = Clock()
        d = defer.Deferred()
        d.addTimeout(10, clock)

        # addTimeout is added first so that if d is timed out, d would be
        # canceled before innerDeferred gets returned from an callback on d
        innerDeferred = defer.Deferred()
        dCallbacked = [None]

        def onCallback(results):
            dCallbacked[0] = results
            return innerDeferred

        d.addCallback(onCallback)
        d.callback("results")

        # d is callbacked immediately, before innerDeferred is returned from
        # the callback on d
        self.assertIsNot(None, dCallbacked[0])
        self.assertEqual(dCallbacked[0], "results")

        # The timeout never happens - if it did, d would have been cancelled,
        # which would cancel innerDeferred too.
        clock.advance(15)
        self.assertNoResult(innerDeferred)


    def test_successResultBeforeTimeoutCustom(self):
        """
        The L{defer.Deferred} callbacks with the result if it succeeds before
        the timeout, even if a custom C{onTimeoutCancel} function is provided.
        No cancellation happens after the callback either, which could also
        cancel inner deferreds.
        """
        clock = Clock()
        d = defer.Deferred()
        d.addTimeout(10, clock, onTimeoutCancel=_overrideFunc)

        # addTimeout is added first so that if d is timed out, d would be
        # canceled before innerDeferred gets returned from an callback on d
        innerDeferred = defer.Deferred()
        dCallbacked = [None]

        def onCallback(results):
            dCallbacked[0] = results
            return innerDeferred

        d.addCallback(onCallback)
        d.callback("results")

        # d is callbacked immediately, before innerDeferred is returned from
        # the callback on d
        self.assertIsNot(None, dCallbacked[0])
        self.assertEqual(dCallbacked[0], "results")

        # The timeout never happens - if it did, d would have been cancelled,
        # which would cancel innerDeferred too
        clock.advance(15)
        self.assertNoResult(innerDeferred)


    def test_failureBeforeTimeout(self):
        """
        The L{defer.Deferred} errbacks with the failure if it fails before the
        timeout. No cancellation happens after the errback either, which
        could also cancel inner deferreds.
        """
        clock = Clock()
        d = defer.Deferred()
        d.addTimeout(10, clock)

        # addTimeout is added first so that if d is timed out, d would be
        # canceled before innerDeferred gets returned from an errback on d
        innerDeferred = defer.Deferred()
        dErrbacked = [None]
        error = ValueError("fail")

        def onErrback(f):
            dErrbacked[0] = f
            return innerDeferred

        d.addErrback(onErrback)
        d.errback(error)

        # d is errbacked immediately, before innerDeferred is returned from the
        # errback on d
        self.assertIsInstance(dErrbacked[0], failure.Failure)
        self.assertIs(dErrbacked[0].value, error)

        # The timeout never happens - if it did, d would have been cancelled,
        # which would cancel innerDeferred too
        clock.advance(15)
        self.assertNoResult(innerDeferred)


    def test_failureBeforeTimeoutCustom(self):
        """
        The L{defer.Deferred} errbacks with the failure if it fails before the
        timeout, even if using a custom C{onTimeoutCancel} function.
        No cancellation happens after the errback either, which could also
        cancel inner deferreds.
        """
        clock = Clock()
        d = defer.Deferred()
        d.addTimeout(10, clock, onTimeoutCancel=_overrideFunc)

        # addTimeout is added first so that if d is timed out, d would be
        # canceled before innerDeferred gets returned from an errback on d
        innerDeferred = defer.Deferred()
        dErrbacked = [None]
        error = ValueError("fail")

        def onErrback(f):
            dErrbacked[0] = f
            return innerDeferred

        d.addErrback(onErrback)
        d.errback(error)

        # d is errbacked immediately, before innerDeferred is returned from the
        # errback on d
        self.assertIsInstance(dErrbacked[0], failure.Failure)
        self.assertIs(dErrbacked[0].value, error)

        # The timeout never happens - if it did, d would have been cancelled,
        # which would cancel innerDeferred too
        clock.advance(15)
        self.assertNoResult(innerDeferred)


    def test_timedOut(self):
        """
        The L{defer.Deferred} by default errbacks with a L{defer.TimeoutError}
        if it times out before callbacking or errbacking.
        """
        clock = Clock()
        d = defer.Deferred()
        d.addTimeout(10, clock)
        self.assertNoResult(d)

        clock.advance(15)

        self.failureResultOf(d, defer.TimeoutError)


    def test_timedOutCustom(self):
        """
        If a custom C{onTimeoutCancel] function is provided, the
        L{defer.Deferred} returns the custom function's return value if the
        L{defer.Deferred} times out before callbacking or errbacking.
        The custom C{onTimeoutCancel} function can return a result instead of
        a failure.
        """
        clock = Clock()
        d = defer.Deferred()
        d.addTimeout(10, clock, onTimeoutCancel=_overrideFunc)
        self.assertNoResult(d)

        clock.advance(15)

        self.assertEqual("OVERRIDDEN", self.successResultOf(d))


    def test_timedOutProvidedCancelSuccess(self):
        """
        If a cancellation function is provided when the L{defer.Deferred} is
        initialized, the L{defer.Deferred} returns the cancellation value's
        non-failure return value when the L{defer.Deferred} times out.
        """
        clock = Clock()
        d = defer.Deferred(lambda c: c.callback('I was cancelled!'))
        d.addTimeout(10, clock)
        self.assertNoResult(d)

        clock.advance(15)

        self.assertEqual(self.successResultOf(d), 'I was cancelled!')


    def test_timedOutProvidedCancelFailure(self):
        """
        If a cancellation function is provided when the L{defer.Deferred} is
        initialized, the L{defer.Deferred} returns the cancellation value's
        non-L{CanceledError} failure when the L{defer.Deferred} times out.
        """
        clock = Clock()
        error = ValueError('what!')
        d = defer.Deferred(lambda c: c.errback(error))
        d.addTimeout(10, clock)
        self.assertNoResult(d)

        clock.advance(15)

        f = self.failureResultOf(d, ValueError)
        self.assertIs(f.value, error)


    def test_cancelBeforeTimeout(self):
        """
        If the L{defer.Deferred} is manually cancelled before the timeout, it
        is not re-cancelled (no L{AlreadyCancelled} error, and also no
        canceling of inner deferreds), and the default C{onTimeoutCancel}
        function is not called, preserving the original L{CancelledError}.
        """
        clock = Clock()
        d = defer.Deferred()
        d.addTimeout(10, clock)

        # addTimeout is added first so that if d is timed out, d would be
        # canceled before innerDeferred gets returned from an errback on d
        innerDeferred = defer.Deferred()
        dCanceled = [None]

        def onErrback(f):
            dCanceled[0] = f
            return innerDeferred

        d.addErrback(onErrback)
        d.cancel()

        # d is cancelled immediately, before innerDeferred is returned from the
        # errback on d
        self.assertIsInstance(dCanceled[0], failure.Failure)
        self.assertIs(dCanceled[0].type, defer.CancelledError)

        # The timeout never happens - if it did, d would have been cancelled
        # again, which would cancel innerDeferred too
        clock.advance(15)
        self.assertNoResult(innerDeferred)


    def test_cancelBeforeTimeoutCustom(self):
        """
        If the L{defer.Deferred} is manually cancelled before the timeout, it
        is not re-cancelled (no L{AlreadyCancelled} error, and also no
        canceling of inner deferreds), and the custom C{onTimeoutCancel}
        function is not called, preserving the original L{CancelledError}.
        """
        clock = Clock()
        d = defer.Deferred()
        d.addTimeout(10, clock, onTimeoutCancel=_overrideFunc)

        # addTimeout is added first so that if d is timed out, d would be
        # canceled before innerDeferred gets returned from an errback on d
        innerDeferred = defer.Deferred()
        dCanceled = [None]

        def onErrback(f):
            dCanceled[0] = f
            return innerDeferred

        d.addErrback(onErrback)
        d.cancel()

        # d is cancelled immediately, before innerDeferred is returned from the
        # errback on d
        self.assertIsInstance(dCanceled[0], failure.Failure)
        self.assertIs(dCanceled[0].type, defer.CancelledError)

        # The timeout never happens - if it did, d would have been cancelled
        # again, which would cancel innerDeferred too
        clock.advance(15)
        self.assertNoResult(innerDeferred)


    def test_providedCancelCalledBeforeTimeoutCustom(self):
        """
        A custom translation function can handle a L{defer.Deferred} with a
        custom cancellation function.
        """
        clock = Clock()
        d = defer.Deferred(lambda c: c.errback(ValueError('what!')))
        d.addTimeout(10, clock, onTimeoutCancel=_overrideFunc)
        self.assertNoResult(d)

        clock.advance(15)

        self.assertEqual("OVERRIDDEN", self.successResultOf(d))

    def test_errbackAddedBeforeTimeout(self):
        """
        An errback added before a timeout is added errbacks with a
        L{defer.CancelledError} when the timeout fires.  If the
        errback returns the L{defer.CancelledError}, it is translated
        to a L{defer.TimeoutError} by the timeout implementation.
        """
        clock = Clock()
        d = defer.Deferred()

        dErrbacked = [None]

        def errback(f):
            dErrbacked[0] = f
            return f

        d.addErrback(errback)
        d.addTimeout(10, clock)

        clock.advance(15)

        self.assertIsInstance(dErrbacked[0], failure.Failure)
        self.assertIsInstance(dErrbacked[0].value, defer.CancelledError)

        self.failureResultOf(d, defer.TimeoutError)


    def test_errbackAddedBeforeTimeoutSuppressesCancellation(self):
        """
        An errback added before a timeout is added errbacks with a
        L{defer.CancelledError} when the timeout fires.  If the
        errback suppresses the L{defer.CancelledError}, the deferred
        successfully completes.
        """
        clock = Clock()
        d = defer.Deferred()

        dErrbacked = [None]

        def errback(f):
            dErrbacked[0] = f
            f.trap(defer.CancelledError)

        d.addErrback(errback)
        d.addTimeout(10, clock)

        clock.advance(15)

        self.assertIsInstance(dErrbacked[0], failure.Failure)
        self.assertIsInstance(dErrbacked[0].value, defer.CancelledError)

        self.successResultOf(d)


    def test_errbackAddedBeforeTimeoutCustom(self):
        """
        An errback added before a timeout is added with a custom
        timeout function errbacks with a L{defer.CancelledError} when
        the timeout fires.  The timeout function runs if the errback
        returns the L{defer.CancelledError}.
        """
        clock = Clock()
        d = defer.Deferred()

        dErrbacked = [None]

        def errback(f):
            dErrbacked[0] = f
            return f

        d.addErrback(errback)
        d.addTimeout(10, clock, _overrideFunc)

        clock.advance(15)

        self.assertIsInstance(dErrbacked[0], failure.Failure)
        self.assertIsInstance(dErrbacked[0].value, defer.CancelledError)

        self.assertEqual("OVERRIDDEN", self.successResultOf(d))


    def test_errbackAddedBeforeTimeoutSuppressesCancellationCustom(self):
        """
        An errback added before a timeout is added with a custom
        timeout function errbacks with a L{defer.CancelledError} when
        the timeout fires.  The timeout function runs if the errback
        suppresses the L{defer.CancelledError}.
        """
        clock = Clock()
        d = defer.Deferred()

        dErrbacked = [None]

        def errback(f):
            dErrbacked[0] = f

        d.addErrback(errback)
        d.addTimeout(10, clock, _overrideFunc)

        clock.advance(15)

        self.assertIsInstance(dErrbacked[0], failure.Failure)
        self.assertIsInstance(dErrbacked[0].value, defer.CancelledError)

        self.assertEqual("OVERRIDDEN", self.successResultOf(d))


    def test_callbackAddedToCancelerBeforeTimeout(self):
        """
        Given a deferred with a cancellation function that resumes the
        callback chain, a callback that is added to the deferred
        before a timeout is added to runs when the timeout fires.  The
        deferred completes successfully, without a
        L{defer.TimeoutError}.
        """
        clock = Clock()
        success = "success"
        d = defer.Deferred(lambda d: d.callback(success))

        dCallbacked = [None]

        def callback(value):
            dCallbacked[0] = value
            return value

        d.addCallback(callback)
        d.addTimeout(10, clock)

        clock.advance(15)

        self.assertEqual(dCallbacked[0], success)

        self.assertIs(success, self.successResultOf(d))


    def test_callbackAddedToCancelerBeforeTimeoutCustom(self):
        """
        Given a deferred with a cancellation function that resumes the
        callback chain, a callback that is added to the deferred
        before a timeout is added to runs when the timeout fires.  The
        deferred completes successfully, without a
        L{defer.TimeoutError}.  The timeout's custom timeout function
        also runs.
        """
        clock = Clock()
        success = "success"
        d = defer.Deferred(lambda d: d.callback(success))

        dCallbacked = [None]

        def callback(value):
            dCallbacked[0] = value
            return value

        d.addCallback(callback)
        d.addTimeout(10, clock, onTimeoutCancel=_overrideFunc)

        clock.advance(15)

        self.assertEqual(dCallbacked[0], success)

        self.assertEqual("OVERRIDDEN", self.successResultOf(d))



class EnsureDeferredTests(unittest.TestCase):
    """
    Tests for L{twisted.internet.defer.ensureDeferred}.
    """

    def test_passesThroughDeferreds(self):
        """
        L{defer.ensureDeferred} will pass through a Deferred unchanged.
        """
        d = defer.Deferred()
        d2 = defer.ensureDeferred(d)
        self.assertIs(d, d2)


    def test_willNotAllowNonDeferredOrCoroutine(self):
        """
        Passing L{defer.ensureDeferred} a non-coroutine and a non-Deferred will
        raise a L{ValueError}.
        """
        with self.assertRaises(ValueError):
            defer.ensureDeferred("something")



class TimeoutErrorTests(unittest.TestCase, ImmediateFailureMixin):
    """
    L{twisted.internet.defer} timeout code.
    """
    def test_deprecatedTimeout(self):
        """
        L{twisted.internet.defer.timeout} is deprecated.
        """
        deferred = defer.Deferred()
        defer.timeout(deferred)
        self.assertFailure(deferred, defer.TimeoutError)
        warningsShown = self.flushWarnings([self.test_deprecatedTimeout])
        self.assertEqual(len(warningsShown), 1)
        self.assertIs(warningsShown[0]['category'], DeprecationWarning)
        self.assertEqual(
            warningsShown[0]['message'],
            'twisted.internet.defer.timeout was deprecated in Twisted 17.1.0;'
            ' please use twisted.internet.defer.Deferred.addTimeout instead')



def callAllSoonCalls(loop):
    """
    Tickle an asyncio event loop to call all of the things scheduled with
    call_soon, inasmuch as this can be done via the public API.

    @param loop: The asyncio event loop to flush the previously-called
        C{call_soon} entries from.
    """
    loop.call_soon(loop.stop)
    loop.run_forever()



class DeferredFutureAdapterTests(unittest.TestCase):

    def test_asFuture(self):
        """
        L{defer.Deferred.asFuture} returns a L{asyncio.Future} which fires when
        the given L{defer.Deferred} does.
        """
        d = defer.Deferred()
        loop = new_event_loop()
        aFuture = d.asFuture(loop)
        self.assertEqual(aFuture.done(), False)
        d.callback(13)
        callAllSoonCalls(loop)
        self.assertEqual(self.successResultOf(d), None)
        self.assertEqual(aFuture.result(), 13)


    def test_asFutureCancelFuture(self):
        """
        L{defer.Deferred.asFuture} returns a L{asyncio.Future} which, when
        cancelled, will cancel the original L{defer.Deferred}.
        """
        def canceler(dprime):
            canceler.called = True
        canceler.called = False
        d = defer.Deferred(canceler)
        loop = new_event_loop()
        aFuture = d.asFuture(loop)
        aFuture.cancel()
        callAllSoonCalls(loop)
        self.assertEqual(canceler.called, True)
        self.assertEqual(self.successResultOf(d), None)
        self.assertRaises(CancelledError, aFuture.result)


    def test_asFutureSuccessCancel(self):
        """
        While Futures don't support succeeding in response to cancellation,
        Deferreds do; if a Deferred is coerced into a success by a Future
        cancellation, that should just be ignored.
        """
        def canceler(dprime):
            dprime.callback(9)
        d = defer.Deferred(canceler)
        loop = new_event_loop()
        aFuture = d.asFuture(loop)
        aFuture.cancel()
        callAllSoonCalls(loop)
        self.assertEqual(self.successResultOf(d), None)
        self.assertRaises(CancelledError, aFuture.result)


    def test_asFutureFailure(self):
        """
        L{defer.Deferred.asFuture} makes a L{asyncio.Future} fire with an
        exception when the given L{defer.Deferred} does.
        """
        d = defer.Deferred()
        theFailure = failure.Failure(ZeroDivisionError())
        loop = new_event_loop()
        future = d.asFuture(loop)
        callAllSoonCalls(loop)
        d.errback(theFailure)
        callAllSoonCalls(loop)
        self.assertRaises(ZeroDivisionError, future.result)


    def test_fromFuture(self):
        """
        L{defer.Deferred.fromFuture} returns a L{defer.Deferred} that fires
        when the given L{asyncio.Future} does.
        """
        loop = new_event_loop()
        aFuture = Future(loop=loop)
        d = defer.Deferred.fromFuture(aFuture)
        self.assertNoResult(d)
        aFuture.set_result(7)
        callAllSoonCalls(loop)
        self.assertEqual(self.successResultOf(d), 7)


    def test_fromFutureFutureCancelled(self):
        """
        L{defer.Deferred.fromFuture} makes a L{defer.Deferred} fire with
        an L{asyncio.CancelledError} when the given
        L{asyncio.Future} is cancelled.
        """
        loop = new_event_loop()
        cancelled = Future(loop=loop)
        d = defer.Deferred.fromFuture(cancelled)
        cancelled.cancel()
        callAllSoonCalls(loop)
        self.assertRaises(CancelledError, cancelled.result)
        self.failureResultOf(d).trap(CancelledError)


    def test_fromFutureDeferredCancelled(self):
        """
        L{defer.Deferred.fromFuture} makes a L{defer.Deferred} which, when
        cancelled, cancels the L{asyncio.Future} it was created from.
        """
        loop = new_event_loop()
        cancelled = Future(loop=loop)
        d = defer.Deferred.fromFuture(cancelled)
        d.cancel()
        callAllSoonCalls(loop)
        self.assertEqual(cancelled.cancelled(), True)
        self.assertRaises(CancelledError, cancelled.result)
        self.failureResultOf(d).trap(CancelledError)



class DeferredContextVarsWithoutSupportTests(unittest.TestCase):

    if not contextvarsSkip:
        skip = "Requires contextvars support to be missing."

    def test_setContext(self):
        """
        setContext raises RuntimeError if it is used without contextvars
        support.
        """
        d = defer.Deferred()
        self.assertRaises(RuntimeError, d.setContext, None)


    def test_getContext(self):
        """
        getContext raises RuntimeError if it is used without contextvars
        support.
        """
        d = defer.Deferred()
        self.assertRaises(RuntimeError, d.getContext)



class DeferredContextVarsTests(unittest.TestCase):

    skip = contextvarsSkip

    def test_contextIsFromDeferredCreation(self):
        """
        Callbacks executed by Deferreds will have a copy of the context that
        the Deferred was created in.
        """
        var = contextvars.ContextVar("testvar")

        contexts = []

        def recordCurrentContext(_):
            contexts.append(var.get())

        var.set(1)

        d = defer.Deferred()
        d.addCallback(recordCurrentContext)

        var.set(2)

        d2 = defer.Deferred()
        d2.addCallback(recordCurrentContext)

        d.callback(True)
        d2.callback(True)

        self.assertEqual(contexts, [1, 2])


    def test_manualContext(self):
        """
        Passing a context to a Deferred will have it use that context and not
        the current one when it was instantiated.
        """
        var = contextvars.ContextVar("testvar")

        contexts = []

        def recordCurrentContext(_):
            contexts.append(var.get())

        var.set(1)

        manual_context = contextvars.Context()
        manual_context.run(lambda: var.set(3))

        self.assertEqual(var.get(), 1)

        d = defer.Deferred(context=manual_context)
        d.addCallback(recordCurrentContext)

        var.set(2)

        d2 = defer.Deferred()
        d2.addCallback(recordCurrentContext)

        d.callback(True)
        d2.callback(True)

        self.assertEqual(contexts, [3, 2])


    def test_setContext(self):
        """
        Calling setContext on a Deferred will have it use that context and not
        the current one when it was instantiated.
        """
        var = contextvars.ContextVar("testvar")

        contexts = []

        def recordCurrentContext(_):
            contexts.append(var.get())

        var.set(1)

        manualContext = contextvars.Context()
        manualContext.run(lambda: var.set(3))

        d = defer.Deferred()
        d.callback(True)
        d.addCallback(recordCurrentContext)

        # Set the context then add another callback to be run
        d.setContext(manualContext)
        d.addCallback(recordCurrentContext)

        # Check setting the outer context doesn't change it
        var.set(2)
        d.addCallback(recordCurrentContext)

        self.assertEqual(contexts, [1, 3, 3])


    def test_chainedDeferreds(self):
        """
        If a Deferred is chained to another paused Deferred, it uses its
        original context to call Deferreds when the paused Deferred becomes
        unpaused.
        """
        var = contextvars.ContextVar("testvar")
        var.set(1)

        results = []

        paused = defer.Deferred()
        paused.addCallback(
            lambda ignored: results.append(('paused', var.get()))
        )
        paused.pause()
        paused.callback(None)

        chained = defer.Deferred()
        # Set chained's context to have testvar=3
        chained.addCallback(lambda ignored: var.set(3))
        chained.addCallback(lambda ignored: paused)
        chained.addCallback(
            lambda ignored: results.append(('chained', var.get()))
        )
        chained.callback(None)

        # Set the test's context to have testvar=3
        var.set(2)

        # Nothing has happened yet because the Deferred is paused
        self.assertEqual(results, [])

        # Unpausing will mean that the callbacks will run, and they will dump
        # their unique contexts.
        paused.unpause()
        self.assertEqual(results, [('paused', 1), ('chained', 3)])
        self.assertEqual(var.get(), 2)

        # These contexts are not shared
        self.assertIsNot(paused.getContext(), chained.getContext())


    def test_withInlineCallbacks(self):
        """
        When an inlineCallbacks function is called, the context is taken from
        when it was first called. When it resumes, the same context is applied.
        """
        clock = Clock()

        var = contextvars.ContextVar("testvar")
        var.set(1)

        # This Deferred will set its own context to 3 when it is called
        mutatingDeferred = defer.Deferred()
        mutatingDeferred.addCallback(lambda _: var.set(3))

        mutatingDeferredThatFails = defer.Deferred()
        mutatingDeferredThatFails.addCallback(lambda _: var.set(4))
        mutatingDeferredThatFails.addCallback(lambda _: 1 / 0)

        @defer.inlineCallbacks
        def yieldingDeferred():
            d = defer.Deferred()
            clock.callLater(1, d.callback, True)
            yield d
            var.set(3)

        # context is 1 when the function is defined
        @defer.inlineCallbacks
        def testFunction():

            # Expected to be 2
            self.assertEqual(var.get(), 2)

            # Does not mutate the context
            yield defer.succeed(1)

            # Expected to be 2
            self.assertEqual(var.get(), 2)

            # mutatingDeferred mutates it to 3, but only in its Deferred chain
            clock.callLater(1, mutatingDeferred.callback, True)
            yield mutatingDeferred

            # When it resumes, it should still be 2
            self.assertEqual(var.get(), 2)

            # mutatingDeferredThatFails mutates it to 3, but only in its
            # Deferred chain
            clock.callLater(1, mutatingDeferredThatFails.callback, True)
            try:
                yield mutatingDeferredThatFails
            except Exception:
                self.assertEqual(var.get(), 2)
            else:
                raise Exception("???? should have failed")

            # IMPLEMENTATION DETAIL: Because inlineCallbacks must be at every
            # level, an inlineCallbacks function yielding another
            # inlineCallbacks function will NOT mutate the outer one's context,
            # as it is copied when the inner one is ran and mutated there.
            yield yieldingDeferred()
            self.assertEqual(var.get(), 2)

            defer.returnValue(True)

        # The inlineCallbacks context is 2 when it's called
        var.set(2)
        d = testFunction()

        # Advance the clock so mutatingDeferred triggers
        clock.advance(1)

        # Advance the clock so that mutatingDeferredThatFails triggers
        clock.advance(1)

        # Advance the clock so that yieldingDeferred triggers
        clock.advance(1)

        self.assertEqual(self.successResultOf(d), True)


    @ensuringDeferred
    async def test_asyncWithLock(self):
        """
        L{defer.DeferredLock} can be used as an asynchronous context manager.
        """
        lock = defer.DeferredLock()
        async with lock:
            self.assertTrue(lock.locked)
            d = lock.acquire()
            d.addCallback(lambda _: lock.release())
            self.assertTrue(lock.locked)
            self.assertFalse(d.called)
        self.assertTrue(d.called)
        await d
        self.assertFalse(lock.locked)


    @ensuringDeferred
    async def test_asyncWithSemaphore(self):
        """
        L{defer.DeferredSemaphore} can be used as an asynchronous context
        manager.
        """
        sem = defer.DeferredSemaphore(3)

        async with sem:
            self.assertEqual(sem.tokens, 2)
            async with sem:
                self.assertEqual(sem.tokens, 1)
                d1 = sem.acquire()
                d2 = sem.acquire()
                self.assertEqual(sem.tokens, 0)
                self.assertTrue(d1.called)
                self.assertFalse(d2.called)
            self.assertEqual(sem.tokens, 0)
            self.assertTrue(d2.called)
            d1.addCallback(lambda _: sem.release())
            d2.addCallback(lambda _: sem.release())
            await d1
            await d2
            self.assertEqual(sem.tokens, 2)
        self.assertEqual(sem.tokens, 3)

    @ensuringDeferred
    async def test_asyncWithLockException(self):
        """
        C{defer.DeferredLock} correctly propagates exceptions when
        used as an asynchronous context manager.
        """
        lock = defer.DeferredLock()
        with self.assertRaisesRegexp(Exception, 'some specific exception'):
            async with lock:
                self.assertTrue(lock.locked)
                raise Exception('some specific exception')
        self.assertFalse(lock.locked)


    def test_contextvarsWithAsyncAwait(self):
        """
        When a coroutine is called, the context is taken from when it was first
        called. When it resumes, the same context is applied.
        """
        clock = Clock()

        var = contextvars.ContextVar("testvar")
        var.set(1)

        # This Deferred will set its own context to 3 when it is called
        mutatingDeferred = defer.Deferred()
        mutatingDeferred.addCallback(lambda _: var.set(3))

        mutatingDeferredThatFails = defer.Deferred()
        mutatingDeferredThatFails.addCallback(lambda _: var.set(4))
        mutatingDeferredThatFails.addCallback(lambda _: 1 / 0)

        async def asyncFuncAwaitingDeferred():
            d = defer.Deferred()
            clock.callLater(1, d.callback, True)
            await d
            var.set(3)

        # context is 1 when the function is defined
        async def testFunction():

            # Expected to be 2
            self.assertEqual(var.get(), 2)

            # Does not mutate the context
            await defer.succeed(1)

            # Expected to be 2
            self.assertEqual(var.get(), 2)

            # mutatingDeferred mutates it to 3, but only in its Deferred chain
            clock.callLater(0, mutatingDeferred.callback, True)
            await mutatingDeferred

            # When it resumes, it should still be 2
            self.assertEqual(var.get(), 2)

            # mutatingDeferredThatFails mutates it to 3, but only in its
            # Deferred chain
            clock.callLater(1, mutatingDeferredThatFails.callback, True)
            try:
                await mutatingDeferredThatFails
            except Exception:
                self.assertEqual(var.get(), 2)
            else:
                raise Exception("???? should have failed")

            # If we await another async def-defined function, it will be able
            # to mutate the outer function's context, it is *not* frozen and
            # restored inside the function call.
            await asyncFuncAwaitingDeferred()
            self.assertEqual(var.get(), 3)

            return True

        # The inlineCallbacks context is 2 when it's called
        var.set(2)
        d = defer.ensureDeferred(testFunction())

        # Advance the clock so mutatingDeferred triggers
        clock.advance(1)

        # Advance the clock so that mutatingDeferredThatFails triggers
        clock.advance(1)

        # Advance the clock so that asyncFuncAwaitingDeferred triggers
        clock.advance(1)

        self.assertEqual(self.successResultOf(d), True)
