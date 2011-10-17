# -*- test-case-name: twisted.trial.test.test_tests -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Things likely to be used by writers of unit tests.

Maintainer: Jonathan Lange
"""


import doctest, inspect
import os, warnings, sys, tempfile, gc, types
from pprint import pformat
from dis import findlinestarts as _findlinestarts

from twisted.internet import defer, utils
from twisted.python import components, failure, log, monkey
from twisted.python.deprecate import getDeprecationWarningString

from twisted.trial import itrial, reporter, util

pyunit = __import__('unittest')

from zope.interface import implements



class SkipTest(Exception):
    """
    Raise this (with a reason) to skip the current test. You may also set
    method.skip to a reason string to skip it, or set class.skip to skip the
    entire TestCase.
    """


class FailTest(AssertionError):
    """Raised to indicate the current test has failed to pass."""


class Todo(object):
    """
    Internal object used to mark a L{TestCase} as 'todo'. Tests marked 'todo'
    are reported differently in Trial L{TestResult}s. If todo'd tests fail,
    they do not fail the suite and the errors are reported in a separate
    category. If todo'd tests succeed, Trial L{TestResult}s will report an
    unexpected success.
    """

    def __init__(self, reason, errors=None):
        """
        @param reason: A string explaining why the test is marked 'todo'

        @param errors: An iterable of exception types that the test is
        expected to raise. If one of these errors is raised by the test, it
        will be trapped. Raising any other kind of error will fail the test.
        If C{None} is passed, then all errors will be trapped.
        """
        self.reason = reason
        self.errors = errors

    def __repr__(self):
        return "<Todo reason=%r errors=%r>" % (self.reason, self.errors)

    def expected(self, failure):
        """
        @param failure: A L{twisted.python.failure.Failure}.

        @return: C{True} if C{failure} is expected, C{False} otherwise.
        """
        if self.errors is None:
            return True
        for error in self.errors:
            if failure.check(error):
                return True
        return False


def makeTodo(value):
    """
    Return a L{Todo} object built from C{value}.

    If C{value} is a string, return a Todo that expects any exception with
    C{value} as a reason. If C{value} is a tuple, the second element is used
    as the reason and the first element as the excepted error(s).

    @param value: A string or a tuple of C{(errors, reason)}, where C{errors}
    is either a single exception class or an iterable of exception classes.

    @return: A L{Todo} object.
    """
    if isinstance(value, str):
        return Todo(reason=value)
    if isinstance(value, tuple):
        errors, reason = value
        try:
            errors = list(errors)
        except TypeError:
            errors = [errors]
        return Todo(reason=reason, errors=errors)



class _Warning(object):
    """
    A L{_Warning} instance represents one warning emitted through the Python
    warning system (L{warnings}).  This is used to insulate callers of
    L{_collectWarnings} from changes to the Python warnings system which might
    otherwise require changes to the warning objects that function passes to
    the observer object it accepts.

    @ivar message: The string which was passed as the message parameter to
        L{warnings.warn}.

    @ivar category: The L{Warning} subclass which was passed as the category
        parameter to L{warnings.warn}.

    @ivar filename: The name of the file containing the definition of the code
        object which was C{stacklevel} frames above the call to
        L{warnings.warn}, where C{stacklevel} is the value of the C{stacklevel}
        parameter passed to L{warnings.warn}.

    @ivar lineno: The source line associated with the active instruction of the
        code object object which was C{stacklevel} frames above the call to
        L{warnings.warn}, where C{stacklevel} is the value of the C{stacklevel}
        parameter passed to L{warnings.warn}.
    """
    def __init__(self, message, category, filename, lineno):
        self.message = message
        self.category = category
        self.filename = filename
        self.lineno = lineno


def _setWarningRegistryToNone(modules):
    """
    Disable the per-module cache for every module found in C{modules}, typically
    C{sys.modules}.

    @param modules: Dictionary of modules, typically sys.module dict
    """
    for v in modules.values():
        if v is not None:
            try:
                v.__warningregistry__ = None
            except:
                # Don't specify a particular exception type to handle in case
                # some wacky object raises some wacky exception in response to
                # the setattr attempt.
                pass


def _collectWarnings(observeWarning, f, *args, **kwargs):
    """
    Call C{f} with C{args} positional arguments and C{kwargs} keyword arguments
    and collect all warnings which are emitted as a result in a list.

    @param observeWarning: A callable which will be invoked with a L{_Warning}
        instance each time a warning is emitted.

    @return: The return value of C{f(*args, **kwargs)}.
    """
    def showWarning(message, category, filename, lineno, file=None, line=None):
        assert isinstance(message, Warning)
        observeWarning(_Warning(
                message.args[0], category, filename, lineno))

    # Disable the per-module cache for every module otherwise if the warning
    # which the caller is expecting us to collect was already emitted it won't
    # be re-emitted by the call to f which happens below.
    _setWarningRegistryToNone(sys.modules)

    origFilters = warnings.filters[:]
    origShow = warnings.showwarning
    warnings.simplefilter('always')
    try:
        warnings.showwarning = showWarning
        result = f(*args, **kwargs)
    finally:
        warnings.filters[:] = origFilters
        warnings.showwarning = origShow
    return result



class _Assertions(pyunit.TestCase, object):
    """
    Replaces many of the built-in TestCase assertions. In general, these
    assertions provide better error messages and are easier to use in
    callbacks. Also provides new assertions such as L{failUnlessFailure}.

    Although the tests are defined as 'failIf*' and 'failUnless*', they can
    also be called as 'assertNot*' and 'assert*'.
    """

    def fail(self, msg=None):
        """
        Absolutely fail the test.  Do not pass go, do not collect $200.

        @param msg: the message that will be displayed as the reason for the
        failure
        """
        raise self.failureException(msg)

    def failIf(self, condition, msg=None):
        """
        Fail the test if C{condition} evaluates to True.

        @param condition: any object that defines __nonzero__
        """
        if condition:
            raise self.failureException(msg)
        return condition
    assertNot = assertFalse = failUnlessFalse = failIf

    def failUnless(self, condition, msg=None):
        """
        Fail the test if C{condition} evaluates to False.

        @param condition: any object that defines __nonzero__
        """
        if not condition:
            raise self.failureException(msg)
        return condition
    assert_ = assertTrue = failUnlessTrue = failUnless

    def failUnlessRaises(self, exception, f, *args, **kwargs):
        """
        Fail the test unless calling the function C{f} with the given
        C{args} and C{kwargs} raises C{exception}. The failure will report
        the traceback and call stack of the unexpected exception.

        @param exception: exception type that is to be expected
        @param f: the function to call

        @return: The raised exception instance, if it is of the given type.
        @raise self.failureException: Raised if the function call does
            not raise an exception or if it raises an exception of a
            different type.
        """
        try:
            result = f(*args, **kwargs)
        except exception, inst:
            return inst
        except:
            raise self.failureException('%s raised instead of %s:\n %s'
                                        % (sys.exc_info()[0],
                                           exception.__name__,
                                           failure.Failure().getTraceback()))
        else:
            raise self.failureException('%s not raised (%r returned)'
                                        % (exception.__name__, result))
    assertRaises = failUnlessRaises


    def assertEqual(self, first, second, msg=''):
        """
        Fail the test if C{first} and C{second} are not equal.

        @param msg: A string describing the failure that's included in the
            exception.
        """
        if not first == second:
            if msg is None:
                msg = ''
            if len(msg) > 0:
                msg += '\n'
            raise self.failureException(
                '%snot equal:\na = %s\nb = %s\n'
                % (msg, pformat(first), pformat(second)))
        return first
    failUnlessEqual = failUnlessEquals = assertEquals = assertEqual


    def failUnlessIdentical(self, first, second, msg=None):
        """
        Fail the test if C{first} is not C{second}.  This is an
        obect-identity-equality test, not an object equality
        (i.e. C{__eq__}) test.

        @param msg: if msg is None, then the failure message will be
        '%r is not %r' % (first, second)
        """
        if first is not second:
            raise self.failureException(msg or '%r is not %r' % (first, second))
        return first
    assertIdentical = failUnlessIdentical

    def failIfIdentical(self, first, second, msg=None):
        """
        Fail the test if C{first} is C{second}.  This is an
        obect-identity-equality test, not an object equality
        (i.e. C{__eq__}) test.

        @param msg: if msg is None, then the failure message will be
        '%r is %r' % (first, second)
        """
        if first is second:
            raise self.failureException(msg or '%r is %r' % (first, second))
        return first
    assertNotIdentical = failIfIdentical

    def failIfEqual(self, first, second, msg=None):
        """
        Fail the test if C{first} == C{second}.

        @param msg: if msg is None, then the failure message will be
        '%r == %r' % (first, second)
        """
        if not first != second:
            raise self.failureException(msg or '%r == %r' % (first, second))
        return first
    assertNotEqual = assertNotEquals = failIfEquals = failIfEqual

    def failUnlessIn(self, containee, container, msg=None):
        """
        Fail the test if C{containee} is not found in C{container}.

        @param containee: the value that should be in C{container}
        @param container: a sequence type, or in the case of a mapping type,
                          will follow semantics of 'if key in dict.keys()'
        @param msg: if msg is None, then the failure message will be
                    '%r not in %r' % (first, second)
        """
        if containee not in container:
            raise self.failureException(msg or "%r not in %r"
                                        % (containee, container))
        return containee
    assertIn = failUnlessIn

    def failIfIn(self, containee, container, msg=None):
        """
        Fail the test if C{containee} is found in C{container}.

        @param containee: the value that should not be in C{container}
        @param container: a sequence type, or in the case of a mapping type,
                          will follow semantics of 'if key in dict.keys()'
        @param msg: if msg is None, then the failure message will be
                    '%r in %r' % (first, second)
        """
        if containee in container:
            raise self.failureException(msg or "%r in %r"
                                        % (containee, container))
        return containee
    assertNotIn = failIfIn

    def failIfAlmostEqual(self, first, second, places=7, msg=None):
        """
        Fail if the two objects are equal as determined by their
        difference rounded to the given number of decimal places
        (default 7) and comparing to zero.

        @note: decimal places (from zero) is usually not the same
               as significant digits (measured from the most
               signficant digit).

        @note: included for compatiblity with PyUnit test cases
        """
        if round(second-first, places) == 0:
            raise self.failureException(msg or '%r == %r within %r places'
                                        % (first, second, places))
        return first
    assertNotAlmostEqual = assertNotAlmostEquals = failIfAlmostEqual
    failIfAlmostEquals = failIfAlmostEqual

    def failUnlessAlmostEqual(self, first, second, places=7, msg=None):
        """
        Fail if the two objects are unequal as determined by their
        difference rounded to the given number of decimal places
        (default 7) and comparing to zero.

        @note: decimal places (from zero) is usually not the same
               as significant digits (measured from the most
               signficant digit).

        @note: included for compatiblity with PyUnit test cases
        """
        if round(second-first, places) != 0:
            raise self.failureException(msg or '%r != %r within %r places'
                                        % (first, second, places))
        return first
    assertAlmostEqual = assertAlmostEquals = failUnlessAlmostEqual
    failUnlessAlmostEquals = failUnlessAlmostEqual

    def failUnlessApproximates(self, first, second, tolerance, msg=None):
        """
        Fail if C{first} - C{second} > C{tolerance}

        @param msg: if msg is None, then the failure message will be
                    '%r ~== %r' % (first, second)
        """
        if abs(first - second) > tolerance:
            raise self.failureException(msg or "%s ~== %s" % (first, second))
        return first
    assertApproximates = failUnlessApproximates

    def failUnlessFailure(self, deferred, *expectedFailures):
        """
        Fail if C{deferred} does not errback with one of C{expectedFailures}.
        Returns the original Deferred with callbacks added. You will need
        to return this Deferred from your test case.
        """
        def _cb(ignore):
            raise self.failureException(
                "did not catch an error, instead got %r" % (ignore,))

        def _eb(failure):
            if failure.check(*expectedFailures):
                return failure.value
            else:
                output = ('\nExpected: %r\nGot:\n%s'
                          % (expectedFailures, str(failure)))
                raise self.failureException(output)
        return deferred.addCallbacks(_cb, _eb)
    assertFailure = failUnlessFailure

    def failUnlessSubstring(self, substring, astring, msg=None):
        """
        Fail if C{substring} does not exist within C{astring}.
        """
        return self.failUnlessIn(substring, astring, msg)
    assertSubstring = failUnlessSubstring

    def failIfSubstring(self, substring, astring, msg=None):
        """
        Fail if C{astring} contains C{substring}.
        """
        return self.failIfIn(substring, astring, msg)
    assertNotSubstring = failIfSubstring

    def failUnlessWarns(self, category, message, filename, f,
                       *args, **kwargs):
        """
        Fail if the given function doesn't generate the specified warning when
        called. It calls the function, checks the warning, and forwards the
        result of the function if everything is fine.

        @param category: the category of the warning to check.
        @param message: the output message of the warning to check.
        @param filename: the filename where the warning should come from.
        @param f: the function which is supposed to generate the warning.
        @type f: any callable.
        @param args: the arguments to C{f}.
        @param kwargs: the keywords arguments to C{f}.

        @return: the result of the original function C{f}.
        """
        warningsShown = []
        result = _collectWarnings(warningsShown.append, f, *args, **kwargs)

        if not warningsShown:
            self.fail("No warnings emitted")
        first = warningsShown[0]
        for other in warningsShown[1:]:
            if ((other.message, other.category)
                != (first.message, first.category)):
                self.fail("Can't handle different warnings")
        self.assertEqual(first.message, message)
        self.assertIdentical(first.category, category)

        # Use starts with because of .pyc/.pyo issues.
        self.failUnless(
            filename.startswith(first.filename),
            'Warning in %r, expected %r' % (first.filename, filename))

        # It would be nice to be able to check the line number as well, but
        # different configurations actually end up reporting different line
        # numbers (generally the variation is only 1 line, but that's enough
        # to fail the test erroneously...).
        # self.assertEqual(lineno, xxx)

        return result
    assertWarns = failUnlessWarns

    def failUnlessIsInstance(self, instance, classOrTuple, message=None):
        """
        Fail if C{instance} is not an instance of the given class or of
        one of the given classes.

        @param instance: the object to test the type (first argument of the
            C{isinstance} call).
        @type instance: any.
        @param classOrTuple: the class or classes to test against (second
            argument of the C{isinstance} call).
        @type classOrTuple: class, type, or tuple.

        @param message: Custom text to include in the exception text if the
            assertion fails.
        """
        if not isinstance(instance, classOrTuple):
            if message is None:
                suffix = ""
            else:
                suffix = ": " + message
            self.fail("%r is not an instance of %s%s" % (
                    instance, classOrTuple, suffix))
    assertIsInstance = failUnlessIsInstance

    def failIfIsInstance(self, instance, classOrTuple):
        """
        Fail if C{instance} is not an instance of the given class or of
        one of the given classes.

        @param instance: the object to test the type (first argument of the
            C{isinstance} call).
        @type instance: any.
        @param classOrTuple: the class or classes to test against (second
            argument of the C{isinstance} call).
        @type classOrTuple: class, type, or tuple.
        """
        if isinstance(instance, classOrTuple):
            self.fail("%r is an instance of %s" % (instance, classOrTuple))
    assertNotIsInstance = failIfIsInstance


class _LogObserver(object):
    """
    Observes the Twisted logs and catches any errors.

    @ivar _errors: A C{list} of L{Failure} instances which were received as
        error events from the Twisted logging system.

    @ivar _added: A C{int} giving the number of times C{_add} has been called
        less the number of times C{_remove} has been called; used to only add
        this observer to the Twisted logging since once, regardless of the
        number of calls to the add method.

    @ivar _ignored: A C{list} of exception types which will not be recorded.
    """

    def __init__(self):
        self._errors = []
        self._added = 0
        self._ignored = []


    def _add(self):
        if self._added == 0:
            log.addObserver(self.gotEvent)
            self._oldFE, log._flushErrors = (log._flushErrors, self.flushErrors)
            self._oldIE, log._ignore = (log._ignore, self._ignoreErrors)
            self._oldCI, log._clearIgnores = (log._clearIgnores,
                                              self._clearIgnores)
        self._added += 1

    def _remove(self):
        self._added -= 1
        if self._added == 0:
            log.removeObserver(self.gotEvent)
            log._flushErrors = self._oldFE
            log._ignore = self._oldIE
            log._clearIgnores = self._oldCI


    def _ignoreErrors(self, *errorTypes):
        """
        Do not store any errors with any of the given types.
        """
        self._ignored.extend(errorTypes)


    def _clearIgnores(self):
        """
        Stop ignoring any errors we might currently be ignoring.
        """
        self._ignored = []


    def flushErrors(self, *errorTypes):
        """
        Flush errors from the list of caught errors. If no arguments are
        specified, remove all errors. If arguments are specified, only remove
        errors of those types from the stored list.
        """
        if errorTypes:
            flushed = []
            remainder = []
            for f in self._errors:
                if f.check(*errorTypes):
                    flushed.append(f)
                else:
                    remainder.append(f)
            self._errors = remainder
        else:
            flushed = self._errors
            self._errors = []
        return flushed


    def getErrors(self):
        """
        Return a list of errors caught by this observer.
        """
        return self._errors


    def gotEvent(self, event):
        """
        The actual observer method. Called whenever a message is logged.

        @param event: A dictionary containing the log message. Actual
        structure undocumented (see source for L{twisted.python.log}).
        """
        if event.get('isError', False) and 'failure' in event:
            f = event['failure']
            if len(self._ignored) == 0 or not f.check(*self._ignored):
                self._errors.append(f)



_logObserver = _LogObserver()

_wait_is_running = []

class TestCase(_Assertions):
    """
    A unit test. The atom of the unit testing universe.

    This class extends C{unittest.TestCase} from the standard library. The
    main feature is the ability to return C{Deferred}s from tests and fixture
    methods and to have the suite wait for those C{Deferred}s to fire.

    To write a unit test, subclass C{TestCase} and define a method (say,
    'test_foo') on the subclass. To run the test, instantiate your subclass
    with the name of the method, and call L{run} on the instance, passing a
    L{TestResult} object.

    The C{trial} script will automatically find any C{TestCase} subclasses
    defined in modules beginning with 'test_' and construct test cases for all
    methods beginning with 'test'.

    If an error is logged during the test run, the test will fail with an
    error. See L{log.err}.

    @ivar failureException: An exception class, defaulting to C{FailTest}. If
    the test method raises this exception, it will be reported as a failure,
    rather than an exception. All of the assertion methods raise this if the
    assertion fails.

    @ivar skip: C{None} or a string explaining why this test is to be
    skipped. If defined, the test will not be run. Instead, it will be
    reported to the result object as 'skipped' (if the C{TestResult} supports
    skipping).

    @ivar suppress: C{None} or a list of tuples of C{(args, kwargs)} to be
    passed to C{warnings.filterwarnings}. Use these to suppress warnings
    raised in a test. Useful for testing deprecated code. See also
    L{util.suppress}.

    @ivar timeout: A real number of seconds. If set, the test will
    raise an error if it takes longer than C{timeout} seconds.
    If not set, util.DEFAULT_TIMEOUT_DURATION is used.

    @ivar todo: C{None}, a string or a tuple of C{(errors, reason)} where
    C{errors} is either an exception class or an iterable of exception
    classes, and C{reason} is a string. See L{Todo} or L{makeTodo} for more
    information.
    """

    implements(itrial.ITestCase)
    failureException = FailTest

    def __init__(self, methodName='runTest'):
        """
        Construct an asynchronous test case for C{methodName}.

        @param methodName: The name of a method on C{self}. This method should
        be a unit test. That is, it should be a short method that calls some of
        the assert* methods. If C{methodName} is unspecified, L{runTest} will
        be used as the test method. This is mostly useful for testing Trial.
        """
        super(TestCase, self).__init__(methodName)
        self._testMethodName = methodName
        testMethod = getattr(self, methodName)
        self._parents = [testMethod, self]
        self._parents.extend(util.getPythonContainers(testMethod))
        self._passed = False
        self._cleanups = []

    if sys.version_info >= (2, 6):
        # Override the comparison defined by the base TestCase which considers
        # instances of the same class with the same _testMethodName to be
        # equal.  Since trial puts TestCase instances into a set, that
        # definition of comparison makes it impossible to run the same test
        # method twice.  Most likely, trial should stop using a set to hold
        # tests, but until it does, this is necessary on Python 2.6.  Only
        # __eq__ and __ne__ are required here, not __hash__, since the
        # inherited __hash__ is compatible with these equality semantics.  A
        # different __hash__ might be slightly more efficient (by reducing
        # collisions), but who cares? -exarkun
        def __eq__(self, other):
            return self is other

        def __ne__(self, other):
            return self is not other


    def _run(self, methodName, result):
        from twisted.internet import reactor
        timeout = self.getTimeout()
        def onTimeout(d):
            e = defer.TimeoutError("%r (%s) still running at %s secs"
                % (self, methodName, timeout))
            f = failure.Failure(e)
            # try to errback the deferred that the test returns (for no gorram
            # reason) (see issue1005 and test_errorPropagation in
            # test_deferred)
            try:
                d.errback(f)
            except defer.AlreadyCalledError:
                # if the deferred has been called already but the *back chain
                # is still unfinished, crash the reactor and report timeout
                # error ourself.
                reactor.crash()
                self._timedOut = True # see self._wait
                todo = self.getTodo()
                if todo is not None and todo.expected(f):
                    result.addExpectedFailure(self, f, todo)
                else:
                    result.addError(self, f)
        onTimeout = utils.suppressWarnings(
            onTimeout, util.suppress(category=DeprecationWarning))
        method = getattr(self, methodName)
        d = defer.maybeDeferred(utils.runWithWarningsSuppressed,
                                self.getSuppress(), method)
        call = reactor.callLater(timeout, onTimeout, d)
        d.addBoth(lambda x : call.active() and call.cancel() or x)
        return d

    def shortDescription(self):
        desc = super(TestCase, self).shortDescription()
        if desc is None:
            return self._testMethodName
        return desc

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)

    def deferSetUp(self, ignored, result):
        d = self._run('setUp', result)
        d.addCallbacks(self.deferTestMethod, self._ebDeferSetUp,
                       callbackArgs=(result,),
                       errbackArgs=(result,))
        return d

    def _ebDeferSetUp(self, failure, result):
        if failure.check(SkipTest):
            result.addSkip(self, self._getReason(failure))
        else:
            result.addError(self, failure)
            if failure.check(KeyboardInterrupt):
                result.stop()
        return self.deferRunCleanups(None, result)

    def deferTestMethod(self, ignored, result):
        d = self._run(self._testMethodName, result)
        d.addCallbacks(self._cbDeferTestMethod, self._ebDeferTestMethod,
                       callbackArgs=(result,),
                       errbackArgs=(result,))
        d.addBoth(self.deferRunCleanups, result)
        d.addBoth(self.deferTearDown, result)
        return d

    def _cbDeferTestMethod(self, ignored, result):
        if self.getTodo() is not None:
            result.addUnexpectedSuccess(self, self.getTodo())
        else:
            self._passed = True
        return ignored

    def _ebDeferTestMethod(self, f, result):
        todo = self.getTodo()
        if todo is not None and todo.expected(f):
            result.addExpectedFailure(self, f, todo)
        elif f.check(self.failureException, FailTest):
            result.addFailure(self, f)
        elif f.check(KeyboardInterrupt):
            result.addError(self, f)
            result.stop()
        elif f.check(SkipTest):
            result.addSkip(self, self._getReason(f))
        else:
            result.addError(self, f)

    def deferTearDown(self, ignored, result):
        d = self._run('tearDown', result)
        d.addErrback(self._ebDeferTearDown, result)
        return d

    def _ebDeferTearDown(self, failure, result):
        result.addError(self, failure)
        if failure.check(KeyboardInterrupt):
            result.stop()
        self._passed = False

    def deferRunCleanups(self, ignored, result):
        """
        Run any scheduled cleanups and report errors (if any to the result
        object.
        """
        d = self._runCleanups()
        d.addCallback(self._cbDeferRunCleanups, result)
        return d

    def _cbDeferRunCleanups(self, cleanupResults, result):
        for flag, failure in cleanupResults:
            if flag == defer.FAILURE:
                result.addError(self, failure)
                if failure.check(KeyboardInterrupt):
                    result.stop()
                self._passed = False

    def _cleanUp(self, result):
        try:
            clean = util._Janitor(self, result).postCaseCleanup()
            if not clean:
                self._passed = False
        except:
            result.addError(self, failure.Failure())
            self._passed = False
        for error in self._observer.getErrors():
            result.addError(self, error)
            self._passed = False
        self.flushLoggedErrors()
        self._removeObserver()
        if self._passed:
            result.addSuccess(self)

    def _classCleanUp(self, result):
        try:
            util._Janitor(self, result).postClassCleanup()
        except:
            result.addError(self, failure.Failure())

    def _makeReactorMethod(self, name):
        """
        Create a method which wraps the reactor method C{name}. The new
        method issues a deprecation warning and calls the original.
        """
        def _(*a, **kw):
            warnings.warn("reactor.%s cannot be used inside unit tests. "
                          "In the future, using %s will fail the test and may "
                          "crash or hang the test run."
                          % (name, name),
                          stacklevel=2, category=DeprecationWarning)
            return self._reactorMethods[name](*a, **kw)
        return _

    def _deprecateReactor(self, reactor):
        """
        Deprecate C{iterate}, C{crash} and C{stop} on C{reactor}. That is,
        each method is wrapped in a function that issues a deprecation
        warning, then calls the original.

        @param reactor: The Twisted reactor.
        """
        self._reactorMethods = {}
        for name in ['crash', 'iterate', 'stop']:
            self._reactorMethods[name] = getattr(reactor, name)
            setattr(reactor, name, self._makeReactorMethod(name))

    def _undeprecateReactor(self, reactor):
        """
        Restore the deprecated reactor methods. Undoes what
        L{_deprecateReactor} did.

        @param reactor: The Twisted reactor.
        """
        for name, method in self._reactorMethods.iteritems():
            setattr(reactor, name, method)
        self._reactorMethods = {}

    def _installObserver(self):
        self._observer = _logObserver
        self._observer._add()

    def _removeObserver(self):
        self._observer._remove()

    def flushLoggedErrors(self, *errorTypes):
        """
        Remove stored errors received from the log.

        C{TestCase} stores each error logged during the run of the test and
        reports them as errors during the cleanup phase (after C{tearDown}).

        @param *errorTypes: If unspecifed, flush all errors. Otherwise, only
        flush errors that match the given types.

        @return: A list of failures that have been removed.
        """
        return self._observer.flushErrors(*errorTypes)


    def flushWarnings(self, offendingFunctions=None):
        """
        Remove stored warnings from the list of captured warnings and return
        them.

        @param offendingFunctions: If C{None}, all warnings issued during the
            currently running test will be flushed.  Otherwise, only warnings
            which I{point} to a function included in this list will be flushed.
            All warnings include a filename and source line number; if these
            parts of a warning point to a source line which is part of a
            function, then the warning I{points} to that function.
        @type offendingFunctions: L{NoneType} or L{list} of functions or methods.

        @raise ValueError: If C{offendingFunctions} is not C{None} and includes
            an object which is not a L{FunctionType} or L{MethodType} instance.

        @return: A C{list}, each element of which is a C{dict} giving
            information about one warning which was flushed by this call.  The
            keys of each C{dict} are:

                - C{'message'}: The string which was passed as the I{message}
                  parameter to L{warnings.warn}.

                - C{'category'}: The warning subclass which was passed as the
                  I{category} parameter to L{warnings.warn}.

                - C{'filename'}: The name of the file containing the definition
                  of the code object which was C{stacklevel} frames above the
                  call to L{warnings.warn}, where C{stacklevel} is the value of
                  the C{stacklevel} parameter passed to L{warnings.warn}.

                - C{'lineno'}: The source line associated with the active
                  instruction of the code object object which was C{stacklevel}
                  frames above the call to L{warnings.warn}, where
                  C{stacklevel} is the value of the C{stacklevel} parameter
                  passed to L{warnings.warn}.
        """
        if offendingFunctions is None:
            toFlush = self._warnings[:]
            self._warnings[:] = []
        else:
            toFlush = []
            for aWarning in self._warnings:
                for aFunction in offendingFunctions:
                    if not isinstance(aFunction, (
                            types.FunctionType, types.MethodType)):
                        raise ValueError("%r is not a function or method" % (
                                aFunction,))

                    # inspect.getabsfile(aFunction) sometimes returns a
                    # filename which disagrees with the filename the warning
                    # system generates.  This seems to be because a
                    # function's code object doesn't deal with source files
                    # being renamed.  inspect.getabsfile(module) seems
                    # better (or at least agrees with the warning system
                    # more often), and does some normalization for us which
                    # is desirable.  inspect.getmodule() is attractive, but
                    # somewhat broken in Python < 2.6.  See Python bug 4845.
                    aModule = sys.modules[aFunction.__module__]
                    filename = inspect.getabsfile(aModule)

                    if filename != os.path.normcase(aWarning.filename):
                        continue
                    lineStarts = list(_findlinestarts(aFunction.func_code))
                    first = lineStarts[0][1]
                    last = lineStarts[-1][1]
                    if not (first <= aWarning.lineno <= last):
                        continue
                    # The warning points to this function, flush it and move on
                    # to the next warning.
                    toFlush.append(aWarning)
                    break
            # Remove everything which is being flushed.
            map(self._warnings.remove, toFlush)

        return [
            {'message': w.message, 'category': w.category,
             'filename': w.filename, 'lineno': w.lineno}
            for w in toFlush]


    def addCleanup(self, f, *args, **kwargs):
        """
        Add the given function to a list of functions to be called after the
        test has run, but before C{tearDown}.

        Functions will be run in reverse order of being added. This helps
        ensure that tear down complements set up.

        The function C{f} may return a Deferred. If so, C{TestCase} will wait
        until the Deferred has fired before proceeding to the next function.
        """
        self._cleanups.append((f, args, kwargs))


    def callDeprecated(self, version, f, *args, **kwargs):
        """
        Call a function that should have been deprecated at a specific version
        and in favor of a specific alternative, and assert that it was thusly
        deprecated.

        @param version: A 2-sequence of (since, replacement), where C{since} is
            a the first L{version<twisted.python.versions.Version>} that C{f}
            should have been deprecated since, and C{replacement} is a suggested
            replacement for the deprecated functionality, as described by
            L{twisted.python.deprecate.deprecated}.  If there is no suggested
            replacement, this parameter may also be simply a
            L{version<twisted.python.versions.Version>} by itself.

        @param f: The deprecated function to call.

        @param args: The arguments to pass to C{f}.

        @param kwargs: The keyword arguments to pass to C{f}.

        @return: Whatever C{f} returns.

        @raise: Whatever C{f} raises.  If any exception is
            raised by C{f}, though, no assertions will be made about emitted
            deprecations.

        @raise FailTest: if no warnings were emitted by C{f}, or if the
            L{DeprecationWarning} emitted did not produce the canonical
            please-use-something-else message that is standard for Twisted
            deprecations according to the given version and replacement.
        """
        result = f(*args, **kwargs)
        warningsShown = self.flushWarnings([self.callDeprecated])
        try:
            info = list(version)
        except TypeError:
            since = version
            replacement = None
        else:
            [since, replacement] = info

        if len(warningsShown) == 0:
            self.fail('%r is not deprecated.' % (f,))

        observedWarning = warningsShown[0]['message']
        expectedWarning = getDeprecationWarningString(
            f, since, replacement=replacement)
        self.assertEqual(expectedWarning, observedWarning)

        return result


    def _runCleanups(self):
        """
        Run the cleanups added with L{addCleanup} in order.

        @return: A C{Deferred} that fires when all cleanups are run.
        """
        def _makeFunction(f, args, kwargs):
            return lambda: f(*args, **kwargs)
        callables = []
        while len(self._cleanups) > 0:
            f, args, kwargs = self._cleanups.pop()
            callables.append(_makeFunction(f, args, kwargs))
        return util._runSequentially(callables)


    def patch(self, obj, attribute, value):
        """
        Monkey patch an object for the duration of the test.

        The monkey patch will be reverted at the end of the test using the
        L{addCleanup} mechanism.

        The L{MonkeyPatcher} is returned so that users can restore and
        re-apply the monkey patch within their tests.

        @param obj: The object to monkey patch.
        @param attribute: The name of the attribute to change.
        @param value: The value to set the attribute to.
        @return: A L{monkey.MonkeyPatcher} object.
        """
        monkeyPatch = monkey.MonkeyPatcher((obj, attribute, value))
        monkeyPatch.patch()
        self.addCleanup(monkeyPatch.restore)
        return monkeyPatch


    def runTest(self):
        """
        If no C{methodName} argument is passed to the constructor, L{run} will
        treat this method as the thing with the actual test inside.
        """


    def run(self, result):
        """
        Run the test case, storing the results in C{result}.

        First runs C{setUp} on self, then runs the test method (defined in the
        constructor), then runs C{tearDown}. Any of these may return
        L{Deferred}s. After they complete, does some reactor cleanup.

        @param result: A L{TestResult} object.
        """
        log.msg("--> %s <--" % (self.id()))
        from twisted.internet import reactor
        new_result = itrial.IReporter(result, None)
        if new_result is None:
            result = PyUnitResultAdapter(result)
        else:
            result = new_result
        self._timedOut = False
        result.startTest(self)
        if self.getSkip(): # don't run test methods that are marked as .skip
            result.addSkip(self, self.getSkip())
            result.stopTest(self)
            return
        self._installObserver()

        # All the code inside runThunk will be run such that warnings emitted
        # by it will be collected and retrievable by flushWarnings.
        def runThunk():
            self._passed = False
            self._deprecateReactor(reactor)
            try:
                d = self.deferSetUp(None, result)
                try:
                    self._wait(d)
                finally:
                    self._cleanUp(result)
                    self._classCleanUp(result)
            finally:
                self._undeprecateReactor(reactor)

        self._warnings = []
        _collectWarnings(self._warnings.append, runThunk)

        # Any collected warnings which the test method didn't flush get
        # re-emitted so they'll be logged or show up on stdout or whatever.
        for w in self.flushWarnings():
            try:
                warnings.warn_explicit(**w)
            except:
                result.addError(self, failure.Failure())

        result.stopTest(self)


    def _getReason(self, f):
        if len(f.value.args) > 0:
            reason = f.value.args[0]
        else:
            warnings.warn(("Do not raise unittest.SkipTest with no "
                           "arguments! Give a reason for skipping tests!"),
                          stacklevel=2)
            reason = f
        return reason

    def getSkip(self):
        """
        Return the skip reason set on this test, if any is set. Checks on the
        instance first, then the class, then the module, then packages. As
        soon as it finds something with a C{skip} attribute, returns that.
        Returns C{None} if it cannot find anything. See L{TestCase} docstring
        for more details.
        """
        return util.acquireAttribute(self._parents, 'skip', None)

    def getTodo(self):
        """
        Return a L{Todo} object if the test is marked todo. Checks on the
        instance first, then the class, then the module, then packages. As
        soon as it finds something with a C{todo} attribute, returns that.
        Returns C{None} if it cannot find anything. See L{TestCase} docstring
        for more details.
        """
        todo = util.acquireAttribute(self._parents, 'todo', None)
        if todo is None:
            return None
        return makeTodo(todo)

    def getTimeout(self):
        """
        Returns the timeout value set on this test. Checks on the instance
        first, then the class, then the module, then packages. As soon as it
        finds something with a C{timeout} attribute, returns that. Returns
        L{util.DEFAULT_TIMEOUT_DURATION} if it cannot find anything. See
        L{TestCase} docstring for more details.
        """
        timeout =  util.acquireAttribute(self._parents, 'timeout',
                                         util.DEFAULT_TIMEOUT_DURATION)
        try:
            return float(timeout)
        except (ValueError, TypeError):
            # XXX -- this is here because sometimes people will have methods
            # called 'timeout', or set timeout to 'orange', or something
            # Particularly, test_news.NewsTestCase and ReactorCoreTestCase
            # both do this.
            warnings.warn("'timeout' attribute needs to be a number.",
                          category=DeprecationWarning)
            return util.DEFAULT_TIMEOUT_DURATION

    def getSuppress(self):
        """
        Returns any warning suppressions set for this test. Checks on the
        instance first, then the class, then the module, then packages. As
        soon as it finds something with a C{suppress} attribute, returns that.
        Returns any empty list (i.e. suppress no warnings) if it cannot find
        anything. See L{TestCase} docstring for more details.
        """
        return util.acquireAttribute(self._parents, 'suppress', [])


    def visit(self, visitor):
        """
        Visit this test case. Call C{visitor} with C{self} as a parameter.

        Deprecated in Twisted 8.0.

        @param visitor: A callable which expects a single parameter: a test
        case.

        @return: None
        """
        warnings.warn("Test visitors deprecated in Twisted 8.0",
                      category=DeprecationWarning)
        visitor(self)


    def mktemp(self):
        """Returns a unique name that may be used as either a temporary
        directory or filename.

        @note: you must call os.mkdir on the value returned from this
               method if you wish to use it as a directory!
        """
        MAX_FILENAME = 32 # some platforms limit lengths of filenames
        base = os.path.join(self.__class__.__module__[:MAX_FILENAME],
                            self.__class__.__name__[:MAX_FILENAME],
                            self._testMethodName[:MAX_FILENAME])
        if not os.path.exists(base):
            os.makedirs(base)
        dirname = tempfile.mkdtemp('', '', base)
        return os.path.join(dirname, 'temp')

    def _wait(self, d, running=_wait_is_running):
        """Take a Deferred that only ever callbacks. Block until it happens.
        """
        from twisted.internet import reactor
        if running:
            raise RuntimeError("_wait is not reentrant")

        results = []
        def append(any):
            if results is not None:
                results.append(any)
        def crash(ign):
            if results is not None:
                reactor.crash()
        crash = utils.suppressWarnings(
            crash, util.suppress(message=r'reactor\.crash cannot be used.*',
                                 category=DeprecationWarning))
        def stop():
            reactor.crash()
        stop = utils.suppressWarnings(
            stop, util.suppress(message=r'reactor\.crash cannot be used.*',
                                category=DeprecationWarning))

        running.append(None)
        try:
            d.addBoth(append)
            if results:
                # d might have already been fired, in which case append is
                # called synchronously. Avoid any reactor stuff.
                return
            d.addBoth(crash)
            reactor.stop = stop
            try:
                reactor.run()
            finally:
                del reactor.stop

            # If the reactor was crashed elsewhere due to a timeout, hopefully
            # that crasher also reported an error. Just return.
            # _timedOut is most likely to be set when d has fired but hasn't
            # completed its callback chain (see self._run)
            if results or self._timedOut: #defined in run() and _run()
                return

            # If the timeout didn't happen, and we didn't get a result or
            # a failure, then the user probably aborted the test, so let's
            # just raise KeyboardInterrupt.

            # FIXME: imagine this:
            # web/test/test_webclient.py:
            # exc = self.assertRaises(error.Error, wait, method(url))
            #
            # wait() will raise KeyboardInterrupt, and assertRaises will
            # swallow it. Therefore, wait() raising KeyboardInterrupt is
            # insufficient to stop trial. A suggested solution is to have
            # this code set a "stop trial" flag, or otherwise notify trial
            # that it should really try to stop as soon as possible.
            raise KeyboardInterrupt()
        finally:
            results = None
            running.pop()


class UnsupportedTrialFeature(Exception):
    """A feature of twisted.trial was used that pyunit cannot support."""



class PyUnitResultAdapter(object):
    """
    Wrap a C{TestResult} from the standard library's C{unittest} so that it
    supports the extended result types from Trial, and also supports
    L{twisted.python.failure.Failure}s being passed to L{addError} and
    L{addFailure}.
    """

    def __init__(self, original):
        """
        @param original: A C{TestResult} instance from C{unittest}.
        """
        self.original = original

    def _exc_info(self, err):
        return util.excInfoOrFailureToExcInfo(err)

    def startTest(self, method):
        self.original.startTest(method)

    def stopTest(self, method):
        self.original.stopTest(method)

    def addFailure(self, test, fail):
        self.original.addFailure(test, self._exc_info(fail))

    def addError(self, test, error):
        self.original.addError(test, self._exc_info(error))

    def _unsupported(self, test, feature, info):
        self.original.addFailure(
            test,
            (UnsupportedTrialFeature,
             UnsupportedTrialFeature(feature, info),
             None))

    def addSkip(self, test, reason):
        """
        Report the skip as a failure.
        """
        self._unsupported(test, 'skip', reason)

    def addUnexpectedSuccess(self, test, todo):
        """
        Report the unexpected success as a failure.
        """
        self._unsupported(test, 'unexpected success', todo)

    def addExpectedFailure(self, test, error):
        """
        Report the expected failure (i.e. todo) as a failure.
        """
        self._unsupported(test, 'expected failure', error)

    def addSuccess(self, test):
        self.original.addSuccess(test)

    def upDownError(self, method, error, warn, printStatus):
        pass



def suiteVisit(suite, visitor):
    """
    Visit each test in C{suite} with C{visitor}.

    Deprecated in Twisted 8.0.

    @param visitor: A callable which takes a single argument, the L{TestCase}
    instance to visit.
    @return: None
    """
    warnings.warn("Test visitors deprecated in Twisted 8.0",
                  category=DeprecationWarning)
    for case in suite._tests:
        visit = getattr(case, 'visit', None)
        if visit is not None:
            visit(visitor)
        elif isinstance(case, pyunit.TestCase):
            case = itrial.ITestCase(case)
            case.visit(visitor)
        elif isinstance(case, pyunit.TestSuite):
            suiteVisit(case, visitor)
        else:
            case.visit(visitor)



class TestSuite(pyunit.TestSuite):
    """
    Extend the standard library's C{TestSuite} with support for the visitor
    pattern and a consistently overrideable C{run} method.
    """

    visit = suiteVisit

    def __call__(self, result):
        return self.run(result)


    def run(self, result):
        """
        Call C{run} on every member of the suite.
        """
        # we implement this because Python 2.3 unittest defines this code
        # in __call__, whereas 2.4 defines the code in run.
        for test in self._tests:
            if result.shouldStop:
                break
            test(result)
        return result



class TestDecorator(components.proxyForInterface(itrial.ITestCase,
                                                 "_originalTest")):
    """
    Decorator for test cases.

    @param _originalTest: The wrapped instance of test.
    @type _originalTest: A provider of L{itrial.ITestCase}
    """

    implements(itrial.ITestCase)


    def __call__(self, result):
        """
        Run the unit test.

        @param result: A TestResult object.
        """
        return self.run(result)


    def run(self, result):
        """
        Run the unit test.

        @param result: A TestResult object.
        """
        return self._originalTest.run(
            reporter._AdaptedReporter(result, self.__class__))



def _clearSuite(suite):
    """
    Clear all tests from C{suite}.

    This messes with the internals of C{suite}. In particular, it assumes that
    the suite keeps all of its tests in a list in an instance variable called
    C{_tests}.
    """
    suite._tests = []


def decorate(test, decorator):
    """
    Decorate all test cases in C{test} with C{decorator}.

    C{test} can be a test case or a test suite. If it is a test suite, then the
    structure of the suite is preserved.

    L{decorate} tries to preserve the class of the test suites it finds, but
    assumes the presence of the C{_tests} attribute on the suite.

    @param test: The C{TestCase} or C{TestSuite} to decorate.

    @param decorator: A unary callable used to decorate C{TestCase}s.

    @return: A decorated C{TestCase} or a C{TestSuite} containing decorated
        C{TestCase}s.
    """

    try:
        tests = iter(test)
    except TypeError:
        return decorator(test)

    # At this point, we know that 'test' is a test suite.
    _clearSuite(test)

    for case in tests:
        test.addTest(decorate(case, decorator))
    return test



class _PyUnitTestCaseAdapter(TestDecorator):
    """
    Adapt from pyunit.TestCase to ITestCase.
    """


    def visit(self, visitor):
        """
        Deprecated in Twisted 8.0.
        """
        warnings.warn("Test visitors deprecated in Twisted 8.0",
                      category=DeprecationWarning)
        visitor(self)



class _BrokenIDTestCaseAdapter(_PyUnitTestCaseAdapter):
    """
    Adapter for pyunit-style C{TestCase} subclasses that have undesirable id()
    methods. That is L{pyunit.FunctionTestCase} and L{pyunit.DocTestCase}.
    """

    def id(self):
        """
        Return the fully-qualified Python name of the doctest.
        """
        testID = self._originalTest.shortDescription()
        if testID is not None:
            return testID
        return self._originalTest.id()



class _ForceGarbageCollectionDecorator(TestDecorator):
    """
    Forces garbage collection to be run before and after the test. Any errors
    logged during the post-test collection are added to the test result as
    errors.
    """

    def run(self, result):
        gc.collect()
        TestDecorator.run(self, result)
        _logObserver._add()
        gc.collect()
        for error in _logObserver.getErrors():
            result.addError(self, error)
        _logObserver.flushErrors()
        _logObserver._remove()


components.registerAdapter(
    _PyUnitTestCaseAdapter, pyunit.TestCase, itrial.ITestCase)


components.registerAdapter(
    _BrokenIDTestCaseAdapter, pyunit.FunctionTestCase, itrial.ITestCase)


_docTestCase = getattr(doctest, 'DocTestCase', None)
if _docTestCase:
    components.registerAdapter(
        _BrokenIDTestCaseAdapter, _docTestCase, itrial.ITestCase)


def _iterateTests(testSuiteOrCase):
    """
    Iterate through all of the test cases in C{testSuiteOrCase}.
    """
    try:
        suite = iter(testSuiteOrCase)
    except TypeError:
        yield testSuiteOrCase
    else:
        for test in suite:
            for subtest in _iterateTests(test):
                yield subtest



# Support for Python 2.3
try:
    iter(pyunit.TestSuite())
except TypeError:
    # Python 2.3's TestSuite doesn't support iteration. Let's monkey patch it!
    def __iter__(self):
        return iter(self._tests)
    pyunit.TestSuite.__iter__ = __iter__



class _SubTestCase(TestCase):
    def __init__(self):
        TestCase.__init__(self, 'run')

_inst = _SubTestCase()

def _deprecate(name):
    """
    Internal method used to deprecate top-level assertions. Do not use this.
    """
    def _(*args, **kwargs):
        warnings.warn("unittest.%s is deprecated.  Instead use the %r "
                      "method on unittest.TestCase" % (name, name),
                      stacklevel=2, category=DeprecationWarning)
        return getattr(_inst, name)(*args, **kwargs)
    return _


_assertions = ['fail', 'failUnlessEqual', 'failIfEqual', 'failIfEquals',
               'failUnless', 'failUnlessIdentical', 'failUnlessIn',
               'failIfIdentical', 'failIfIn', 'failIf',
               'failUnlessAlmostEqual', 'failIfAlmostEqual',
               'failUnlessRaises', 'assertApproximates',
               'assertFailure', 'failUnlessSubstring', 'failIfSubstring',
               'assertAlmostEqual', 'assertAlmostEquals',
               'assertNotAlmostEqual', 'assertNotAlmostEquals', 'assertEqual',
               'assertEquals', 'assertNotEqual', 'assertNotEquals',
               'assertRaises', 'assert_', 'assertIdentical',
               'assertNotIdentical', 'assertIn', 'assertNotIn',
               'failUnlessFailure', 'assertSubstring', 'assertNotSubstring']


for methodName in _assertions:
    globals()[methodName] = _deprecate(methodName)


__all__ = ['TestCase', 'FailTest', 'SkipTest']
