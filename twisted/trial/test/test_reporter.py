# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Maintainer: Jonathan Lange <jml@twistedmatrix.com>


import errno, sys, os, re, StringIO
from twisted.internet.utils import suppressWarnings
from twisted.python import failure
from twisted.trial import unittest, runner, reporter, util
from twisted.trial.test import erroneous


class BrokenStream(object):
    """
    Stream-ish object that raises a signal interrupt error. We use this to make
    sure that Trial still manages to write what it needs to write.
    """
    written = False
    flushed = False

    def __init__(self, fObj):
        self.fObj = fObj

    def write(self, s):
        if self.written:
            return self.fObj.write(s)
        self.written = True
        raise IOError(errno.EINTR, "Interrupted write")

    def flush(self):
        if self.flushed:
            return self.fObj.flush()
        self.flushed = True
        raise IOError(errno.EINTR, "Interrupted flush")


class StringTest(unittest.TestCase):
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


class TestTestResult(unittest.TestCase):
    def setUp(self):
        self.result = reporter.TestResult()

    def test_pyunitAddError(self):
        # pyunit passes an exc_info tuple directly to addError
        try:
            raise RuntimeError('foo')
        except RuntimeError, excValue:
            self.result.addError(self, sys.exc_info())
        failure = self.result.errors[0][1]
        self.assertEqual(excValue, failure.value)
        self.assertEqual(RuntimeError, failure.type)

    def test_pyunitAddFailure(self):
        # pyunit passes an exc_info tuple directly to addFailure
        try:
            raise self.failureException('foo')
        except self.failureException, excValue:
            self.result.addFailure(self, sys.exc_info())
        failure = self.result.failures[0][1]
        self.assertEqual(excValue, failure.value)
        self.assertEqual(self.failureException, failure.type)


class TestReporterRealtime(TestTestResult):
    def setUp(self):
        output = StringIO.StringIO()
        self.result = reporter.Reporter(output, realtime=True)


class TestErrorReporting(StringTest):
    doubleSeparator = re.compile(r'^=+$')

    def setUp(self):
        self.loader = runner.TestLoader()
        self.output = StringIO.StringIO()
        self.result = reporter.Reporter(self.output)

    def getOutput(self, suite):
        result = self.getResult(suite)
        result.printErrors()
        return self.output.getvalue()

    def getResult(self, suite):
        suite.run(self.result)
        return self.result

    def testFormatErroredMethod(self):
        suite = self.loader.loadClass(erroneous.TestFailureInSetUp)
        output = self.getOutput(suite).splitlines()
        match = [self.doubleSeparator,
                 ('[ERROR]: twisted.trial.test.erroneous.'
                  'TestFailureInSetUp.test_noop'),
                 'Traceback (most recent call last):',
                 re.compile(r'^\s+File .*erroneous\.py., line \d+, in setUp$'),
                 re.compile(r'^\s+raise FoolishError, '
                            r'.I am a broken setUp method.$'),
                 ('twisted.trial.test.erroneous.FoolishError: '
                  'I am a broken setUp method')]
        self.stringComparison(match, output)

    def testFormatFailedMethod(self):
        suite = self.loader.loadMethod(erroneous.TestRegularFail.test_fail)
        output = self.getOutput(suite).splitlines()
        match = [
            self.doubleSeparator,
            '[FAIL]: '
            'twisted.trial.test.erroneous.TestRegularFail.test_fail',
            'Traceback (most recent call last):',
            re.compile(r'^\s+File .*erroneous\.py., line \d+, in test_fail$'),
            re.compile(r'^\s+self\.fail\("I fail"\)$'),
            'twisted.trial.unittest.FailTest: I fail'
            ]
        self.stringComparison(match, output)

    def testDoctestError(self):
        from twisted.trial.test import erroneous
        suite = self.loader.loadDoctests(erroneous)
        output = self.getOutput(suite)
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
        """
        Check that errors in C{DelayedCall}s get reported, even if the
        test already has a failure.

        Only really necessary for testing the deprecated style of tests that
        use iterate() directly. See
        L{erroneous.DelayedCall.testHiddenException} for more details.
        """
        test = erroneous.DelayedCall('testHiddenException')
        result = self.getResult(test)
        self.flushLoggedErrors(RuntimeError)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(result.errors[0][1].getErrorMessage(),
                         test.hiddenExceptionMsg)


