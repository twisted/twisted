# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test Twisted's doctest support.
"""

from twisted.trial import itrial, runner, unittest, reporter
from twisted.trial.test import mockdoctest


class TestRunners(unittest.TestCase):
    """
    Tests for Twisted's doctest support.
    """

    def test_basicTrialIntegration(self):
        """
        L{loadDoctests} loads all of the doctests in the given module.
        """
        loader = runner.TestLoader()
        suite = loader.loadDoctests(mockdoctest)
        self.assertEqual(7, suite.countTestCases())


    def _testRun(self, suite):
        """
        Run C{suite} and check the result.
        """
        result = reporter.TestResult()
        suite.run(result)
        self.assertEqual(5, result.successes)
        self.assertEqual(2, len(result.failures))


    def test_expectedResults(self, count=1):
        """
        Trial can correctly run doctests with its xUnit test APIs.
        """
        suite = runner.TestLoader().loadDoctests(mockdoctest)
        self._testRun(suite)


    def test_repeatable(self):
        """
        Doctests should be runnable repeatably.
        """
        suite = runner.TestLoader().loadDoctests(mockdoctest)
        self._testRun(suite)
        self._testRun(suite)
