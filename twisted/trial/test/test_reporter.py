# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Maintainer: Jonathan Lange <jml@twistedmatrix.com>


import errno, sys, os, re, StringIO
from twisted.internet.utils import suppressWarnings
from twisted.python.failure import Failure
from twisted.trial import itrial, unittest, runner, reporter, util
from twisted.trial.reporter import UncleanWarningsReporterWrapper
from twisted.trial.test import erroneous
from twisted.trial.unittest import makeTodo, SkipTest, Todo


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
        for line_number, (exp, out) in enumerate(zip(expect, output)):
            if exp is None:
                continue
            elif isinstance(exp, str):
                self.assertSubstring(exp, out, "Line %d: %r not in %r"
                                     % (line_number, exp, out))
            elif isinstance(exp, REGEX_PATTERN_TYPE):
                self.failUnless(exp.match(out),
                                "Line %d: %r did not match string %r"
                                % (line_number, exp.pattern, out))
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
        result.done()
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
        suite = unittest.decorate(
            self.loader.loadDoctests(erroneous), itrial.ITestCase)
        output = self.getOutput(suite)
        path = 'twisted.trial.test.erroneous.unexpectedException'
        for substring in ['1/0', 'ZeroDivisionError',
                          'Exception raised:', path]:
            self.assertSubstring(substring, output)
        self.failUnless(re.search('Fail(ed|ure in) example:', output),
                        "Couldn't match 'Failure in example: ' "
                        "or 'Failed example: '")
        expect = [self.doubleSeparator,
                  re.compile(r'\[(ERROR|FAIL)\]: .*' + re.escape(path))]
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
        output = self.getOutput(test).splitlines()
        match = [
            self.doubleSeparator,
            '[FAIL]: '
            'twisted.trial.test.erroneous.DelayedCall.testHiddenException',
            'Traceback (most recent call last):',
            re.compile(r'^\s+File .*erroneous\.py., line \d+, in '
                       'testHiddenException$'),
            re.compile(r'^\s+self\.fail\("Deliberate failure to mask the '
                       'hidden exception"\)$'),
            'twisted.trial.unittest.FailTest: '
            'Deliberate failure to mask the hidden exception',
            self.doubleSeparator,
            '[ERROR]: '
            'twisted.trial.test.erroneous.DelayedCall.testHiddenException',
            'Traceback (most recent call last):',
            re.compile(r'^\s+File .* in runUntilCurrent'),
            re.compile(r'^\s+.*'),
            re.compile('^\s+File .*erroneous\.py", line \d+, in go'),
            re.compile('^\s+raise RuntimeError\(self.hiddenExceptionMsg\)'),
            'exceptions.RuntimeError: something blew up',
            ]

        self.stringComparison(match, output)



class TestUncleanWarningWrapperErrorReporting(TestErrorReporting):
    """
    Tests that the L{UncleanWarningsReporterWrapper} can sufficiently proxy
    IReporter failure and error reporting methods to a L{reporter.Reporter}.
    """
    def setUp(self):
        self.loader = runner.TestLoader()
        self.output = StringIO.StringIO()
        self.result = UncleanWarningsReporterWrapper(
            reporter.Reporter(self.output))



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
            self.f = Failure()
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
        """
        The summary of L{reporter.MinimalReporter} is a simple list of
        numbers, indicating how many tests ran, how many failed etc.
        """
        result = reporter.MinimalReporter(self.stream)
        self.test.run(result)
        result._printSummary()
        output = self.stream.getvalue().strip().split(' ')
        self.failUnlessEqual(output[1:], ['1', '1', '0', '0', '0'])



