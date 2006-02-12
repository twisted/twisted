# -*- test-case-name: twisted.trial.test.test_tests -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


import os, errno, warnings, sys, time, tempfile, sets

from twisted.internet import defer, utils
from twisted.python import failure, log, reflect
from twisted.trial import itrial, util
from twisted.trial.util import deferredResult, deferredError

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
    def __init__(self, reason, errors=None):
        self.reason = reason
        self.errors = errors

    def __repr__(self):
        return "<Todo reason=%r errors=%r>" % (self.reason, self.errors)

    def expected(self, failure):
        if self.errors is None:
            return True
        for error in self.errors:
            if failure.check(error):
                return True
        return False


def makeTodo(value):
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
        """assert that deferred will errback a failure of type in expectedFailures
        this is analagous to an async assertRaises 
        """
        def _cb(ignore):
            raise self.failureException(
                "did not catch an error, instead got %r" % (ignore,))

        def _eb(failure):
            failure.trap(*expectedFailures)
            return failure.value
        return deferred.addCallbacks(_cb, _eb)
    assertFailure = failUnlessFailure

    def failUnlessSubstring(self, substring, astring, msg=None):
        return self.failUnlessIn(substring, astring, msg)
    assertSubstring = failUnlessSubstring

    def failIfSubstring(self, substring, astring, msg=None):
        return self.failIfIn(substring, astring, msg)
    assertNotSubstring = failIfSubstring


class TestCase(_Assertions):
    zi.implements(itrial.ITestCase)
    failureException = FailTest

    def __init__(self, methodName=None):
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
            # reason) (see issue1005 and test_errorPropagation in test_deferred)
            try:
                d.errback(f)
            except defer.AlreadyCalledError:
                # if the deferred has been called already but the *back chain is
                # still unfinished, crash the reactor and report timeout error
                # ourself.
                reactor.crash()
                self._timedOut = True # see self._wait
                todo = self.getTodo()
                if todo is not None and todo.expected(f):
                    result.addExpectedFailure(self, f, todo)
                else:
                    result.addError(self, f)
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
            util._Janitor().postCaseCleanup()
        except util.FailureError, e:
            result.addError(self, e.original)
            self._passed = False
        except:
            result.cleanupErrors(failure.Failure())
            self._passed = False
        if self._passed:
            result.addSuccess(self)

    def _classCleanUp(self, result):
        try:
            util._Janitor().postClassCleanup()
        except util.FailureError, e:
            result.cleanupErrors(e.original)
        except:
            result.cleanupErrors(failure.Failure())

    def run(self, result):
        log.msg("--> %s <--" % (self.id()))
        self._timedOut = False
        if self._shared and self not in self.__class__._instances:
            self.__class__._instances.add(self)
        result.startTest(self)
        if self.getSkip(): # don't run test methods that are marked as .skip
            result.addSkip(self, self.getSkip())
            result.stopTest(self)
            return
        self._passed = False
        first = False
        if self._shared:
            first = self._isFirst()
            self.__class__._instancesRun.add(self)
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
        return util.acquireAttribute(self._parents, 'skip', None)

    def getTodo(self):
        todo = util.acquireAttribute(self._parents, 'todo', None)
        if todo is None:
            return None
        return makeTodo(todo)

    def getTimeout(self):
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
        return util.acquireAttribute(self._parents, 'suppress', [])
    
    def visit(self, visitor):
        """Call visitor.visitCase(self)."""
        visitor.visitCase(self)

    def mktemp(self):
        """will return a unique name that may be used as either a temporary
        directory or filename
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
    
    def _wait(self, d, running=util._wait_is_running):
        """Take a Deferred that only ever callbacks. Block until it happens.
        """
        from twisted.internet import reactor
        if running:
            raise WaitIsNotReentrantError, REENTRANT_WAIT_ERROR_MSG
    
        results = []
        def append(any):
            if results is not None:
                results.append(any)
        def crash(ign):
            if results is not None:
                reactor.crash()
        def stop():
            reactor.crash()
    
        running.append(None)
        try:
            d.addBoth(append)
            if results:
                # d might have already been fired, in which case append is called 
                # synchronously. Avoid any reactor stuff.
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
            # exc = self.assertRaises(error.Error, unittest.wait, method(url))
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


class TestVisitor(object):
    
    def visitCase(self, testCase):
        """Visit the testCase testCase."""

    def visitSuite(self, testSuite):
        """Visit the TestModuleSuite testModule."""

    def visitSuiteAfter(self, testSuite):
        """Visit the TestModuleSuite testModule after its children."""

    def visitTrial(self, testSuite):
        """Visit the TestSuite testSuite."""

    def visitTrialAfter(self, testSuite):
        """Visit the TestSuite testSuite after its children."""


def wait(*args, **kwargs):
    warnings.warn("Do NOT use wait().  Just return a Deferred",
                  stacklevel=2, category=DeprecationWarning)
    return util.wait(*args, **kwargs)


class _SubTestCase(TestCase):
    def __init__(self):
        TestCase.__init__(self, 'run')
    
_inst = _SubTestCase()

def deprecate(name):
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


__all__ = [
    'TestCase', 'deferredResult', 'deferredError', 'wait', 'TestResult',
    'FailTest', 'SkipTest'
    ]

