# -*- test-case-name: twisted.trial.test.test_tests -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Things likely to be used by writers of unit tests.

Maintainer: Jonathan Lange <jml@twistedmatrix.com>
"""


import os, warnings, sys, tempfile, sets, gc

from twisted.internet import defer, utils
from twisted.python import failure, log
from twisted.trial import itrial, util

pyunit = __import__('unittest')

import zope.interface as zi

zi.classImplements(pyunit.TestCase, itrial.ITestCase)


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


class _Assertions(pyunit.TestCase, object):
    """
    Replaces many of the built-in TestCase assertions. In general, these
    assertions provide better error messages and are easier to use in
    callbacks. Also provides new assertions such as L{failUnlessFailure}.

    Although the tests are defined as 'failIf*' and 'failUnless*', they can
    also be called as 'assertNot*' and 'assert*'.
    """

    def fail(self, msg=None):
        """absolutely fails the test, do not pass go, do not collect $200

        @param msg: the message that will be displayed as the reason for the
        failure
        """
        raise self.failureException(msg)

    def failIf(self, condition, msg=None):
        """fails the test if C{condition} evaluates to False

        @param condition: any object that defines __nonzero__
        """
        if condition:
            raise self.failureException(msg)
        return condition
    assertNot = assertFalse = failUnlessFalse = failIf

    def failUnless(self, condition, msg=None):
        """fails the test if C{condition} evaluates to True

        @param condition: any object that defines __nonzero__
        """
        if not condition:
            raise self.failureException(msg)
        return condition
    assert_ = assertTrue = failUnlessTrue = failUnless

    def failUnlessRaises(self, exception, f, *args, **kwargs):
        """fails the test unless calling the function C{f} with the given C{args}
        and C{kwargs} does not raise C{exception}. The failure will report the
        traceback and call stack of the unexpected exception.

        @param exception: exception type that is to be expected
        @param f: the function to call

        @return: The raised exception instance, if it is of the given type.
        @raise self.failureException: Raised if the function call does not raise an exception
        or if it raises an exception of a different type.
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

    def failUnlessEqual(self, first, second, msg=None):
        """fail the test if C{first} and C{second} are not equal
        @param msg: if msg is None, then the failure message will be '%r != %r'
        % (first, second)
        """
        if not first == second:
            raise self.failureException(msg or '%r != %r' % (first, second))
        return first
    assertEqual = assertEquals = failUnlessEquals = failUnlessEqual

    def failUnlessIdentical(self, first, second, msg=None):
        """fail the test if C{first} is not C{second}. This is an
        obect-identity-equality test, not an object equality (i.e. C{__eq__}) test

        @param msg: if msg is None, then the failure message will be
        '%r is not %r' % (first, second)
        """
        if first is not second:
            raise self.failureException(msg or '%r is not %r' % (first, second))
        return first
    assertIdentical = failUnlessIdentical

    def failIfIdentical(self, first, second, msg=None):
        """fail the test if C{first} is C{second}. This is an
        obect-identity-equality test, not an object equality (i.e. C{__eq__}) test

        @param msg: if msg is None, then the failure message will be
        '%r is %r' % (first, second)
        """
        if first is second:
            raise self.failureException(msg or '%r is %r' % (first, second))
        return first
    assertNotIdentical = failIfIdentical

    def failIfEqual(self, first, second, msg=None):
        """fail the test if C{first} == C{second}

        @param msg: if msg is None, then the failure message will be
        '%r == %r' % (first, second)
        """
        if not first != second:
            raise self.failureException(msg or '%r == %r' % (first, second))
        return first
    assertNotEqual = assertNotEquals = failIfEquals = failIfEqual

    def failUnlessIn(self, containee, container, msg=None):
        """fail the test if C{containee} is not found in C{container}

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
        """fail the test if C{containee} is found in C{container}

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
        """Fail if the two objects are equal as determined by their
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
        """Fail if the two objects are unequal as determined by their
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
        """asserts that C{first} - C{second} > C{tolerance}

        @param msg: if msg is None, then the failure message will be
                    '%r ~== %r' % (first, second)
        """
        if abs(first - second) > tolerance:
            raise self.failureException(msg or "%s ~== %s" % (first, second))
        return first
    assertApproximates = failUnlessApproximates

    def failUnlessFailure(self, deferred, *expectedFailures):
        """Assert that C{deferred} will errback with one of
        C{expectedFailures}.  Returns the original Deferred with callbacks
        added. You will need to return this Deferred from your test case.
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
        return self.failUnlessIn(substring, astring, msg)
    assertSubstring = failUnlessSubstring

    def failIfSubstring(self, substring, astring, msg=None):
        return self.failIfIn(substring, astring, msg)
    assertNotSubstring = failIfSubstring


class _LogObserver(object):
    """
    Observes the Twisted logs and catches any errors.
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

    @ivar forceGarbageCollection: If set to True, C{gc.collect()} will be
    called before and after the test. Otherwise, garbage collection will
    happen in whatever way Python sees fit.

    @ivar skip: C{None} or a string explaining why this test is to be
    skipped. If defined, the test will not be run. Instead, it will be
    reported to the result object as 'skipped' (if the C{TestResult} supports
    skipping).

    @ivar suppress: C{None} or a list of tuples of C{(args, kwargs)} to be
    passed to C{warnings.filterwarnings}. Use these to suppress warnings
    raised in a test. Useful for testing deprecated code. See also
    L{util.suppress}.

    @ivar timeout: C{None} or a real number of seconds. If set, the test will
    raise an error if it takes longer than C{timeout} seconds.

    @ivar todo: C{None}, a string or a tuple of C{(errors, reason)} where
    C{errors} is either an exception class or an iterable of exception
    classes, and C{reason} is a string. See L{Todo} or L{makeTodo} for more
    information.
    """

    zi.implements(itrial.ITestCase)
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
        self._shared = (hasattr(self, 'setUpClass') or
                        hasattr(self, 'tearDownClass'))
        if self._shared:
            self._prepareClassFixture()
            if not hasattr(self.__class__, '_instances'):
                self._initInstances()
            self.__class__._instances.add(self)
        self._passed = False
        self.forceGarbageCollection = False

    def _initInstances(cls):
        cls._instances = sets.Set()
        cls._instancesRun = sets.Set()
    _initInstances = classmethod(_initInstances)

    def _isFirst(self):
        return len(self.__class__._instancesRun) == 0

    def _isLast(self):
        return self.__class__._instancesRun == self.__class__._instances

    def _prepareClassFixture(self):
        """Lots of tests assume that test methods all run in the same instance
        of TestCase.  This isn't true. Calling this method ensures that
        self.__class__._testCaseInstance contains an instance of this class
        that will remain the same for all tests from this class.
        """
        if not hasattr(self.__class__, '_testCaseInstance'):
            self.__class__._testCaseInstance = self
        if self.__class__._testCaseInstance.__class__ != self.__class__:
            self.__class__._testCaseInstance = self

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
        if self._shared:
            test = self.__class__._testCaseInstance
        else:
            test = self
        method = getattr(test, methodName)
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

    def deferSetUpClass(self, result):
        if not hasattr(self, 'setUpClass'):
            d = defer.succeed(None)
            d.addCallback(self.deferSetUp, result)
            return d
        d = self._run('setUpClass', result)
        d.addCallbacks(self.deferSetUp, self._ebDeferSetUpClass,
                       callbackArgs=(result,),
                       errbackArgs=(result,))
        return d

    def _ebDeferSetUpClass(self, error, result):
        if error.check(SkipTest):
            result.addSkip(self, self._getReason(error))
            self.__class__._instancesRun.remove(self)
        elif error.check(KeyboardInterrupt):
            result.stop()
        else:
            result.upDownError('setUpClass', error, warn=True,
                               printStatus=True)
            result.addError(self, error)
            self.__class__._instancesRun.remove(self)

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
            result.upDownError('setUp', failure, warn=False, printStatus=False)
            if failure.check(KeyboardInterrupt):
                result.stop()

    def deferTestMethod(self, ignored, result):
        d = self._run(self._testMethodName, result)
        d.addCallbacks(self._cbDeferTestMethod, self._ebDeferTestMethod,
                       callbackArgs=(result,),
                       errbackArgs=(result,))
        d.addBoth(self.deferTearDown, result)
        if self._shared and hasattr(self, 'tearDownClass') and self._isLast():
            d.addBoth(self.deferTearDownClass, result)
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
        result.upDownError('tearDown', failure, warn=False, printStatus=True)
        self._passed = False

    def deferTearDownClass(self, ignored, result):
        d = self._run('tearDownClass', result)
        d.addErrback(self._ebTearDownClass, result)
        return d

    def _ebTearDownClass(self, error, result):
        if error.check(KeyboardInterrupt):
            result.stop()
        result.upDownError('tearDownClass', error, warn=True, printStatus=True)

    def _cleanUp(self, result):
        try:
            if self.forceGarbageCollection:
                gc.collect()
            util._Janitor().postCaseCleanup()
        except util.FailureError, e:
            result.addError(self, e.original)
            self._passed = False
        except:
            result.cleanupErrors(failure.Failure())
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
            util._Janitor().postClassCleanup()
        except util.FailureError, e:
            result.cleanupErrors(e.original)
        except:
            result.cleanupErrors(failure.Failure())

    def _makeReactorMethod(self, name):
        """
        Create a method which wraps the reactor method C{name}. The new
        method issues a deprecation warning and calls the original.
        """
        def _(*a, **kw):
            warnings.warn("reactor.%s cannot be used inside unit tests. By "
                          "Twisted 2.7, using %s will fail the test and may "
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
        from twisted.trial import reporter
        if not isinstance(result, reporter.TestResult):
            result = PyUnitResultAdapter(result)
        self._timedOut = False
        if self._shared and self not in self.__class__._instances:
            self.__class__._instances.add(self)
        result.startTest(self)
        if self.getSkip(): # don't run test methods that are marked as .skip
            result.addSkip(self, self.getSkip())
            result.stopTest(self)
            return
        self._installObserver()
        self._passed = False
        first = False
        if self._shared:
            first = self._isFirst()
            self.__class__._instancesRun.add(self)
        self._deprecateReactor(reactor)
        try:
            if self.forceGarbageCollection:
                gc.collect()
            if first:
                d = self.deferSetUpClass(result)
            else:
                d = self.deferSetUp(None, result)
            try:
                self._wait(d)
            finally:
                self._cleanUp(result)
                result.stopTest(self)
                if self._shared and self._isLast():
                    self._initInstances()
                    self._classCleanUp(result)
                if not self._shared:
                    self._classCleanUp(result)
        finally:
            self._undeprecateReactor(reactor)

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

        @param visitor: A callable which expects a single parameter: a test
        case.

        @return: None
        """
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
        if isinstance(err, failure.Failure):
            # Unwrap the Failure into a exc_info tuple.
            # XXX: if err.tb is a real traceback and not stringified, we should
            #      use that.
            err = (err.type, err.value, None)
        return err

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

    def cleanupErrors(self, errs):
        pass

    def startSuite(self, name):
        pass



class _SubTestCase(TestCase):
    def __init__(self):
        TestCase.__init__(self, 'run')

_inst = _SubTestCase()

def deprecate(name):
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
    globals()[methodName] = deprecate(methodName)


__all__ = ['TestCase', 'wait', 'FailTest', 'SkipTest']