class TestDirtyReactor(unittest.TestCase):
    """
    The trial script has an option to treat L{DirtyReactorAggregateError}s as
    warnings, as a migration tool for test authors. It causes a wrapper to be
    placed around reporters that replaces L{DirtyReactorAggregatErrors} with
    warnings.
    """

    def setUp(self):
        self.dirtyError = Failure(
            util.DirtyReactorAggregateError(['foo'], ['bar']))
        self.output = StringIO.StringIO()
        self.test = TestDirtyReactor('test_errorByDefault')


    def test_errorByDefault(self):
        """
        C{DirtyReactorAggregateError}s are reported as errors with the default
        Reporter.
        """
        result = reporter.Reporter(stream=self.output)
        result.addError(self.test, self.dirtyError)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0][1], self.dirtyError)


    def test_warningsEnabled(self):
        """
        C{DirtyReactorErrors}s are reported as warnings when using the
        L{UncleanWarningsReporterWrapper}.
        """
        result = UncleanWarningsReporterWrapper(
            reporter.Reporter(stream=self.output))
        self.assertWarns(UserWarning, self.dirtyError.getErrorMessage(),
                         reporter.__file__,
                         result.addError, self.test, self.dirtyError)


    def test_warningsMaskErrors(self):
        """
        C{DirtyReactorErrors}s are I{not} reported as errors if the
        L{UncleanWarningsReporterWrapper} is used.
        """
        result = UncleanWarningsReporterWrapper(
            reporter.Reporter(stream=self.output))
        self.assertWarns(UserWarning, self.dirtyError.getErrorMessage(),
                         reporter.__file__,
                         result.addError, self.test, self.dirtyError)
        self.assertEquals(result._originalReporter.errors, [])


    def test_dealsWithThreeTuples(self):
        """
        Some annoying stuff can pass three-tuples to addError instead of
        Failures (like PyUnit). The wrapper, of course, handles this case,
        since it is a part of L{twisted.trial.itrial.IReporter}! But it does
        not convert L{DirtyReactorError} to warnings in this case, because
        nobody should be passing those in the form of three-tuples.
        """
        result = UncleanWarningsReporterWrapper(
            reporter.Reporter(stream=self.output))
        result.addError(self.test,
                        (self.dirtyError.type, self.dirtyError.value, None))
        self.assertEqual(len(result._originalReporter.errors), 1)
        self.assertEquals(result._originalReporter.errors[0][1].type,
                          self.dirtyError.type)
        self.assertEquals(result._originalReporter.errors[0][1].value,
                          self.dirtyError.value)



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


class TestSkip(unittest.TestCase):
    """
    Tests for L{reporter.Reporter}'s handling of skips.
    """
    def setUp(self):
        from twisted.trial.test import sample
        self.stream = StringIO.StringIO()
        self.result = reporter.Reporter(self.stream)
        self.test = sample.FooTest('test_foo')

    def _getSkips(self, result):
        """
        Get the number of skips that happened to a reporter.
        """
        return len(result.skips)

    def test_accumulation(self):
        self.result.addSkip(self.test, 'some reason')
        self.assertEqual(self._getSkips(self.result), 1)

    def test_success(self):
        self.result.addSkip(self.test, 'some reason')
        self.failUnlessEqual(True, self.result.wasSuccessful())


    def test_summary(self):
        """
        The summary of a successful run with skips indicates that the test
        suite passed and includes the number of skips.
        """
        self.result.addSkip(self.test, 'some reason')
        self.result.done()
        output = self.stream.getvalue().splitlines()[-1]
        prefix = 'PASSED '
        self.failUnless(output.startswith(prefix))
        self.failUnlessEqual(output[len(prefix):].strip(), '(skips=1)')


    def test_basicErrors(self):
        """
        The output at the end of a test run with skips includes the reasons
        for skipping those tests.
        """
        self.result.addSkip(self.test, 'some reason')
        self.result.done()
        output = self.stream.getvalue().splitlines()[4]
        self.failUnlessEqual(output.strip(), 'some reason')


    def test_booleanSkip(self):
        """
        Tests can be skipped without specifying a reason by setting the 'skip'
        attribute to True. When this happens, the test output includes 'True'
        as the reason.
        """
        self.result.addSkip(self.test, True)
        self.result.done()
        output = self.stream.getvalue().splitlines()[4]
        self.failUnlessEqual(output, 'True')


    def test_exceptionSkip(self):
        """
        Skips can be raised as errors. When this happens, the error is
        included in the summary at the end of the test suite.
        """
        try:
            1/0
        except Exception, e:
            error = e
        self.result.addSkip(self.test, error)
        self.result.done()
        output = '\n'.join(self.stream.getvalue().splitlines()[3:5]).strip()
        self.failUnlessEqual(output, str(e))


