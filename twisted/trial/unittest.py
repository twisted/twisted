# -*- test-case-name: twisted.test.test_trial -*-

"""
Twisted Test Framework
"""

from __future__ import nested_scopes

# twisted imports
from twisted.python.compat import *
from twisted.python import reflect, log, failure, components
from twisted.internet import interfaces

# system imports
import sys, time, string, traceback, types, os, glob, inspect, pdb
try:
    import gc # not available in jython
except ImportError:
    gc = None

log.startKeepingErrors()


class SkipTest(Exception):
    """Raise this (with a reason) to skip the current test. You may also set
    method.skip to a reason string to skip it, or set class.skip to skip the
    entire TestCase."""
    pass

class FailTest(AssertionError):
    """Raised to indicate the current test has failed to pass."""
    pass

# Set this to True if you want to disambiguate between test failures and
# other assertions.  If you are in the habit of using the "assert" statement
# in your tests, you probably want to leave this false.
ASSERTION_IS_ERROR = 0

class TestCase:
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def fail(self, message=None):
        raise FailTest, message

    def failIf(self, condition, message=None):
        if condition:
            raise FailTest, message

    def failUnless(self, condition, message=None):
        if not condition:
            raise FailTest, message

    def failUnlessRaises(self, exception, f, *args, **kwargs):
        try:
            f(*args, **kwargs)
        except exception:
            return
        except:
            raise FailTest, '%s raised instead of %s' % (sys.exc_info()[0],
                                                         exception.__name__)
        else:
            raise FailTest, '%s not raised' % exception.__name__

    def failUnlessEqual(self, first, second, msg=None):
        if not first == second:
            raise FailTest, (msg or '%r != %r' % (first, second))

    def failUnlessIdentical(self, first, second, msg=None):
        if first is not second:
            raise FailTest, (msg or '%r is not %r' % (first, second))

    def failIfEqual(self, first, second, msg=None):
        if not first != second:
            raise FailTest, (msg or '%r == %r' % (first, second))

    assertEqual = assertEquals = failUnlessEqual
    assertNotEqual = assertNotEquals = failIfEqual
    assertRaises = failUnlessRaises
    assert_ = failUnless
    failIfEquals = failIfEqual
    assertIdentical = failUnlessIdentical

    def assertApproximates(self, first, second, tolerance, msg=None):
        if abs(first - second) > tolerance:
            raise FailTest, (msg or "%s ~== %s" % (first, second))

# Methods in this list will be omitted from a failed test's traceback if
# they are the final frame.
_failureConditionals = [
    'fail', 'failIf', 'failUnless', 'failUnlessRaises', 'failUnlessEqual',
    'failUnlessIdentical', 'failIfEqual', 'assertApproximates']

def isTestClass(testClass):
    return issubclass(testClass, TestCase)

def isTestCase(testCase):
    return isinstance(testCase, TestCase)


