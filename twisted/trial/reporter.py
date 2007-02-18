# -*- test-case-name: twisted.trial.test.test_reporter -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Maintainer: Jonathan Lange <jml@twistedmatrix.com>

"""Defines classes that handle the results of tests.

API Stability: Unstable
"""

import sys, os
import time
import warnings

from twisted.python import reflect, failure, log
from twisted.python.util import untilConcludes
from twisted.trial import itrial
import zope.interface as zi

pyunit = __import__('unittest')


class BrokenTestCaseWarning(Warning):
    """emitted as a warning when an exception occurs in one of
    setUp, tearDown, setUpClass, or tearDownClass"""


class SafeStream(object):
    """
    Wraps a stream object so that all C{write} calls are wrapped in
    L{untilConcludes}.
    """

    def __init__(self, original):
        self.original = original

    def __getattr__(self, name):
        return getattr(self.original, name)

    def write(self, *a, **kw):
        return untilConcludes(self.original.write, *a, **kw)


class TestResult(pyunit.TestResult, object):
    """Accumulates the results of several L{twisted.trial.unittest.TestCase}s.
    """

    def __init__(self):
        super(TestResult, self).__init__()
        self.skips = []
        self.expectedFailures = []
        self.unexpectedSuccesses = []
        self.successes = []
        self._timings = []

    def __repr__(self):
        return ('<%s run=%d errors=%d failures=%d todos=%d dones=%d skips=%d>'
                % (reflect.qual(self.__class__), self.testsRun,
                   len(self.errors), len(self.failures),
                   len(self.expectedFailures), len(self.skips),
                   len(self.unexpectedSuccesses)))

    def _getTime(self):
        return time.time()

    def startTest(self, test):
        """This must be called before the given test is commenced.

        @type test: L{pyunit.TestCase}
        """
        super(TestResult, self).startTest(test)
        self._testStarted = self._getTime()

    def stopTest(self, test):
        """This must be called after the given test is completed.

        @type test: L{pyunit.TestCase}
        """
        super(TestResult, self).stopTest(test)
        self._lastTime = self._getTime() - self._testStarted

    def addFailure(self, test, fail):
        """Report a failed assertion for the given test.

        @type test: L{pyunit.TestCase}
        @type fail: L{failure.Failure} or L{tuple}
        """
        if isinstance(fail, tuple):
            fail = failure.Failure(fail[1], fail[0], fail[2])
        self.failures.append((test, fail))

    def addError(self, test, error):
        """Report an error that occurred while running the given test.

        @type test: L{pyunit.TestCase}
        @type fail: L{failure.Failure} or L{tuple}
        """
        if isinstance(error, tuple):
            error = failure.Failure(error[1], error[0], error[2])
        self.errors.append((test, error))

    def addSkip(self, test, reason):
        """
        Report that the given test was skipped.

        In Trial, tests can be 'skipped'. Tests are skipped mostly because there
        is some platform or configuration issue that prevents them from being
        run correctly.

        @type test: L{pyunit.TestCase}
        @type reason: L{str}
        """
        self.skips.append((test, reason))

    def addUnexpectedSuccess(self, test, todo):
        """Report that the given test succeeded against expectations.

        In Trial, tests can be marked 'todo'. That is, they are expected to fail.
        When a test that is expected to fail instead succeeds, it should call
        this method to report the unexpected success.

        @type test: L{pyunit.TestCase}
        @type todo: L{unittest.Todo}
        """
        # XXX - 'todo' should just be a string
        self.unexpectedSuccesses.append((test, todo))

    def addExpectedFailure(self, test, error, todo):
        """Report that the given test succeeded against expectations.

        In Trial, tests can be marked 'todo'. That is, they are expected to fail.

        @type test: L{pyunit.TestCase}
        @type error: L{failure.Failure}
        @type todo: L{unittest.Todo}
        """
        # XXX - 'todo' should just be a string
        self.expectedFailures.append((test, error, todo))

    def addSuccess(self, test):
        """Report that the given test succeeded.

        @type test: L{pyunit.TestCase}
        """
        self.successes.append((test,))

    def upDownError(self, method, error, warn, printStatus):
        pass

    def cleanupErrors(self, errs):
        """Report an error that occurred during the cleanup between tests.
        """
        # XXX - deprecate this method, we don't need it any more

    def startSuite(self, name):
        # XXX - these should be removed, but not in this branch
        pass

    def endSuite(self, name):
        # XXX - these should be removed, but not in this branch
        pass


class Reporter(TestResult):
    zi.implements(itrial.IReporter)

    separator = '-' * 79
    doubleSeparator = '=' * 79

    def __init__(self, stream=sys.stdout, tbformat='default', realtime=False):
        super(Reporter, self).__init__()
        self.stream = SafeStream(stream)
        self.tbformat = tbformat
        self.realtime = realtime

    def startTest(self, test):
        super(Reporter, self).startTest(test)

    def addFailure(self, test, fail):
        super(Reporter, self).addFailure(test, fail)
        if self.realtime:
            fail = self.failures[-1][1] # guarantee it's a Failure
            self.write(self._formatFailureTraceback(fail))

    def addError(self, test, error):
        super(Reporter, self).addError(test, error)
        if self.realtime:
            error = self.errors[-1][1] # guarantee it's a Failure
            self.write(self._formatFailureTraceback(error))

    def write(self, format, *args):
        s = str(format)
        assert isinstance(s, type(''))
        if args:
            self.stream.write(s % args)
        else:
            self.stream.write(s)
        untilConcludes(self.stream.flush)

    def writeln(self, format, *args):
        self.write(format, *args)
        self.write('\n')

    def upDownError(self, method, error, warn, printStatus):
        super(Reporter, self).upDownError(method, error, warn, printStatus)
        if warn:
            tbStr = self._formatFailureTraceback(error)
            log.msg(tbStr)
            msg = ("caught exception in %s, your TestCase is broken\n\n%s"
                   % (method, tbStr))
            warnings.warn(msg, BrokenTestCaseWarning, stacklevel=2)

    def cleanupErrors(self, errs):
        super(Reporter, self).cleanupErrors(errs)
        warnings.warn("%s\n%s" % ("REACTOR UNCLEAN! traceback(s) follow: ",
                                  self._formatFailureTraceback(errs)),
                      BrokenTestCaseWarning)

    def _trimFrames(self, frames):
        # when a method fails synchronously, the stack looks like this:
        #  [0]: defer.maybeDeferred()
        #  [1]: utils.runWithWarningsSuppressed()
        #  [2:-2]: code in the test method which failed
        #  [-1]: unittest.fail

        # when a method fails inside a Deferred (i.e., when the test method
        # returns a Deferred, and that Deferred's errback fires), the stack
        # captured inside the resulting Failure looks like this:
        #  [0]: defer.Deferred._runCallbacks
        #  [1:-2]: code in the testmethod which failed
        #  [-1]: unittest.fail

        # as a result, we want to trim either [maybeDeferred,runWWS] or
        # [Deferred._runCallbacks] from the front, and trim the
        # [unittest.fail] from the end.

        newFrames = list(frames)

        if len(frames) < 2:
            return newFrames

        first = newFrames[0]
        second = newFrames[1]
        if (first[0] == "maybeDeferred"
            and os.path.splitext(os.path.basename(first[1]))[0] == 'defer'
            and second[0] == "runWithWarningsSuppressed"
            and os.path.splitext(os.path.basename(second[1]))[0] == 'utils'):
            newFrames = newFrames[2:]
        elif (first[0] == "_runCallbacks"
              and os.path.splitext(os.path.basename(first[1]))[0] == 'defer'):
            newFrames = newFrames[1:]

        last = newFrames[-1]
        if (last[0].startswith('fail')
            and os.path.splitext(os.path.basename(last[1]))[0] == 'unittest'):
            newFrames = newFrames[:-1]

        return newFrames

    def _formatFailureTraceback(self, fail):
        if isinstance(fail, str):
            return fail.rstrip() + '\n'
        fail.frames, frames = self._trimFrames(fail.frames), fail.frames
        result = fail.getTraceback(detail=self.tbformat, elideFrameworkCode=True)
        fail.frames = frames
        return result

    def _printResults(self, flavour, errors, formatter):
        for content in errors:
            self.writeln(self.doubleSeparator)
            self.writeln('%s: %s' % (flavour, content[0].id()))
            self.writeln('')
            self.write(formatter(*(content[1:])))

    def _printExpectedFailure(self, error, todo):
        return 'Reason: %r\n%s' % (todo.reason,
                                   self._formatFailureTraceback(error))

    def _printUnexpectedSuccess(self, todo):
        ret = 'Reason: %r\n' % (todo.reason,)
        if todo.errors:
            ret += 'Expected errors: %s\n' % (', '.join(todo.errors),)
        return ret

    def printErrors(self):
        """Print all of the non-success results in full to the stream.
        """
        self.write('\n')
        self._printResults('[SKIPPED]', self.skips, lambda x : '%s\n' % x)
        self._printResults('[TODO]', self.expectedFailures,
                           self._printExpectedFailure)
        self._printResults('[FAIL]', self.failures,
                           self._formatFailureTraceback)
        self._printResults('[ERROR]', self.errors,
                           self._formatFailureTraceback)
        self._printResults('[SUCCESS!?!]', self.unexpectedSuccesses,
                           self._printUnexpectedSuccess)

    def printSummary(self):
        """Print a line summarising the test results to the stream.
        """
        summaries = []
        for stat in ("skips", "expectedFailures", "failures", "errors",
                     "unexpectedSuccesses", "successes"):
            num = len(getattr(self, stat))
            if num:
                summaries.append('%s=%d' % (stat, num))
        summary = (summaries and ' ('+', '.join(summaries)+')') or ''
        if not self.wasSuccessful():
            status = "FAILED"
        else:
            status = "PASSED"
        self.write("%s%s\n", status, summary)


class MinimalReporter(Reporter):
    """A minimalist reporter that prints only a summary of the test result,
    in the form of (timeTaken, #tests, #tests, #errors, #failures, #skips).
    """

    _runStarted = None

    def startTest(self, test):
        super(MinimalReporter, self).startTest(test)
        if self._runStarted is None:
            self._runStarted = self._getTime()

    def printErrors(self):
        pass

    def printSummary(self):
        numTests = self.testsRun
        t = (self._runStarted - self._getTime(), numTests, numTests,
             len(self.errors), len(self.failures), len(self.skips))
        self.writeln(' '.join(map(str, t)))


class TextReporter(Reporter):
    """
    Simple reporter that prints a single character for each test as it runs,
    along with the standard Trial summary text.
    """

    def addSuccess(self, test):
        super(TextReporter, self).addSuccess(test)
        self.write('.')

    def addError(self, *args):
        super(TextReporter, self).addError(*args)
        self.write('E')

    def addFailure(self, *args):
        super(TextReporter, self).addFailure(*args)
        self.write('F')

    def addSkip(self, *args):
        super(TextReporter, self).addSkip(*args)
        self.write('S')

    def addExpectedFailure(self, *args):
        super(TextReporter, self).addExpectedFailure(*args)
        self.write('T')

    def addUnexpectedSuccess(self, *args):
        super(TextReporter, self).addUnexpectedSuccess(*args)
        self.write('!')


class VerboseTextReporter(Reporter):
    """
    A verbose reporter that prints the name of each test as it is running.

    Each line is printed with the name of the test, followed by the result of
    that test.
    """

    # This is actually the bwverbose option

    def startTest(self, tm):
        self.write('%s ... ', tm.id())
        super(VerboseTextReporter, self).startTest(tm)

    def addSuccess(self, test):
        super(VerboseTextReporter, self).addSuccess(test)
        self.write('[OK]')

    def addError(self, *args):
        super(VerboseTextReporter, self).addError(*args)
        self.write('[ERROR]')

    def addFailure(self, *args):
        super(VerboseTextReporter, self).addFailure(*args)
        self.write('[FAILURE]')

    def addSkip(self, *args):
        super(VerboseTextReporter, self).addSkip(*args)
        self.write('[SKIPPED]')

    def addExpectedFailure(self, *args):
        super(VerboseTextReporter, self).addExpectedFailure(*args)
        self.write('[TODO]')

    def addUnexpectedSuccess(self, *args):
        super(VerboseTextReporter, self).addUnexpectedSuccess(*args)
        self.write('[SUCCESS!?!]')

    def stopTest(self, test):
        super(VerboseTextReporter, self).stopTest(test)
        self.write('\n')


class TimingTextReporter(VerboseTextReporter):
    """Prints out each test as it is running, followed by the time taken for each
    test to run.
    """

    def stopTest(self, method):
        super(TimingTextReporter, self).stopTest(method)
        self.write("(%.03f secs)\n" % self._lastTime)


class _AnsiColorizer(object):
    """
    A colorizer is an object that loosely wraps around a stream, allowing
    callers to write text to the stream in a particular color.

    Colorizer classes must implement C{supported()} and C{write(text, color)}.
    """
    _colors = dict(black=30, red=31, green=32, yellow=33,
                   blue=34, magenta=35, cyan=36, white=37)

    def __init__(self, stream):
        self.stream = stream

    def supported(self):
        """
        A class method that returns True if the current platform supports
        coloring terminal output using this method. Returns False otherwise.
        """
        # assuming stderr
        # isatty() returns False when SSHd into Win32 machine
        if 'CYGWIN' in os.environ:
            return True
        if not sys.stderr.isatty():
            return False # auto color only on TTYs
        try:
            import curses
            curses.setupterm()
            return curses.tigetnum("colors") > 2
        except:
            # guess false in case of error
            return False
    supported = classmethod(supported)

    def write(self, text, color):
        """
        Write the given text to the stream in the given color.

        @param text: Text to be written to the stream.

        @param color: A string label for a color. e.g. 'red', 'white'.
        """
        color = self._colors[color]
        self.stream.write('\x1b[%s;1m%s\x1b[0m' % (color, text))


class _Win32Colorizer(object):
    """
    See _AnsiColorizer docstring.
    """
    def __init__(self, stream):
        from win32console import GetStdHandle, STD_OUTPUT_HANDLE, \
             FOREGROUND_RED, FOREGROUND_BLUE, FOREGROUND_GREEN, \
             FOREGROUND_INTENSITY
        red, green, blue, bold = (FOREGROUND_RED, FOREGROUND_GREEN,
                                  FOREGROUND_BLUE, FOREGROUND_INTENSITY)
        self.stream = stream
        self.screenBuffer = GetStdHandle(STD_OUTPUT_HANDLE)
        self._colors = {
            'normal': red | green | blue,
            'red': red | bold,
            'green': green | bold,
            'blue': blue | bold,
            'yellow': red | green | bold,
            'magenta': red | blue | bold,
            'cyan': green | blue | bold,
            'white': red | green | blue | bold
            }

    def supported(self):
        try:
            import win32console
            screenBuffer = win32console.GetStdHandle(
                win32console.STD_OUTPUT_HANDLE)
        except ImportError:
            return False
        import pywintypes
        try:
            screenBuffer.SetConsoleTextAttribute(
                win32console.FOREGROUND_RED |
                win32console.FOREGROUND_GREEN |
                win32console.FOREGROUND_BLUE)
        except pywintypes.error:
            return False
        else:
            return True
    supported = classmethod(supported)

    def write(self, text, color):
        color = self._colors[color]
        self.screenBuffer.SetConsoleTextAttribute(color)
        self.stream.write(text)
        self.screenBuffer.SetConsoleTextAttribute(self._colors['normal'])


