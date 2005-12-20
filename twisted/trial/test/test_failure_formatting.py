# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Maintainer: Jonathan Lange <jml@twistedmatrix.com>

import re, os, sys, StringIO

from twisted.trial.test import erroneous, common
from twisted.trial import itrial, unittest, reporter, runner
from twisted.python import failure


class TestFailureFormatting(common.RegistryBaseMixin):
    def setUp(self):
        super(TestFailureFormatting, self).setUp()
        self.loader = runner.TestLoader()
    
    def testFormatErroredMethod(self):
        # FIXME
        # this should be in test_reporter, and should be testing output summaries
        # not run() side effects. Until then wrap it in TrialSuite which triggers
        # the output side effects
        suite = self.loader.loadClass(erroneous.TestFailureInSetUp)
        output = StringIO.StringIO()
        result = reporter.Reporter(output)
        suite.run(result)
        result.printErrors()
        output = output.getvalue().splitlines()
        match = [re.compile(r'^=+$'),
                 ('[ERROR]: twisted.trial.test.erroneous.'
                  'TestFailureInSetUp.testMethod'),
                 re.compile(r'^\s+File .*erroneous\.py., line \d+, in setUp$'),
                 re.compile(r'^\s+raise FoolishError, '
                            r'.I am a broken setUp method.$'),
                 ('twisted.trial.test.erroneous.FoolishError: '
                  'I am a broken setUp method')]
        self.stringComparison(match, output)

    def testFormatFailedMethod(self):
        # FIXME - this should be in test_reporter
        suite = self.loader.loadMethod(common.FailfulTests.testFailure)
        output = StringIO.StringIO()
        result = reporter.Reporter(output)
        suite.run(result)
        result.printErrors()
        output = output.getvalue().splitlines()
        match = [re.compile(r'^=+$'),
                 r'[FAIL]: twisted.trial.test.common.FailfulTests.testFailure',
                 re.compile(r'^\s+File .*common\.py., line \d+, in testFailure$'),
                 re.compile(r'^\s+raise unittest.FailTest, FAILURE_MSG$'),
                 'twisted.trial.unittest.FailTest: this test failed']
        self.stringComparison(match, output)

    def testDoctestError(self):
        if sys.version_info[0:2] < (2, 3):
            raise unittest.SkipTest(
                'doctest support only works in Python 2.3 or later')
        from twisted.trial.test import trialdoctest2
        # this should be in test_reporter, and should be testing output summaries
        # not run() side effects. Until then wrap it in TrialSuite which triggers
        # the output side effects
        self.run_a_suite(runner.TrialSuite([
            self.loader.loadDoctests(trialdoctest2)]))
        output = self.reporter.out.splitlines()
        path = 'twisted.trial.test.trialdoctest2.unexpectedException'
        expect = ['Running 1 tests.',
                  reporter.Reporter.doubleSeparator,
                  re.compile(r'\[(ERROR|FAIL)\]: .*[Dd]octest.*'
                             + re.escape(path))]
        self.stringComparison(expect, output)
        output = '\n'.join(output)
        for substring in ['1/0', 'ZeroDivisionError',
                          'Exception raised:',
                          'twisted.trial.test.trialdoctest2.unexpectedException']:
            self.assertSubstring(substring, output)
        self.failUnless(
            re.search('Fail(ed|ure in) example:', output),
            "Couldn't match 'Failure in example: ' or 'Failed example: '")
