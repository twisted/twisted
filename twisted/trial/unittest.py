# -*- test-case-name: twisted.trial.test.test_trial -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


import os, errno, warnings, sys

from twisted.python import failure
from twisted.trial import itrial

from twisted.trial.util import deferredResult, deferredError, wait
pyunit = __import__('unittest')

import zope.interface as zi

zi.classImplements(pyunit.TestCase, itrial.ITestCase)

#------------------------------------------------------------------------------
# Set this to True if you want to disambiguate between test failures and
# other assertions.  If you are in the habit of using the "assert" statement
# in your tests, you probably want to leave this false.

ASSERTION_IS_ERROR = 0
if not ASSERTION_IS_ERROR:
    FAILING_EXCEPTION = AssertionError
else:
    FAILING_EXCEPTION = FailTest

# ------------------------------------------------------------- #


class SkipTest(Exception):
    """
    Raise this (with a reason) to skip the current test. You may also set
    method.skip to a reason string to skip it, or set class.skip to skip the
    entire TestCase.
    """


class FailTest(AssertionError):
    """Raised to indicate the current test has failed to pass."""


class TestCase(object):
    zi.implements(itrial.ITestCase)

    def __init__(self, methodName=None):
        pass
            
    def setUpClass(self):
        pass

    def tearDownClass(self):
        pass
    
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def countTestCases(self):
        return 1

    def fail(self, msg=None):
        """absolutely fails the test, do not pass go, do not collect $200

        @param msg: the message that will be displayed as the reason for the
        failure
        """
        raise FailTest, msg

    def failIf(self, condition, msg=None):
        """fails the test if C{condition} evaluates to False

        @param condition: any object that defines __nonzero__
        """
        if condition:
            raise FailTest, msg
        return condition
    assertNot = failIf

    def failUnless(self, condition, msg=None):
        """fails the test if C{condition} evaluates to True
        
        @param condition: any object that defines __nonzero__
        """
        if not condition:
            raise FailTest, msg
        return condition
    assert_ = failUnless

    def failUnlessRaises(self, exception, f, *args, **kwargs):
        """fails the test unless calling the function C{f} with the given C{args}
        and C{kwargs} does not raise C{exception}. The failure will report the
        traceback and call stack of the unexpected exception.
        
        @param exception: exception type that is to be expected
        @param f: the function to call
    
        @return: The raised exception instance, if it is of the given type.
        @raise FailTest: Raised if the function call does not raise an exception
        or if it raises an exception of a different type.
        """
        try:
            result = f(*args, **kwargs)
        except exception, inst:
            return inst
        except:
            raise FailTest, '%s raised instead of %s:\n %s' % \
                  (sys.exc_info()[0], exception.__name__,
                   failure.Failure().getTraceback())
        else:
            raise FailTest('%s not raised (%r returned)'
                           % (exception.__name__, result))
    assertRaises = failUnlessRaises

    def failUnlessEqual(self, first, second, msg=None):
        """fail the test if C{first} and C{second} are not equal
        @param msg: if msg is None, then the failure message will be '%r != %r'
        % (first, second)
        """
        if not first == second:
            raise FailTest, (msg or '%r != %r' % (first, second))
        return first
    assertEqual = assertEquals = failUnlessEqual

    def failUnlessIdentical(self, first, second, msg=None):
        """fail the test if C{first} is not C{second}. This is an
        obect-identity-equality test, not an object equality (i.e. C{__eq__}) test
        
        @param msg: if msg is None, then the failure message will be
        '%r is not %r' % (first, second)
        """
        if first is not second:
            raise FailTest, (msg or '%r is not %r' % (first, second))
        return first
    assertIdentical = failUnlessIdentical

    def failIfIdentical(self, first, second, msg=None):
        """fail the test if C{first} is C{second}. This is an
        obect-identity-equality test, not an object equality (i.e. C{__eq__}) test
        
        @param msg: if msg is None, then the failure message will be
        '%r is %r' % (first, second)
        """
        if first is second:
            raise FailTest, (msg or '%r is %r' % (first, second))
        return first
    assertNotIdentical = failIfIdentical

    def failIfEqual(self, first, second, msg=None):
        """fail the test if C{first} == C{second}
        
        @param msg: if msg is None, then the failure message will be
        '%r == %r' % (first, second)
        """
        if not first != second:
            raise FailTest, (msg or '%r == %r' % (first, second))
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
            raise FailTest, (msg or "%r not in %r" % (containee, container))
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
            raise FailTest, (msg or "%r in %r" % (containee, container))
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
            raise FailTest, (msg or '%r == %r within %r places' %
                                                 (first, second, places))
    assertNotAlmostEqual = assertNotAlmostEquals = failIfAlmostEqual
    
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
            raise FailTest, (msg or '%r != %r within %r places' %
                                                 (first, second, places))
    assertAlmostEqual = assertAlmostEquals = failUnlessAlmostEqual

    def failUnlessApproximates(self, first, second, tolerance, msg=None):
        """asserts that C{first} - C{second} > C{tolerance}

        @param msg: if msg is None, then the failure message will be
                    '%r ~== %r' % (first, second)
        """
        if abs(first - second) > tolerance:
            raise FailTest, (msg or "%s ~== %s" % (first, second))
        return first
    assertApproximates = failUnlessApproximates

    def failUnlessFailure(self, deferred, *expectedFailures):
        """assert that deferred will errback a failure of type in expectedFailures
        this is analagous to an async assertRaises 
        """
        def _cb(ignore):
            raise FailTest, "did not catch an error, instead got %r" % (ignore,)

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
            raise FailTest, (msg or "%r not found in %r" % (substring, astring))
    assertSubstring = failUnlessSubstring

    def failIfSubstring(self, substring, astring, msg=None):
        """a python2.2 friendly test to assert that substring is not found in
        astring parameters follow the semantics of failUnlessIn
        """
        if astring.find(substring) != -1:
            raise FailTest, (msg or "%r found in %r" % (substring, astring))
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
                            getattr(self, '_trial_caseMethodName', 'class')[:32])
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


_inst = TestCase()

def deprecate(name):
    def _(*args, **kwargs):
        warnings.warn("unittest.%s is deprecated.  Instead use the %r "
                      "method on unittest.TestCase" % (name, name),
                      stacklevel=2)
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
    'TestCase', 'deferredResult', 'deferredError', 'wait', 'TestResult'
    ]