class TestSuite:
    methodPrefix = 'test'
    moduleGlob = 'test_*.py'

    def __init__(self):
        self.testClasses = {}
        self.numTests = 0
        self.couldNotImport = {}
        self.testMethods = []

    def addMethod(self, method):
        """Add a single method of a test case class to this test suite.
        """
        if type(method) is types.StringType:
            klass = reflect.namedObject('.'.join(method.split('.')[:-1]))
            methodName = method.split('.')[-1]
        else:
            klass = method.im_class
            methodName = method.__name__
        self.testMethods.append((klass, methodName))
        self.numTests += 1

    def addTestClass(self, testClass):
        methods = [getattr(testClass, "%s%s" % (self.methodPrefix, name)) for name in
                   reflect.prefixedMethodNames(testClass, self.methodPrefix)]
        self.testClasses[testClass] = methods
        self.numTests += len(methods)

    def addModule(self, module):
        if type(module) is types.StringType:
            try:
                module = reflect.namedModule(module)
            except (ImportError, Warning), e:
                self.couldNotImport[module] = e
                return
        names = dir(module)
        for name in names:
            obj = getattr(module, name)
            if type(obj) is types.ClassType and isTestClass(obj):
                self.addTestClass(obj)

    def addPackage(self, package):
        if type(package) is types.StringType:
            try:
                package = reflect.namedModule(packageName)
            except ImportError, e:
                self.couldNotImport[packageName] = e
                return
        modGlob = os.path.join(os.path.dirname(package.__file__),
                               self.moduleGlob)
        modules = map(reflect.filenameToModuleName, glob.glob(modGlob))
        for module in modules:
            self.addModule(module)

    def runOneTest(self, testClass, testCase, method, output):
        ok = 0
        if not ASSERTION_IS_ERROR:
            failingExceptionType = AssertionError
        else:
            failingExceptionType = FailTest

        try:
            if getattr(method, "skip", None):
                raise SkipTest, method.skip
            if getattr(testCase, "skip", None):
                raise SkipTest, testCase.skip
            testCase.setUp()
            method(testCase)
        except failingExceptionType, e:
            output.reportFailure(testClass, method, sys.exc_info())
        except KeyboardInterrupt:
            raise
        except SkipTest, r:
            reason = None
            if len(r.args) > 0:
                reason = r.args[0]
            if reason:
                output.reportSkip(testClass, method, reason)
            else:
                output.reportSkip(testClass, method, sys.exc_info())
        except:
            output.reportError(testClass, method, sys.exc_info())
        else:
            ok = 1

        try:
            testCase.tearDown()
        except failingExceptionType, e:
            if ok:
                output.reportFailure(testClass, method, sys.exc_info())
            ok = 0
        except KeyboardInterrupt:
            raise
        except:
            if ok:
                output.reportError(testClass, method, sys.exc_info())
            ok = 0

        try:
            from twisted.internet import reactor
            reactor.iterate() # flush short-range timers
            pending = reactor.getDelayedCalls()
            if pending:
                msg = "\npendingTimedCalls still pending:\n"
                for p in pending:
                    msg += " %s\n" % p
                from warnings import warn
                warn(msg)
                for p in pending: p.cancel() # delete the rest
                reactor.iterate() # flush them
                # this will go live someday: tests should not leave
                # lingering surprises
                testCase.fail(msg)
            if components.implements(reactor, interfaces.IReactorThreads):
                reactor.suggestThreadPoolSize(0)
                if hasattr(reactor, 'threadpool'):
                    reactor.threadpool.stop()
                    reactor.threadpool = None
        except failingExceptionType, e:
            if ok:
                output.reportFailure(testClass, method, sys.exc_info())
            ok = 0
        except KeyboardInterrupt:
            raise
        except:
            if ok:
                output.reportError(testClass, method, sys.exc_info())
            ok = 0

        # garbage collect now, to make sure any Deferreds with pending
        # errbacks are caught and counted against this test, not some later
        # one.
        if gc:
            gc.collect()

        for e in log.flushErrors():
            ok = 0
            output.reportError(testClass, method, e)

        if ok:
            output.reportSuccess(testClass, method)

    def run(self, output, seed = None):
        output.start(self.numTests)
        testClasses = self.testClasses.keys()
        testClasses.sort(lambda x,y: cmp((x.__module__, x.__name__),
                                         (y.__module__, y.__name__)))

        r = None
        if seed is not None:
            import random
            r = random.Random(seed)
            r.shuffle(testClasses)
            output.writeln('Running tests shuffled with seed %d' % seed)

        ## Run all the single-method tests we want to run.
        for testClass, methodName in self.testMethods:
            testCase  = testClass()
            method = getattr(testClass, methodName)
            output.reportStart(testClass, method)
            self.runOneTest(testClass, testCase, method, output)

        for testClass in testClasses:
            testCase = testClass()
            for method in self.testClasses[testClass]:
                output.reportStart(testClass, method)
                self.runOneTest(testClass, testCase, method, output)
        for name, exc in self.couldNotImport.items():
            output.reportImportError(name, exc)

        output.stop()

def extract_tb(tb, limit=None):
    """Extract a list of frames from a traceback, without unittest internals.

    Functionally identical to L{traceback.extract_tb}, but cropped to just
    the test case itself, excluding frames that are part of the Trial
    testing framework.
    """
    l = traceback.extract_tb(tb, limit)
    myfile = __file__.replace('.pyc','.py')
    # filename, line, funcname, sourcetext
    if (l[0][0] == myfile) and (l[0][2] == 'runOneTest'):
        del l[0]
    if (l[-1][0] == myfile) and (l[-1][2] in _failureConditionals):
        del l[-1]
    return l

def format_exception(eType, eValue, tb, limit=None):
    """A formatted traceback and exception, without exposing the framework.

    I am identical in function to L{traceback.format_exception},
    but I screen out frames from the traceback that are part of
    the testing framework itself, leaving only the code being tested.
    """
    # Only mess with tracebacks if they are from an explicitly failed
    # test.
    if eType != FailTest:
        return traceback.format_exception(eType, eValue, tb, limit)

    tb_list = extract_tb(tb, limit)

    l = ["Traceback (most recent call last):\n"]
    l.extend(traceback.format_list(tb_list))
    l.extend(traceback.format_exception_only(eType, eValue))
    return l

