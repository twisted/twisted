# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test Twisted's doctest support.
"""
import sys
import unittest as pyunit

from twisted.trial import itrial, reporter, runner, unittest
from twisted.trial.test import mockdoctest


class RunnersTests(unittest.SynchronousTestCase):
    """
    Tests for Twisted's doctest support.
    """

    def test_id(self) -> None:
        """
        Check that the id() of the doctests' case object contains the FQPN of
        the actual tests.
        """
        loader = runner.TestLoader()
        suite = loader.loadDoctests(mockdoctest)
        idPrefix = "twisted.trial.test.mockdoctest.Counter"
        for test in suite._tests:
            self.assertIn(idPrefix, itrial.ITestCase(test).id())

    def test_basicTrialIntegration(self) -> None:
        """
        L{loadDoctests} loads all of the doctests in the given module.
        """
        loader = runner.TestLoader()
        suite = loader.loadDoctests(mockdoctest)
        self.assertEqual(7, suite.countTestCases())

    def _testRun(self, suite: pyunit.TestSuite) -> None:
        """
        Run C{suite} and check the result.
        """
        result = reporter.TestResult()
        suite.run(result)
        # Python 3.15+ counts doctest examples differently, resulting in more successes
        # and also consolidates some failures
        expected_successes = 7 if sys.version_info >= (3, 15) else 5
        expected_failures = 1 if sys.version_info >= (3, 15) else 2
        self.assertEqual(expected_successes, result.successes)
        self.assertEqual(expected_failures, len(result.failures))

    def test_expectedResults(self, count: int = 1) -> None:
        """
        Trial can correctly run doctests with its xUnit test APIs.
        """
        suite = runner.TestLoader().loadDoctests(mockdoctest)
        self._testRun(suite)

    def test_repeatable(self) -> None:
        """
        Doctests should be runnable repeatably.
        """
        suite = runner.TestLoader().loadDoctests(mockdoctest)
        self._testRun(suite)
        self._testRun(suite)
