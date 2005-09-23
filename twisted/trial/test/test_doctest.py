#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>

"""
test twisted's doctest support
"""
import exceptions, sys, doctest

from twisted import trial
from twisted.trial import runner, unittest, reporter
from twisted.trial import itrial
from twisted.trial.reporter import  FAILURE, ERROR, SUCCESS
from twisted.python import failure

from twisted.trial.test import trialdoctest1, trialdoctest2, common

from pprint import pprint

import zope.interface as zi


if sys.version_info[0:2] < (2,3):
    skip = 'doctest support only works on 2.3 or later'

class TestRunners(unittest.TestCase):
    def test_correctCount(self):
        suite = runner.DocTestSuite(trialdoctest1)
        self.assertEqual(7, suite.countTestCases())

    def test_basicTrialIntegration(self):
        loader = runner.TestLoader()
        suite = loader.loadDoctests(trialdoctest1)
        self.assertEqual(7, suite.countTestCases())

    def test_expectedResults(self):
        suite = runner.DocTestSuite(trialdoctest1)
        reporter = common.BogusReporter()
        root = runner.TrialRoot(reporter)
        root.run(suite)
        self.assertEqual(5, len(reporter.results[SUCCESS]))
        # doctest reports failures as errors in 2.3
        self.assertEqual(2, len(reporter.results[ERROR])
                         + len(reporter.results[FAILURE]))