class Reporter:
    """I report results from a run of a test suite.

    @ivar errors: Tests which have encountered an error.
    @type errors: List of (testClass, method, exc_info) tuples.
    @ivar failures: Tests which have failed.
    @type failures: List of (testClass, method, exc_info) tuples.
    @ivar skips: Tests which have been skipped.
    @type skips: List of (testClass, method, exc_info) tuples.
    @ivar imports: Import errors encountered while assembling the test suite.
    @type imports: List of (moduleName, exception) tuples.
    @ivar numTests: The number of tests I have reports for.
    @type numTests: int
    @ivar expectedTests: The number of tests I expect to run.
    @type expectedTests: int
    @ivar debugger: Run the debugger when encountering a failing test.
    @type debugger: bool
    """
    def __init__(self):
        self.errors = []
        self.failures = []
        self.skips = []
        self.imports = []
        self.numTests = 0
        self.expectedTests = 0
        self.debugger = False

    def start(self, expectedTests):
        self.expectedTests = expectedTests
        self.startTime = time.time()

    def reportImportError(self, name, exc):
        self.imports.append((name, exc))

    def reportStart(self, testClass, method):
        pass

    def reportSkip(self, testClass, method, exc_info):
        self.skips.append((testClass, method, exc_info))
        self.numTests += 1

    def reportFailure(self, testClass, method, exc_info):
        if self.debugger:
            if isinstance(exc_info, failure.Failure):
                raise TypeError, "Failure, not Exception -- you lose."
            else:
                pdb.post_mortem(exc_info[2])
        self.failures.append((testClass, method, exc_info))
        self.numTests += 1

    def reportError(self, testClass, method, exc_info):
        if self.debugger:
            if isinstance(exc_info, failure.Failure):
                raise TypeError, "Failure, not Exception -- you lose."
            else:
                pdb.post_mortem(exc_info[2])
        self.errors.append((testClass, method, exc_info))
        self.numTests += 1

    def reportSuccess(self, testClass, method):
        self.numTests += 1

    def getRunningTime(self):
        if hasattr(self, 'stopTime'):
            return self.stopTime - self.startTime
        else:
            return time.time() - self.startTime

    def allPassed(self):
        return not (self.errors or self.failures)

    def stop(self):
        self.stopTime = time.time()

class MinimalReporter(Reporter):

    def __init__(self, fp):
        Reporter.__init__(self)
        self.fp = fp

    def stop(self):
        Reporter.stop(self)
        t =  (self.getRunningTime(), self.expectedTests, self.numTests,
               len(self.imports), len(self.errors), len(self.failures),
               len(self.skips))
        self.fp.write(' '.join(map(str,t))+'\n')

class TextReporter(Reporter):
    SEPARATOR = '-' * 79
    DOUBLE_SEPARATOR = '=' * 79

    def __init__(self, stream=sys.stdout):
        self.stream = stream
        Reporter.__init__(self)

    def reportFailure(self, testClass, method, exc_info):
        self.write('F')
        Reporter.reportFailure(self, testClass, method, exc_info)

    def reportError(self, testClass, method, exc_info):
        self.write('E')
        Reporter.reportError(self, testClass, method, exc_info)

    def reportSkip(self, testClass, method, exc_info):
        self.write('S')
        Reporter.reportSkip(self, testClass, method, exc_info)

    def reportSuccess(self, testClass, method):
        self.write('.')
        Reporter.reportSuccess(self, testClass, method)

    def _formatError(self, flavor, (testClass, method, error)):
        if isinstance(error, failure.Failure):
            tb = error.getBriefTraceback()
        elif type(error) == types.TupleType:
            tb = string.join(apply(format_exception, error))
        else:
            tb = "%s\n" % error

        ret = ("%s\n%s: %s (%s)\n%s\n%s" %
               (self.DOUBLE_SEPARATOR,
                flavor, method.__name__, reflect.qual(testClass),
                self.SEPARATOR,
                tb))
        return ret

    def write(self, format, *args):
        if args:
            self.stream.write(format % args)
        else:
            self.stream.write(format)
        self.stream.flush()

    def writeln(self, format=None, *args):
        if format is not None:
            self.stream.write(format % args)
        self.stream.write('\n')
        self.stream.flush()

    def _statusReport(self):
        summaries = []
        if self.failures:
            summaries.append('failures=%d' % len(self.failures))
        if self.errors:
            summaries.append('errors=%d' % len(self.errors))
        if self.skips:
            summaries.append('skips=%d' % len(self.skips))
        summary = (summaries and ' ('+', '.join(summaries)+')') or ''
        if self.failures or self.errors:
            status = 'FAILED'
        else:
            status = 'OK'
        return '%s%s' % (status, summary)

    def stop(self):
        Reporter.stop(self)
        self.writeln()
        for error in self.failures:
            self.write(self._formatError('FAILURE', error))
        for error in self.errors:
            self.write(self._formatError('ERROR', error))
        for error in self.skips:
            self.write(self._formatError('SKIPPED', error))
        self.writeln(self.SEPARATOR)
        self.writeln('Ran %d tests in %.3fs', self.numTests, self.getRunningTime())
        self.writeln()
        self.writeln(self._statusReport())
        if self.imports:
            self.writeln()
            for name, exc in self.imports:
                self.writeln('Could not import %s: %s'
                             % (name, exc.args[0]))
            self.writeln()

