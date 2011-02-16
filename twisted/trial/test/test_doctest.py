# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test twisted's doctest support.
"""

from twisted.trial import itrial, runner, unittest, reporter
from twisted.trial.test import mockdoctest


class TestRunners(unittest.TestCase):
    """
    Tests for Twisted's doctest support.
    """

    def test_id(self):
        """
        Check that the id() of the doctests' case object contains the FQPN of
        the actual tests. We need this because id() has weird behaviour w/
        doctest in Python 2.3.
        """
        loader = runner.TestLoader()
        suite = loader.loadDoctests(mockdoctest)
        idPrefix = 'twisted.trial.test.mockdoctest.Counter'
        for test in suite._tests:
            self.assertIn(idPrefix, itrial.ITestCase(test).id())


    def makeDocSuite(self, module):
        """
        Return a L{runner.DocTestSuite} for the doctests in C{module}.
        """
        return self.assertWarns(
            DeprecationWarning, "DocTestSuite is deprecated in Twisted 8.0.",
            __file__, lambda: runner.DocTestSuite(mockdoctest))


    def test_correctCount(self):
        """
        L{countTestCases} returns the number of doctests in the module.
        """
        suite = self.makeDocSuite(mockdoctest)
        self.assertEqual(7, suite.countTestCases())


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
        # doctest reports failures as errors in 2.3
        self.assertEqual(2, len(result.errors) + len(result.failures))


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
