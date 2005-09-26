# -*- test-case-name: twisted.trial.test.test_reporter -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>

from __future__ import nested_scopes

import re, types
from pprint import pformat, pprint

from twisted.trial import unittest, runner
from twisted.trial.test import common, erroneous
from twisted.trial.reporter import DOUBLE_SEPARATOR, SEPARATOR


class TestReporter(common.RegistryBaseMixin, unittest.TestCase):
    def testTracebackReporting(self):
        loader = runner.TestLoader()
        suite = loader.loadMethod(common.FailfulTests.testTracebackReporting)
        self.suite.run(suite)
        lines = self.reporter.out.split('\n')
        while 1:
            if not lines:
                raise FailTest, "DOUBLE_SEPARATOR not found in lines"
            if lines[0] != DOUBLE_SEPARATOR:
                lines.pop(0)
            else:
                return

        expect = [
DOUBLE_SEPARATOR,
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
       

__unittests__ = [TestReporter]