class VerboseTextReporter(TextReporter):
    def __init__(self, stream=sys.stdout):
        TextReporter.__init__(self, stream)

    def reportStart(self, testClass, method):
        self.write('%s (%s) ... ', method.__name__, reflect.qual(testClass))

    def reportSuccess(self, testClass, method):
        self.writeln('[OK]')
        Reporter.reportSuccess(self, testClass, method)

    def reportFailure(self, testClass, method, exc_info):
        self.writeln('[FAIL]')
        Reporter.reportFailure(self, testClass, method, exc_info)

    def reportError(self, testClass, method, exc_info):
        self.writeln('[ERROR]')
        Reporter.reportError(self, testClass, method, exc_info)

    def reportSkip(self, testClass, method, exc_info):
        self.writeln('[SKIPPED]')
        Reporter.reportSkip(self, testClass, method, exc_info)

class TreeReporter(TextReporter):
    columns = 79

    BLACK = 30
    RED = 31
    GREEN = 32
    YELLOW = 33
    BLUE = 34
    MAGENTA = 35
    CYAN = 36
    WHITE = 37

    def __init__(self, stream=sys.stdout):
        TextReporter.__init__(self, stream)
        self.lastModule = None
        self.lastClass = None

    def reportStart(self, testClass, method):
        if testClass.__module__ != self.lastModule:
            self.writeln(testClass.__module__)
            self.lastModule = testClass.__module__
        if testClass != self.lastClass:
            self.writeln('  %s' % testClass.__name__)
            self.lastClass = testClass

        docstr = inspect.getdoc(method)
        if docstr:
            # inspect trims whitespace on the left; the lstrip here is
            # for those odd folks who start docstrings with a blank line.
            what = docstr.lstrip().split('\n', 1)[0]
        else:
            what = method.__name__
        self.currentLine = '    %s ... ' % (what,)
        self.write(self.currentLine)

    def color(self, text, color):
        return '%s%s;1m%s%s0m' % ('\x1b[', color, text, '\x1b[')

    def endLine(self, message, color):
        import string
        spaces = ' ' * (self.columns - len(self.currentLine) - len(message))
        self.write(spaces)
        self.writeln(self.color(message, color))

    def reportSuccess(self, testClass, method):
        self.endLine('[OK]', self.GREEN)
        Reporter.reportSuccess(self, testClass, method)

    def reportFailure(self, testClass, method, exc_info):
        self.endLine('[FAIL]', self.RED)
        Reporter.reportFailure(self, testClass, method, exc_info)

    def reportError(self, testClass, method, exc_info):
        self.endLine('[ERROR]', self.RED)
        Reporter.reportError(self, testClass, method, exc_info)

    def reportSkip(self, testClass, method, exc_info):
        self.endLine('[SKIPPED]', self.BLUE)
        Reporter.reportSkip(self, testClass, method, exc_info)



def _getDeferredResult(d, timeout=None):
    from twisted.internet import reactor
    if timeout is not None:
        d.setTimeout(timeout)
    resultSet = []
    d.addCallbacks(resultSet.append, resultSet.append)
    while not resultSet:
        reactor.iterate()
    return resultSet[0]

def deferredResult(d, timeout=None):
    """Waits for a Deferred to arrive, then returns or throws an exception,
    based on the result.
    """
    result = _getDeferredResult(d, timeout)
    if isinstance(result, failure.Failure):
        raise result
    else:
        return result

def deferredError(d, timeout=None):
    """Waits for deferred to fail, and it returns the Failure.

    If the deferred succeeds, raises FailTest.
    """
    result = _getDeferredResult(d, timeout)
    if isinstance(result, failure.Failure):
        return result
    else:
        raise FailTest, "Deferred did not fail: %r" % result


# Local Variables:
# test-case-name: "twisted.test.test_trial"
# End:
