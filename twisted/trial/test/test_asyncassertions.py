# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for async assertions provided by C{twisted.trial.unittest.TestCase}.
"""

from __future__ import division, absolute_import

import unittest as pyunit

from twisted.python import failure
from twisted.internet import defer
from twisted.trial import unittest


class TestAsynchronousAssertions(unittest.TestCase):
    """
    Tests for L{TestCase}'s asynchronous extensions to L{SynchronousTestCase}.
    That is, L{TestCase.assertFailure}.
    """
    def test_assertFailure(self):
        """
        C{assertFailure} returns the passed L{Deferred} with callbacks added
        if the L{Deferred} fails with expected exception.
        """
        d = defer.maybeDeferred(lambda: 1/0)
        return self.assertFailure(d, ZeroDivisionError)


    def test_assertFailureWrongException(self):
        """
        C{assertFailure} returns a L{Failure} if the passed L{Deferred} fails
        with unexpected exception.
        """
        d = defer.maybeDeferred(lambda: 1/0)
        self.assertFailure(d, OverflowError)
        d.addCallbacks(lambda x: self.fail('Should have failed'),
                       lambda x: x.trap(self.failureException))
        return d


    def test_assertFailureNoException(self):
        """
        C{assertFailure} returns a L{Failure} if the passed L{Deferred}
        doesn't fail with expected exception.
        """
        d = defer.succeed(None)
        self.assertFailure(d, ZeroDivisionError)
        d.addCallbacks(lambda x: self.fail('Should have failed'),
                       lambda x: x.trap(self.failureException))
        return d


    def test_assertFailureMoreInfo(self):
        """
        C{assertFailure} returns a L{Failure} with error message and brief
        tracebrack information if the C{assertFailure} fails.
        """
        try:
            1/0
        except ZeroDivisionError:
            f = failure.Failure()
            d = defer.fail(f)
        d = self.assertFailure(d, RuntimeError)
        d.addErrback(self._checkInfo, f)
        return d


    def _checkInfo(self, assertionFailure, f):
        """
        Check L{assertFailure} returns L{Failure} with error message and 
        brief trackback information.

        @param assertionFailure: A L{Failure} instance returned by
            L{assertFailure}.

        @param f: A L{Failure} instance initialized with the explanation of
            the exception that causes L{assertFailure} to fail.
        """
        assert assertionFailure.check(self.failureException)
        output = assertionFailure.getErrorMessage()
        self.assertIn(f.getErrorMessage(), output)
        self.assertIn(f.getBriefTraceback(), output)


    def test_assertFailureMasked(self):
        """
        L{unittest.TestCase} fails if a single C{assertFailure} returns a
        L{Failure}.
        """
        class ExampleFailure(Exception):
            pass

        class TC(unittest.TestCase):
            failureException = ExampleFailure
            def test_assertFailure(self):
                d = defer.maybeDeferred(lambda: 1/0)
                self.assertFailure(d, OverflowError)
                self.assertFailure(d, ZeroDivisionError)
                return d

        test = TC('test_assertFailure')
        result = pyunit.TestResult()
        test.run(result)
        self.assertEqual(1, len(result.failures))