class _NullColorizer(object):
    """
    See _AnsiColorizer docstring.
    """
    def __init__(self, stream):
        self.stream = stream

    def supported(self):
        return True
    supported = classmethod(supported)

    def write(self, text, color):
        self.stream.write(text)


class TreeReporter(Reporter):
    """Print out the tests in the form a tree.

    Tests are indented according to which class and module they belong.
    Results are printed in ANSI color.
    """

    currentLine = ''
    indent = '  '
    columns = 79

    FAILURE = 'red'
    ERROR = 'red'
    TODO = 'blue'
    SKIP = 'blue'
    TODONE = 'red'
    SUCCESS = 'green'

    def __init__(self, stream=sys.stdout, tbformat='default', realtime=False):
        super(TreeReporter, self).__init__(stream, tbformat, realtime)
        self._lastTest = []
        for colorizer in [_Win32Colorizer, _AnsiColorizer, _NullColorizer]:
            if colorizer.supported():
                self._colorizer = colorizer(stream)
                break

    def getDescription(self, test):
        """
        Return the name of the method which 'test' represents.  This is
        what gets displayed in the leaves of the tree.

        e.g. getDescription(TestCase('test_foo')) ==> test_foo
        """
        return test.id().split('.')[-1]

    def addSuccess(self, test):
        super(TreeReporter, self).addSuccess(test)
        self.endLine('[OK]', self.SUCCESS)

    def addError(self, *args):
        super(TreeReporter, self).addError(*args)
        self.endLine('[ERROR]', self.ERROR)

    def addFailure(self, *args):
        super(TreeReporter, self).addFailure(*args)
        self.endLine('[FAIL]', self.FAILURE)

    def addSkip(self, *args):
        super(TreeReporter, self).addSkip(*args)
        self.endLine('[SKIPPED]', self.SKIP)

    def addExpectedFailure(self, *args):
        super(TreeReporter, self).addExpectedFailure(*args)
        self.endLine('[TODO]', self.TODO)

    def addUnexpectedSuccess(self, *args):
        super(TreeReporter, self).addUnexpectedSuccess(*args)
        self.endLine('[SUCCESS!?!]', self.TODONE)

    def write(self, format, *args):
        if args:
            format = format % args
        self.currentLine = format
        super(TreeReporter, self).write(self.currentLine)

    def _testPrelude(self, test):
        segments = [test.__class__.__module__, test.__class__.__name__]
        indentLevel = 0
        for seg in segments:
            if indentLevel < len(self._lastTest):
                if seg != self._lastTest[indentLevel]:
                    self.write('%s%s\n' % (self.indent * indentLevel, seg))
            else:
                self.write('%s%s\n' % (self.indent * indentLevel, seg))
            indentLevel += 1
        self._lastTest = segments

    def cleanupErrors(self, errs):
        self._colorizer.write('    cleanup errors', self.ERROR)
        self.endLine('[ERROR]', self.ERROR)
        super(TreeReporter, self).cleanupErrors(errs)

    def upDownError(self, method, error, warn, printStatus):
        self.write(self.color("  %s" % method, self.ERROR))
        if printStatus:
            self.endLine('[ERROR]', self.ERROR)
        super(TreeReporter, self).upDownError(method, error, warn, printStatus)

    def startTest(self, method):
        self._testPrelude(method)
        self.write('%s%s ... ' % (self.indent * (len(self._lastTest)),
                                  self.getDescription(method)))
        super(TreeReporter, self).startTest(method)

    def endLine(self, message, color):
        spaces = ' ' * (self.columns - len(self.currentLine) - len(message))
        super(TreeReporter, self).write(spaces)
        self._colorizer.write(message, color)
        super(TreeReporter, self).write("\n")
