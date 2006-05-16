# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Maintainer: Jonathan Lange <jml@twistedmatrix.com>


import re, StringIO
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
        """errors in DelayedCalls fail the test
        """
        output = self.runTests(erroneous.DemoTest('testHiddenException'))
        self.assertSubstring(erroneous.HIDDEN_EXCEPTION_MSG, output)


class PyunitTestNames(unittest.TestCase):
    def setUp(self):
        from twisted.trial.test import sample
        self.stream = StringIO.StringIO()
        self.test = sample.PyunitTest('test_foo')
    
    def test_verboseReporter(self):
        result = reporter.VerboseTextReporter(self.stream)
        result.startTest(self.test)
        output = self.stream.getvalue()
        self.failUnlessEqual(
            output, 'twisted.trial.test.sample.PyunitTest.test_foo ... ')

    def test_treeReporter(self):
        result = reporter.TreeReporter(self.stream)
        result.startTest(self.test)
        output = self.stream.getvalue()
        output = output.splitlines()[-1].strip()
        self.failUnlessEqual(output, result.getDescription(self.test) + ' ...')

    def test_getDescription(self):
        result = reporter.TreeReporter(self.stream)
        output = result.getDescription(self.test)
        self.failUnlessEqual(output, 'test_foo')

    def test_minimalReporter(self):
        result = reporter.MinimalReporter(self.stream)
        self.test.run(result)
        result.printSummary()
        output = self.stream.getvalue().strip().split(' ')
        self.failUnlessEqual(output[1:], ['1', '1', '0', '0', '0'])


class TrialTestNames(unittest.TestCase):
    def setUp(self):
        from twisted.trial.test import sample
        self.stream = StringIO.StringIO()
        self.test = sample.FooTest('test_foo')
    
    def test_verboseReporter(self):
        result = reporter.VerboseTextReporter(self.stream)
        result.startTest(self.test)
        output = self.stream.getvalue()
        self.failUnlessEqual(output, self.test.id() + ' ... ')

    def test_treeReporter(self):
        result = reporter.TreeReporter(self.stream)
        result.startTest(self.test)
        output = self.stream.getvalue()
        output = output.splitlines()[-1].strip()
        self.failUnlessEqual(output, result.getDescription(self.test) + ' ...')

    def test_getDescription(self):
        result = reporter.TreeReporter(self.stream)
        output = result.getDescription(self.test)
        self.failUnlessEqual(output, "test_foo")


class SkipTest(unittest.TestCase):
    def setUp(self):
        from twisted.trial.test import sample
        self.stream = StringIO.StringIO()
        self.result = reporter.Reporter(self.stream)
        self.test = sample.FooTest('test_foo')

    def test_accumulation(self):
        self.result.addSkip(self.test, 'some reason')
        self.failUnlessEqual(1, len(self.result.skips))

    def test_success(self):
        self.result.addSkip(self.test, 'some reason')
        self.failUnlessEqual(True, self.result.wasSuccessful())

    def test_summary(self):
        self.result.addSkip(self.test, 'some reason')
        self.result.printSummary()
        output = self.stream.getvalue()
        prefix = 'PASSED '
        self.failUnless(output.startswith(prefix))
        self.failUnlessEqual(output[len(prefix):].strip(), '(skips=1)')

    def test_basicErrors(self):
        self.result.addSkip(self.test, 'some reason')
        self.result.printErrors()
        output = self.stream.getvalue().splitlines()[-1]
        self.failUnlessEqual(output.strip(), 'some reason')

    def test_booleanSkip(self):
        self.result.addSkip(self.test, True)
        self.result.printErrors()
        output = self.stream.getvalue().splitlines()[-1]
        self.failUnlessEqual(output.strip(), 'True')

    def test_exceptionSkip(self):
        try:
            1/0
        except Exception, e:
            error = e
        self.result.addSkip(self.test, error)
        self.result.printErrors()
        output = '\n'.join(self.stream.getvalue().splitlines()[3:]).strip()
        self.failUnlessEqual(output, str(e))


class TestReporter(unittest.TestCase):
    resultFactory = reporter.Reporter
    
    def setUp(self):
        from twisted.trial.test import sample
        self.test = sample.FooTest('test_foo')
        self.stream = StringIO.StringIO()
        self.result = self.resultFactory(self.stream)
        self._timer = 0
        self.result._getTime = self._getTime

    def _getTime(self):
        self._timer += 1
        return self._timer
    
    def test_startStop(self):
        self.result.startTest(self.test)
        self.result.stopTest(self.test)
        self.assertTrue(self.result._lastTime > 0)
        self.assertEqual(self.result.testsRun, 1)
        self.assertEqual(self.result.wasSuccessful(), True)


class TestTimingReporter(TestReporter):
    resultFactory = reporter.TimingTextReporter
