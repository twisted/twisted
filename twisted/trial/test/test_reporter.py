# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Maintainer: Jonathan Lange <jml@twistedmatrix.com>


import time, re, StringIO
from twisted.trial import unittest, runner, reporter
from twisted.trial.test import erroneous

class TestErrorReporting(unittest.TestCase):
    doubleSeparator = re.compile(r'^=+$')
    
    def stringComparison(self, expect, output):
        output = filter(None, output)
        self.failUnless(len(expect) <= len(output),
                        "Must have more observed than expected"
                        "lines %d < %d" % (len(output), len(expect)))
        REGEX_PATTERN_TYPE = type(re.compile(''))
        for exp, out in zip(expect, output):
            if exp is None:
                continue
            elif isinstance(exp, str):
                self.assertSubstring(exp, out)
            elif isinstance(exp, REGEX_PATTERN_TYPE):
                self.failUnless(exp.match(out), "%r did not match string %r"
                                % (exp.pattern, out))
            else:
                raise TypeError("don't know what to do with object %r"
                                % (exp,))

    def setUp(self):
        self.loader = runner.TestLoader()

    def runTests(self, suite):
        output = StringIO.StringIO()
        result = reporter.Reporter(output)
        suite.run(result)
        result.printErrors()
        return output.getvalue()
    
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
        
    def testFormatErroredMethod(self):
        suite = self.loader.loadClass(erroneous.TestFailureInSetUp)
        output = self.runTests(suite).splitlines()
        match = [self.doubleSeparator,
                 ('[ERROR]: twisted.trial.test.erroneous.'
                  'TestFailureInSetUp.test_noop'),
                 re.compile(r'^\s+File .*erroneous\.py., line \d+, in setUp$'),
                 re.compile(r'^\s+raise FoolishError, '
                            r'.I am a broken setUp method.$'),
                 ('twisted.trial.test.erroneous.FoolishError: '
                  'I am a broken setUp method')]
        self.stringComparison(match, output)

    def testFormatFailedMethod(self):
        suite = self.loader.loadMethod(erroneous.TestRegularFail.test_fail)
        output = self.runTests(suite).splitlines()
        match = [
            self.doubleSeparator,
            '[FAIL]: '
            'twisted.trial.test.erroneous.TestRegularFail.test_fail',
            re.compile(r'^\s+File .*erroneous\.py., line \d+, in test_fail$'),
            re.compile(r'^\s+self\.fail\("I fail"\)$'),
            'twisted.trial.unittest.FailTest: I fail'
            ]
        self.stringComparison(match, output)

    def testDoctestError(self):
        import sys
        from twisted.trial.test import erroneous
        suite = self.loader.loadDoctests(erroneous)
        output = self.runTests(suite)
        path = 'twisted.trial.test.erroneous.unexpectedException'
        for substring in ['1/0', 'ZeroDivisionError',
                          'Exception raised:', path]:
            self.assertSubstring(substring, output)
        self.failUnless(re.search('Fail(ed|ure in) example:', output),
                        "Couldn't match 'Failure in example: ' "
                        "or 'Failed example: '")
        expect = [self.doubleSeparator,
                  re.compile(r'\[(ERROR|FAIL)\]: .*[Dd]octest.*'
                             + re.escape(path))]
        self.stringComparison(expect, output.splitlines())

    def testHiddenException(self):
        output = self.runTests(erroneous.DemoTest('testHiddenException'))
        self.assertSubstring(erroneous.HIDDEN_EXCEPTION_MSG, output)


