# -*- test-case-name: twisted.trial.test.test_trial -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


import os, errno, warnings, sys, time

from twisted.internet import defer
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


class TestCase(pyunit.TestCase, object):
    zi.implements(itrial.ITestCase)
    failureException = FailTest

    def __init__(self, methodName=None):
        super(TestCase, self).__init__(methodName)
        self._testMethodName = methodName
        testMethod = getattr(self, methodName)
        self._parents = [testMethod, self]
        self._parents.extend(util.getPythonContainers(testMethod))
        self._prepareClassFixture()
        self._passed = False

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

    def _sharedTestCase(self):
        return self.__class__._testCaseInstance

    def _run(self, methodName):
        from twisted.internet import reactor
        method = getattr(self._sharedTestCase(), methodName)
        d = defer.maybeDeferred(util.suppressedRun, self.getSuppress(), method)
        call = reactor.callLater(self.getTimeout(), defer.timeout, d)
        d.addBoth(lambda x : call.active() and call.cancel() or x)
        return d

    def id(self):
        # only overriding this because Python 2.2's unittest has a broken
        # implementation
        return "%s.%s" % (reflect.qual(self.__class__), self._testMethodName)

    def shortDescription(self):
        desc = super(TestCase, self).shortDescription()
        if desc is None:
            return self._testMethodName
        return desc

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)

    def deferSetUp(self, result):
        d = self._run('setUp')
        d.addCallbacks(self.deferTestMethod, self._ebDeferSetUp,
                       callbackArgs=(result,),
                       errbackArgs=(result,))
        return d

    def _ebDeferSetUp(self, failure, result):
        result.addError(self, failure)
        result.upDownError('setUp', failure, warn=False, printStatus=False)
        if failure.check(KeyboardInterrupt):
            result.stop()

    def deferTestMethod(self, ignored, result):
        testMethod = getattr(self._sharedTestCase(), self._testMethodName)
        d = self._run(self._testMethodName)
        d.addCallbacks(self._cbDeferTestMethod, self._ebDeferTestMethod,
                       callbackArgs=(result,),
                       errbackArgs=(result,))
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
        d = self._run('tearDown')
        d.addErrback(self._ebDeferTearDown, result)
        return d

    def _ebDeferTearDown(self, failure, result):
        result.addError(self, failure)
        if failure.check(KeyboardInterrupt):
            result.stop()
        result.upDownError('tearDown', failure, warn=False, printStatus=True)
        self._passed = False

    def _cleanUp(self, result):
        try:
            util._Janitor().postMethodCleanup()
        except util.FailureError, e:
            result.addError(self, e.original)
            self._passed = False
        except:
            result.cleanupErrors(failure.Failure())
            self._passed = False
        if self._passed:
            result.addSuccess(self)
        
    def run(self, result):
        log.msg("--> %s <--" % (self.id()))
        signalStateMgr = util.SignalStateManager()
        signalStateMgr.save()
        result.startTest(self)
        if self.getSkip(): # don't run test methods that are marked as .skip
            result.addSkip(self, self.getSkip())
            result.stopTest(self)
            return
        self._passed = False
        d = self.deferSetUp(result)
        try:
            util.wait(d, timeout=None)
        finally:
            self._cleanUp(result)
            result.stopTest(self)
            signalStateMgr.restore()

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
        """a python2.2 friendly test to assert that substring is found in astring
        parameters follow the semantics of failUnlessIn
        """
        if astring.find(substring) == -1:
            raise self.failureException(msg or "%r not found in %r"
                                        % (substring, astring))
        return substring
    assertSubstring = failUnlessSubstring

    def failIfSubstring(self, substring, astring, msg=None):
        """a python2.2 friendly test to assert that substring is not found in
        astring parameters follow the semantics of failUnlessIn
        """
        if astring.find(substring) != -1:
            raise self.failureException(msg or "%r found in %r"
                                        % (substring, astring))
        return substring
    assertNotSubstring = failIfSubstring

    def mktemp(self):
        """will return a unique name that may be used as either a temporary
        directory or filename
        @note: you must call os.mkdir on the value returned from this
               method if you wish to use it as a directory!
        """
        # FIXME: when we drop support for python 2.2 and start to require 2.3,
        #        we should ditch most of this cruft and just call
        #        tempfile.mkdtemp.
        cls = self.__class__
        base = os.path.join(cls.__module__, cls.__name__,
                            self._testMethodName[:32])
        try:
            os.makedirs(base)
        except OSError, e:
            code = e[0]
            if code == errno.EEXIST:
                pass
            else:
                raise
        pid = os.getpid()
        while 1:
            num = self._mktGetCounter(base)
            name = os.path.join(base, "%s.%s" % (pid, num))
            if not os.path.exists(name):
                break
        return name

    # mktemp helper to increment a counter
    def _mktGetCounter(self, base):
        if getattr(self, "_mktCounters", None) is None:
            self._mktCounters = {}
        if base not in self._mktCounters:
            self._mktCounters[base] = 2
            return 1
        n = self._mktCounters[base]
        self._mktCounters[base] += 1
        return n

    def runReactor(self, timesOrSeconds, seconds=False):
        """DEPRECATED: just return a deferred from your test method and
        trial with do the Right Thing. Alternatively, call
        twisted.trial.util.wait to block until the deferred fires.
        
        I'll iterate the reactor for a while.
        
        You probably want to use expectedAssertions with this.
        
        @type timesOrSeconds: int
        @param timesOrSeconds: Either the number of iterations to run,
               or, if `seconds' is True, the number of seconds to run for.

        @type seconds: bool
        @param seconds: If this is True, `timesOrSeconds' will be
               interpreted as seconds, rather than iterations.
        """
        warnings.warn("runReactor is deprecated. return a deferred from "
                      "your test method, and trial will wait for results.",
                      DeprecationWarning, stacklevel=2)
        from twisted.internet import reactor

        if seconds:
            reactor.callLater(timesOrSeconds, reactor.crash)
            reactor.run()
            return

        for i in xrange(timesOrSeconds):
            reactor.iterate()


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