class UncleanWarningSkipTest(TestSkip):
    """
    Tests for skips on a L{reporter.Reporter} wrapped by an
    L{UncleanWarningsReporterWrapper}.
    """
    def setUp(self):
        TestSkip.setUp(self)
        self.result = UncleanWarningsReporterWrapper(self.result)

    def _getSkips(self, result):
        """
        Get the number of skips that happened to a reporter inside of an
        unclean warnings reporter wrapper.
        """
        return len(result._originalReporter.skips)



class TodoTest(unittest.TestCase):
    """
    Tests for L{reporter.Reporter}'s handling of todos.
    """

    def setUp(self):
        from twisted.trial.test import sample
        self.stream = StringIO.StringIO()
        self.result = reporter.Reporter(self.stream)
        self.test = sample.FooTest('test_foo')


    def _getTodos(self, result):
        """
        Get the number of todos that happened to a reporter.
        """
        return len(result.expectedFailures)


    def _getUnexpectedSuccesses(self, result):
        """
        Get the number of unexpected successes that happened to a reporter.
        """
        return len(result.unexpectedSuccesses)


    def test_accumulation(self):
        """
        L{reporter.Reporter} accumulates the expected failures that it
        is notified of.
        """
        self.result.addExpectedFailure(self.test, Failure(Exception()),
                                       makeTodo('todo!'))
        self.assertEqual(self._getTodos(self.result), 1)


    def test_success(self):
        """
        A test run is still successful even if there are expected failures.
        """
        self.result.addExpectedFailure(self.test, Failure(Exception()),
                                       makeTodo('todo!'))
        self.assertEqual(True, self.result.wasSuccessful())


    def test_unexpectedSuccess(self):
        """
        A test which is marked as todo but succeeds will have an unexpected
        success reported to its result. A test run is still successful even
        when this happens.
        """
        self.result.addUnexpectedSuccess(self.test, makeTodo("Heya!"))
        self.assertEqual(True, self.result.wasSuccessful())
        self.assertEqual(self._getUnexpectedSuccesses(self.result), 1)


    def test_summary(self):
        """
        The reporter's C{printSummary} method should print the number of
        expected failures that occured.
        """
        self.result.addExpectedFailure(self.test, Failure(Exception()),
                                       makeTodo('some reason'))
        self.result.done()
        output = self.stream.getvalue().splitlines()[-1]
        prefix = 'PASSED '
        self.failUnless(output.startswith(prefix))
        self.assertEqual(output[len(prefix):].strip(),
                         '(expectedFailures=1)')


    def test_basicErrors(self):
        """
        The reporter's L{printErrors} method should include the value of the
        Todo.
        """
        self.result.addExpectedFailure(self.test, Failure(Exception()),
                                       makeTodo('some reason'))
        self.result.done()
        output = self.stream.getvalue().splitlines()[4].strip()
        self.assertEqual(output, "Reason: 'some reason'")


    def test_booleanTodo(self):
        """
        Booleans CAN'T be used as the value of a todo. Maybe this sucks. This
        is a test for current behavior, not a requirement.
        """
        self.result.addExpectedFailure(self.test, Failure(Exception()),
                                       makeTodo(True))
        self.assertRaises(Exception, self.result.done)


    def test_exceptionTodo(self):
        """
        The exception for expected failures should be shown in the
        C{printErrors} output.
        """
        try:
            1/0
        except Exception, e:
            error = e
        self.result.addExpectedFailure(self.test, Failure(error),
                                       makeTodo("todo!"))
        self.result.done()
        output = '\n'.join(self.stream.getvalue().splitlines()[3:]).strip()
        self.assertTrue(str(e) in output)