class TracebackHandling(unittest.TestCase):
    def getErrorFrames(self, test):
        stream = StringIO.StringIO()
        result = reporter.Reporter(stream)
        test.run(result)
        bads = result.failures + result.errors
        assert len(bads) == 1
        assert bads[0][0] == test
        return result._trimFrames(bads[0][1].frames)

    def checkFrames(self, observedFrames, expectedFrames):
        for observed, expected in zip(observedFrames, expectedFrames):
            self.assertEqual(observed[0], expected[0])
            observedSegs = os.path.splitext(observed[1])[0].split(os.sep)
            expectedSegs = expected[1].split('/')
            self.assertEqual(observedSegs[-len(expectedSegs):],
                             expectedSegs)
        self.assertEqual(len(observedFrames), len(expectedFrames))

    def test_basic(self):
        test = erroneous.TestRegularFail('test_fail')
        frames = self.getErrorFrames(test)
        self.checkFrames(frames,
                         [('test_fail', 'twisted/trial/test/erroneous')])

    def test_subroutine(self):
        test = erroneous.TestRegularFail('test_subfail')
        frames = self.getErrorFrames(test)
        self.checkFrames(frames,
                         [('test_subfail', 'twisted/trial/test/erroneous'),
                          ('subroutine', 'twisted/trial/test/erroneous')])

    def test_deferred(self):
        test = erroneous.TestFailureInDeferredChain('test_fail')
        frames = self.getErrorFrames(test)
        self.checkFrames(frames,
                         [('_later', 'twisted/trial/test/erroneous')])

    def test_noFrames(self):
        result = reporter.Reporter(None)
        self.assertEqual([], result._trimFrames([]))

    def test_oneFrame(self):
        result = reporter.Reporter(None)
        self.assertEqual(['fake frame'], result._trimFrames(['fake frame']))


class FormatFailures(StringTest):
    def setUp(self):
        try:
            raise RuntimeError('foo')
        except RuntimeError:
            self.f = failure.Failure()
        self.f.frames = [
            ['foo', 'foo/bar.py', 5, [('x', 5)], [('y', 'orange')]],
            ['qux', 'foo/bar.py', 10, [('a', 'two')], [('b', 'MCMXCIX')]]
            ]
        self.stream = StringIO.StringIO()
        self.result = reporter.Reporter(self.stream)

    def test_formatDefault(self):
        tb = self.result._formatFailureTraceback(self.f)
        self.stringComparison([
            'Traceback (most recent call last):',
            '  File "foo/bar.py", line 5, in foo',
            re.compile(r'^\s*$'),
            '  File "foo/bar.py", line 10, in qux',
            re.compile(r'^\s*$'),
            'RuntimeError: foo'], tb.splitlines())

    def test_formatString(self):
        tb = '''
  File "twisted/trial/unittest.py", line 256, in failUnlessSubstring
    return self.failUnlessIn(substring, astring, msg)
exceptions.TypeError: iterable argument required

'''
        expected = '''
  File "twisted/trial/unittest.py", line 256, in failUnlessSubstring
    return self.failUnlessIn(substring, astring, msg)
exceptions.TypeError: iterable argument required
'''
        formatted = self.result._formatFailureTraceback(tb)
        self.assertEqual(expected, formatted)

    def test_mutation(self):
        frames = self.f.frames[:]
        tb = self.result._formatFailureTraceback(self.f)
        self.assertEqual(self.f.frames, frames)


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

    def test_treeReporterWithDocstrings(self):
        """A docstring"""
        result = reporter.TreeReporter(self.stream)
        self.assertEqual(result.getDescription(self),
                         'test_treeReporterWithDocstrings')

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



class MockColorizer:
    """
    Used by TestTreeReporter to make sure that output is colored correctly.
    """
    def __init__(self, stream):
        self.log = []

    def supported(self):
        return True
    supported = classmethod(supported)

    def write(self, text, color):
        self.log.append((color, text))


class TestTreeReporter(unittest.TestCase):
    def setUp(self):
        from twisted.trial.test import sample
        self.test = sample.FooTest('test_foo')
        self.stream = StringIO.StringIO()
        self.result = reporter.TreeReporter(self.stream)
        self.result._colorizer = MockColorizer(self.stream)
        self.log = self.result._colorizer.log

    def makeError(self):
        try:
            1/0
        except ZeroDivisionError:
            f = failure.Failure()
        return f

    def test_cleanupError(self):
        """
        Run cleanupErrors and check that the output is correct, and colored
        correctly.
        """
        f = self.makeError()
        self.result.cleanupErrors(f)
        color, text = self.log[0]
        self.assertEqual(color.strip(), self.result.ERROR)
        self.assertEqual(text.strip(), 'cleanup errors')
        color, text = self.log[1]
        self.assertEqual(color.strip(), self.result.ERROR)
        self.assertEqual(text.strip(), '[ERROR]')
    test_cleanupError = suppressWarnings(
        test_cleanupError,
        util.suppress(category=reporter.BrokenTestCaseWarning))


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


    def test_brokenStream(self):
        """
        Test that the reporter safely writes to its stream.
        """
        result = self.resultFactory(stream=BrokenStream(self.stream))
        result.writeln("Hello")
        self.assertEqual(self.stream.getvalue(), 'Hello\n')
        self.stream.truncate(0)
        result.writeln("Hello %s!", 'World')
        self.assertEqual(self.stream.getvalue(), 'Hello World!\n')


class TestSafeStream(unittest.TestCase):
    def test_safe(self):
        """
        Test that L{reporter.SafeStream} successfully write to its original
        stream even if an interrupt happens during the write.
        """
        stream = StringIO.StringIO()
        broken = BrokenStream(stream)
        safe = reporter.SafeStream(broken)
        safe.write("Hello")
        self.assertEqual(stream.getvalue(), "Hello")


class TestTimingReporter(TestReporter):
    resultFactory = reporter.TimingTextReporter
