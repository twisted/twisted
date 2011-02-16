# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Python 2.5+ test cases for failures thrown into generators.
"""

import sys
import traceback

from twisted.trial.unittest import TestCase

from twisted.python.failure import Failure
from twisted.internet import defer

# Re-implement getDivisionFailure here instead of using the one in
# test_failure.py in order to avoid creating a cyclic dependency.
def getDivisionFailure():
    try:
        1/0
    except:
        f = Failure()
    return f



class TwoPointFiveFailureTests(TestCase):

    def test_inlineCallbacksTracebacks(self):
        """
        inlineCallbacks that re-raise tracebacks into their deferred
        should not lose their tracebacsk.
        """
        f = getDivisionFailure()
        d = defer.Deferred()
        try:
            f.raiseException()
        except:
            d.errback()

        failures = []
        def collect_error(result):
            failures.append(result)

        def ic(d):
            yield d
        ic = defer.inlineCallbacks(ic)
        ic(d).addErrback(collect_error)

        newFailure, = failures
        self.assertEquals(
            traceback.extract_tb(newFailure.getTracebackObject())[-1][-1],
            "1/0"
        )


    def _throwIntoGenerator(self, f, g):
        try:
            f.throwExceptionIntoGenerator(g)
        except StopIteration:
            pass
        else:
            self.fail("throwExceptionIntoGenerator should have raised "
                      "StopIteration")

    def test_throwExceptionIntoGenerator(self):
        """
        It should be possible to throw the exception that a Failure
        represents into a generator.
        """
        stuff = []
        def generator():
            try:
                yield
            except:
                stuff.append(sys.exc_info())
            else:
                self.fail("Yield should have yielded exception.")
        g = generator()
        f = getDivisionFailure()
        g.next()
        self._throwIntoGenerator(f, g)

        self.assertEquals(stuff[0][0], ZeroDivisionError)
        self.assertTrue(isinstance(stuff[0][1], ZeroDivisionError))

        self.assertEquals(traceback.extract_tb(stuff[0][2])[-1][-1], "1/0")


    def test_findFailureInGenerator(self):
        """
        Within an exception handler, it should be possible to find the
        original Failure that caused the current exception (if it was
        caused by throwExceptionIntoGenerator).
        """
        f = getDivisionFailure()
        f.cleanFailure()

        foundFailures = []
        def generator():
            try:
                yield
            except:
                foundFailures.append(Failure._findFailure())
            else:
                self.fail("No exception sent to generator")

        g = generator()
        g.next()
        self._throwIntoGenerator(f, g)

        self.assertEqual(foundFailures, [f])


    def test_failureConstructionFindsOriginalFailure(self):
        """
        When a Failure is constructed in the context of an exception
        handler that is handling an exception raised by
        throwExceptionIntoGenerator, the new Failure should be chained to that
        original Failure.
        """
        f = getDivisionFailure()
        f.cleanFailure()

        newFailures = []

        def generator():
            try:
                yield
            except:
                newFailures.append(Failure())
            else:
                self.fail("No exception sent to generator")
        g = generator()
        g.next()
        self._throwIntoGenerator(f, g)

        self.assertEqual(len(newFailures), 1)
        self.assertEqual(newFailures[0].getTraceback(), f.getTraceback())

    def test_ambiguousFailureInGenerator(self):
        """
        When a generator reraises a different exception,
        L{Failure._findFailure} inside the generator should find the reraised
        exception rather than original one.
        """
        def generator():
            try:
                try:
                    yield
                except:
                    [][1]
            except:
                self.assertIsInstance(Failure().value, IndexError)
        g = generator()
        g.next()
        f = getDivisionFailure()
        self._throwIntoGenerator(f, g)

    def test_ambiguousFailureFromGenerator(self):
        """
        When a generator reraises a different exception,
        L{Failure._findFailure} above the generator should find the reraised
        exception rather than original one.
        """
        def generator():
            try:
                yield
            except:
                [][1]
        g = generator()
        g.next()
        f = getDivisionFailure()
        try:
            self._throwIntoGenerator(f, g)
        except:
            self.assertIsInstance(Failure().value, IndexError)
