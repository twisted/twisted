# -*- test-case-name: twisted.trial.test.test_trial -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


import os, errno, warnings, sys, time

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
        self.startTime = self.endTime = 0 # XXX - this is a kludge

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

    def run(self, reporter):
        log.msg("--> %s <--" % (self.id()))
        _signalStateMgr = util.SignalStateManager()
        _signalStateMgr.save()
        janitor = util._Janitor()
        testCase = self._sharedTestCase()
        testMethod = getattr(testCase, self._testMethodName)

        reporter.startTest(self)
        if self.getSkip(): # don't run test methods that are marked as .skip
            reporter.addSkip(self, self.getSkip())
            reporter.stopTest(self)
            return
        try:
            setUp = util.UserMethodWrapper(testCase.setUp,
                                           suppress=self.getSuppress())
            try:
                setUp()
            except util.UserMethodError:
                for error in setUp.errors:
                    self._eb(error, reporter)
                else:
                    reporter.upDownError(setUp, warn=False,
                                         printStatus=False)
                    return
                 
            orig = util.UserMethodWrapper(testMethod,
                                          raiseOnErr=False,
                                          timeout=self.getTimeout(),
                                          suppress=self.getSuppress())
            orig.errorHook = lambda x : self._eb(x, reporter)
            try:
                self.startTime = time.time()
                orig()
                if (self.getTodo() is not None
                    and len(orig.errors) == 0):
                    reporter.addUnexpectedSuccess(self, self.getTodo())
            finally:
                self.endTime = time.time()
                um = util.UserMethodWrapper(testCase.tearDown,
                                            suppress=self.getSuppress())
                try:
                    um()
                except util.UserMethodError:
                    for error in um.errors:
                        self._eb(error, reporter)
                    else:
                        reporter.upDownError(um, warn=False)
        finally:
            try:
                janitor.postMethodCleanup()
            except util.MultiError, e:
                for f in e.failures:
                    self._eb(f, reporter)
            reporter.stopTest(self)
            _signalStateMgr.restore()

    def _eb(self, f, reporter):
        log.msg(f.getTraceback())
        if self.getTodo() is not None:
            if self._todoExpected(f):
                reporter.addExpectedFailure(self, f, self._getTodoMessage())
                return
        if f.check(util.DirtyReactorWarning):
            reporter.cleanupErrors(f)
        elif f.check(self.failureException, FailTest):
            reporter.addFailure(self, f)
        elif f.check(KeyboardInterrupt):
            reporter.shouldStop = True
            reporter.addError(self, f)
        elif f.check(SkipTest):
            if len(f.value.args) > 0:
                reason = f.value.args[0]
            else:
                warnings.warn(("Do not raise unittest.SkipTest with no "
                               "arguments! Give a reason for skipping tests!"),
                              stacklevel=2)
                reason = f
            self.skip = reason
            reporter.addSkip(self, reason)
        else:
            reporter.addError(self, f)

    def getSkip(self):
        return util.acquireAttribute(self._parents, 'skip', None)

    def getTodo(self):
        return util.acquireAttribute(self._parents, 'todo', None)

    def _todoExpected(self, failure):
        todo = self.getTodo()
        if todo is None:
            return False
        if isinstance(todo, str):
            return True
        elif isinstance(todo, tuple):
            try:
                expected = list(todo[0])
            except TypeError:
                expected = [todo[0]]
            for error in expected:
                if failure.check(error):
                    return True
            return False
        else:
            raise ValueError('%r is not a valid .todo attribute' % (todo,))

    def _getTodoMessage(self):
        todo = self.getTodo()
        if todo is None or isinstance(todo, str):
            return todo
        elif isinstance(todo, tuple):
            return todo[1]
        else:
            raise ValueError("%r is not a valid .todo attribute" % (todo,))
    
    def getSuppress(self):
        return util.acquireAttribute(self._parents, 'suppress', None)

    def getTimeout(self):
        return util.acquireAttribute(self._parents, 'timeout', None)
    
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
                      "your test method, and trial will wait for results."
                      "Alternatively, call twisted.trial.util.wait to"
                      "block until the deferred fires.",
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

    def visitClass(self, testClass):
        """Visit the TestClassSuite testClass."""

    def visitClassAfter(self, testClass):
        """Visit the TestClassSuite testClass after its children."""

    def visitModule(self, testModule):
        """Visit the TestModuleSuite testModule."""

    def visitModuleAfter(self, testModule):
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
        pass

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