class UncleanWarningTodoTest(TodoTest):
    """
    Tests for L{UncleanWarningsReporterWrapper}'s handling of todos.
    """

    def setUp(self):
        TodoTest.setUp(self)
        self.result = UncleanWarningsReporterWrapper(self.result)


    def _getTodos(self, result):
        """
        Get the number of todos that happened to a reporter inside of an
        unclean warnings reporter wrapper.
        """
        return len(result._originalReporter.expectedFailures)


    def _getUnexpectedSuccesses(self, result):
        """
        Get the number of unexpected successes that happened to a reporter
        inside of an unclean warnings reporter wrapper.
        """
        return len(result._originalReporter.unexpectedSuccesses)



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
            f = Failure()
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
        util.suppress(category=reporter.BrokenTestCaseWarning),
        util.suppress(category=DeprecationWarning))


    def test_upDownError(self):
        """
        Run upDownError and check that the output is correct and colored
        correctly.
        """
        self.result.upDownError("method", None, None, False)
        color, text = self.log[0]
        self.assertEqual(color.strip(), self.result.ERROR)
        self.assertEqual(text.strip(), 'method')
    test_upDownError = suppressWarnings(
        test_upDownError,
        util.suppress(category=DeprecationWarning,
                      message="upDownError is deprecated in Twisted 8.0."))


    def test_summaryColoredSuccess(self):
        """
        The summary in case of success should have a good count of successes
        and be colored properly.
        """
        self.result.addSuccess(self.test)
        self.result.done()
        self.assertEquals(self.log[1], (self.result.SUCCESS, 'PASSED'))
        self.assertEquals(
            self.stream.getvalue().splitlines()[-1].strip(), "(successes=1)")


    def test_summaryColoredFailure(self):
        """
        The summary in case of failure should have a good count of errors
        and be colored properly.
        """
        try:
            raise RuntimeError('foo')
        except RuntimeError, excValue:
            self.result.addError(self, sys.exc_info())
        self.result.done()
        self.assertEquals(self.log[1], (self.result.FAILURE, 'FAILED'))
        self.assertEquals(
            self.stream.getvalue().splitlines()[-1].strip(), "(errors=1)")


    def test_getPrelude(self):
        """
        The tree needs to get the segments of the test ID that correspond
        to the module and class that it belongs to.
        """
        self.assertEqual(
            ['foo.bar', 'baz'],
            self.result._getPreludeSegments('foo.bar.baz.qux'))
        self.assertEqual(
            ['foo', 'bar'],
            self.result._getPreludeSegments('foo.bar.baz'))
        self.assertEqual(
            ['foo'],
            self.result._getPreludeSegments('foo.bar'))
        self.assertEqual([], self.result._getPreludeSegments('foo'))


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
        result._writeln("Hello")
        self.assertEqual(self.stream.getvalue(), 'Hello\n')
        self.stream.truncate(0)
        result._writeln("Hello %s!", 'World')
        self.assertEqual(self.stream.getvalue(), 'Hello World!\n')



    def test_printErrorsDeprecated(self):
        """
        L{IReporter.printErrors} was deprecated in Twisted 8.0.
        """
        def f():
            self.result.printErrors()
        self.assertWarns(
            DeprecationWarning, "printErrors is deprecated in Twisted 8.0.",
            __file__, f)


    def test_printSummaryDeprecated(self):
        """
        L{IReporter.printSummary} was deprecated in Twisted 8.0.
        """
        def f():
            self.result.printSummary()
        self.assertWarns(
            DeprecationWarning, "printSummary is deprecated in Twisted 8.0.",
            __file__, f)


    def test_writeDeprecated(self):
        """
        L{IReporter.write} was deprecated in Twisted 8.0.
        """
        def f():
            self.result.write("")
        self.assertWarns(
            DeprecationWarning, "write is deprecated in Twisted 8.0.",
            __file__, f)


    def test_writelnDeprecated(self):
        """
        L{IReporter.writeln} was deprecated in Twisted 8.0.
        """
        def f():
            self.result.writeln("")
        self.assertWarns(
            DeprecationWarning, "writeln is deprecated in Twisted 8.0.",
            __file__, f)


    def test_separatorDeprecated(self):
        """
        L{IReporter.separator} was deprecated in Twisted 8.0.
        """
        def f():
            return self.result.separator
        self.assertWarns(
            DeprecationWarning, "separator is deprecated in Twisted 8.0.",
            __file__, f)


    def test_streamDeprecated(self):
        """
        L{IReporter.stream} was deprecated in Twisted 8.0.
        """
        def f():
            return self.result.stream
        self.assertWarns(
            DeprecationWarning, "stream is deprecated in Twisted 8.0.",
            __file__, f)


    def test_upDownErrorDeprecated(self):
        """
        L{IReporter.upDownError} was deprecated in Twisted 8.0.
        """
        def f():
            self.result.upDownError(None, None, None, None)
        self.assertWarns(
            DeprecationWarning, "upDownError is deprecated in Twisted 8.0.",
            __file__, f)



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



