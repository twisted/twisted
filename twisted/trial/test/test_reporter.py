# -*- test-case-name: twisted.trial.test.test_reporter -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>

from __future__ import nested_scopes

import re
import time
import types
from pprint import pformat, pprint

from twisted.trial import unittest, runner, reporter
from twisted.trial.test import common, erroneous


class TestReporter(common.RegistryBaseMixin):

    def testTracebackReporting(self):
        from twisted.trial.runner import TrialSuite
        # the fact this is needed shows that we need to split out the reporting
        # from the run action.
        loader = runner.TestLoader()
        suite = loader.loadMethod(common.FailfulTests.testTracebackReporting)
        self.run_a_suite(suite)
        self.reporter.printErrors()
        lines = self.reporter.out.split('\n')
        while 1:
            self.failUnless(lines, "double separator not found in lines")
            if lines[0] != reporter.Reporter.doubleSeparator:
                lines.pop(0)
            else:
                return

        expect = [
reporter.Reporter.doubleSeparator,
'[ERROR]: testTracebackReporting (twisted.trial.test.test_reporter.FailfulTests)',
None,
None,
re.compile(r'.*twisted/trial/test/test_reporter\.py.*testTracebackReporting'),
re.compile(r'.*1/0'),
re.compile(r'.*ZeroDivisionError.*'),
SEPARATOR,
re.compile(r'Ran 1 tests in [0-9.]*s'),
r'FAILED (errors=1)'
]
        self.stringComparison(expect, lines)
     
    def test_timing(self):
        the_reporter = reporter.Reporter()
        the_reporter._somethingStarted()
        the_reporter._somethingStarted()
        time.sleep(0.01)
        time1 = the_reporter._somethingStopped()
        time.sleep(0.01)
        time2 = the_reporter._somethingStopped()
        self.failUnless(time1 < time2)
        self.assertEqual(the_reporter._last_time, time2)
        
        
__unittests__ = [TestReporter]