class LoggingReporter(reporter.Reporter):
    """
    Simple reporter that stores the last test that was passed to it.
    """

    def __init__(self, *args, **kwargs):
        reporter.Reporter.__init__(self, *args, **kwargs)
        self.test = None

    def addError(self, test, error):
        self.test = test

    def addExpectedFailure(self, test, failure, todo):
        self.test = test

    def addFailure(self, test, failure):
        self.test = test

    def addSkip(self, test, skip):
        self.test = test

    def addUnexpectedSuccess(self, test, todo):
        self.test = test

    def startTest(self, test):
        self.test = test

    def stopTest(self, test):
        self.test = test



class TestAdaptedReporter(unittest.TestCase):
    """
    L{reporter._AdaptedReporter} is a reporter wrapper that wraps all of the
    tests it receives before passing them on to the original reporter.
    """

    def setUp(self):
        self.wrappedResult = self.getWrappedResult()


    def _testAdapter(self, test):
        return test.id()


    def assertWrapped(self, wrappedResult, test):
        self.assertEqual(wrappedResult._originalReporter.test, self._testAdapter(test))


    def getFailure(self, exceptionInstance):
        """
        Return a L{Failure} from raising the given exception.

        @param exceptionInstance: The exception to raise.
        @return: L{Failure}
        """
        try:
            raise exceptionInstance
        except:
            return Failure()


    def getWrappedResult(self):
        result = LoggingReporter()
        return reporter._AdaptedReporter(result, self._testAdapter)


    def test_addError(self):
        """
        C{addError} wraps its test with the provided adapter.
        """
        self.wrappedResult.addError(self, self.getFailure(RuntimeError()))
        self.assertWrapped(self.wrappedResult, self)


    def test_addFailure(self):
        """
        C{addFailure} wraps its test with the provided adapter.
        """
        self.wrappedResult.addFailure(self, self.getFailure(AssertionError()))
        self.assertWrapped(self.wrappedResult, self)


    def test_addSkip(self):
        """
        C{addSkip} wraps its test with the provided adapter.
        """
        self.wrappedResult.addSkip(self, self.getFailure(SkipTest('no reason')))
        self.assertWrapped(self.wrappedResult, self)


    def test_startTest(self):
        """
        C{startTest} wraps its test with the provided adapter.
        """
        self.wrappedResult.startTest(self)
        self.assertWrapped(self.wrappedResult, self)


    def test_stopTest(self):
        """
        C{stopTest} wraps its test with the provided adapter.
        """
        self.wrappedResult.stopTest(self)
        self.assertWrapped(self.wrappedResult, self)


    def test_addExpectedFailure(self):
        """
        C{addExpectedFailure} wraps its test with the provided adapter.
        """
        self.wrappedResult.addExpectedFailure(
            self, self.getFailure(RuntimeError()), Todo("no reason"))
        self.assertWrapped(self.wrappedResult, self)


    def test_addUnexpectedSuccess(self):
        """
        C{addUnexpectedSuccess} wraps its test with the provided adapter.
        """
        self.wrappedResult.addUnexpectedSuccess(self, Todo("no reason"))
        self.assertWrapped(self.wrappedResult, self)
