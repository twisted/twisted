# -*- test-case-name: twisted.test.test_trial -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#

"""
Twisted Test Framework v2.0::

   'So you think you are strong because you can survive the
   soft cushions. Well, we shall see. Biggles! Put her in
   the Comfy Chair!'

Author/Maintainer: Jonathan D. Simms U{slyphon@twistedmatrix.com<mailto:slyphon@twistedmatrix.com>}

Original Author: Jonathan 'jml' Lange <jml@twistedmatrix.com>

changes in trial v2.0:
======================
  B{Trial now understands deferreds!}
  -----------------------------------
    - There is no reason to use L{twisted.trial.util.wait} or
      L{twisted.trial.util.deferredResult}. Write your deferred handling code
      as you normally would, make your assertions in your callbacks and
      errbacks, then I{return the deferred from your test method}. Trial will
      spin the reactor (correctly) and will wait for the results before
      running the next test. This will allow developers to write more
      natural-looking tests for their asynchronous code.
    - there is a new attribute that has been introduced, C{.timeout}. Trial
      will wait a default 4 seconds for a result from a deferred that is
      returned from a test method. If you wish to make this value smaller or
      larger:

          >>> from twisted.trial.unittest import TestCase
          >>> from twisted.internet import defer
          >>> class MyTestCase(TestCase):
          ...     def testThatReturnsADeferred(self):
          ...         return defer.success('Hooray!')
          ...     testThatReturnsADeferred.timeout = 2.8 
          ... 
          >>> 

      This would cause trial to wait up to 2.8 seconds (quite needlessly in
      this case) for the deferred to either callback or errback

  B{Trial is now 100% compatible with new-style classes and zope interfaces}
  --------------------------------------------------------------------------
    - Some people (the maintainer included), have been bitten in the past by
      trial's mediocre support for new-style classes (classes which inherit
      from object). In v2.0, nearly all of the classes that comprise the
      framework inherit from object, so support is built-in. Whereas before
      the C{TestCase} finding machinery used a test for inheritance from
      L{twisted.trial.unittest.TestCase}, the new mechanism tests that
      L{twisted.trial.interfaces.ITestCaseFactory} is supplied by your class
      B{type}. You can write a custom C{TestCase}, and trial will detect it and
      use it as a class to test, if you do:

          >>> import zope.interface as zi 
          >>> from twisted.trial.interfaces import ITestCaseFactory, ITestCase
          >>> class MyTestCase(object):
          ...     zi.classProvides(ITestCaseFactory)
          ...     zi.implements(ITestCase)
          >>>

      Naturally, the class should actually provide an implementation of
      L{twisted.trial.interfaces.ITestCase}.
    - To avoid any possible conflicts (and to provide component
      de-registration), trial uses it's own private adapter registry, see
      L{twisted.trial.__init__} for details.
    - Trial makes use of zope.interface.Interfaces to allow flexibility and
      adaptation. All objects implement interfaces, and those interfaces are
      centralized and documented in L{twisted.trial.interfaces}.
      

  B{All assert* and fail* methods are now top-level functions of the unittest module}
  -----------------------------------------------------------------------------------
    - Previously they were only available as instance-methods on the
      C{TestCase}. You can now import all of the assert* and fail* variants and
      use them as functions. This will allow you to use this functionality in
      helper classes and functions that aren't part of your C{TestCase} (plus
      less typing ;])
    - Note: these methods are no longer part of the ITestCase API, but are
      provided as a backwards-compatability to classes written to use the
      original C{TestCase} class.
    - Note: these methods now take a B{msg} keyword argument, some of them were
      inconsistent and took 'message' as the kwarg.

  B{I{Real} Reactor cleanup (when using SelectReactor)}
  -----------------------------------------------------
    - This will probably prove to be the most frustrating, and
      enlightening feature of retrial.
    - After each tearDownClass, trial will find all Selectables (open sockets,
      file descriptors) and all timed events and report them as errors. The
      benefits of this are twofold.
        1. The reactor is guaranteed to be clean before each TestCase is run.
           This means that spurious errors caused by tests leaving behind
           timers or open sockets will not occur, and the correct test will
           be blamed for not cleaning up after itself.
        2. You B{will} learn the proper way to clean up after yourself. (The
           author found this very educational ;) )
    - Helpful hint:

      If you find yourself having trouble with tracking down DelayedCalls
      left pending, insert the following into your setUp and tearDown::

          def setUp(self):
              from twisted.internet import base
              base.DelayedCall.debug = True
              # rest of your setUp
              
          def tearDown(self):
              base.DelayedCall.debug = False
              # rest of your tearDown

      This will cause the traceback at the DelayedCall's creation point to
      be printed along with the error.
      

  B{The trial script now accepts a --reporter option}
  ---------------------------------------------------
    - This is to allow for custom reporter classes. If you want to run a
      trial process remotely, and gain access to the output, or if you would
      just like to have your reporting formatted differently, you can supply
      the fully-qualified class name (of a class that implements
      L{twisted.trial.interfaces.IReporter}) to --reporter, and trial will
      report results to your class.
    - The Reporter is now (almost) totally stateless. All stats on the test
      run are held in the TestSuite and are reported as necessary using the
      ITestStats interface. This allows for greatly simplified design in the
      Reporter implementation.
    - The Reporter API has been greatly simplified by changing the method
      signatures so that methods are called with a single object that can
      easily be adapted to provide all information necessary about a given
      test phase.

  B{Reporters are pluggable}
  --------------------------
    - If you have some need for a custom trial reporter, you can now use the
      twisted plugin system for providing your provider to trial and specifying
      command line options for it!

  B{The .todo attribute is more intelligent than ever!}
  -----------------------------------------------------
    - The .todo attribute now takes a tuple of (ExpectedExceptionType, msg)
      or ((EException1, EException2, ...), msg). If the test's errors and or
      failures do not match the type(s) specified in the first tuple element,
      the condition is considered an ERROR, otherwise the test is considered
      an EXPECTED_FAILURE.
    - For backwards compatibility, this attribute still accepts a string, or
      if you set todo = (None, msg), it will have the same effect as the old
      .todo attribute

  B{Compatibility for PyUnit tests}
  ---------------------------------
    - Trial now supports stdlib unittest.TestCase classes transparently. This
      functionality is unstable, and has not been heavily tested.
    - Note: Trial accomplishes this by monkey-patching unittest.TestCase in
      L{twisted.trial.__init__}.
    - Please report any bugs you find with this feature to the twisted-python
      mailing list

  B{Experimental support for doctests}
  ------------------------------------
    - The trial script now supports a --doctest=[module] option. The argument
      is a fully-qualified module name, and trial will use a modified version
      of DocTestSuite to run the doctests it finds.
    - My support for doctests is broken when using Python 2.4-alpha3,
      hopefully, i'll get this fixed by the time the first major-release
      comes out.
    - Note: you cannot use C{.skip} or C{.todo} attributes with doctests, all tests
      will be reported as pass/fail
    - Please report any bugs you find with this feature to the twisted-python
      mailing list

  B{expectedAssertions} is no longer supported
  --------------------------------------------
    - it was just too difficult to make radix's clever deferred-doublecheck
      feature work with this code revision. With his permisison, this feature
      has been removed.

  

Trial's 'special' attributes:
=============================

  1. C{.todo} attributes can either be set on the C{TestCase} or on an individual
     test* method, and indicate that the test is expected to fail. New tests
     (for which the underlying functionality has not yet been added) should
     set this flag while the code is being written. Once the feature is added
     and the test starts to pass, the flag should be removed.

  2. Tests of highly-unstable in-development code should consider using C{.skip}
     to turn off the tests until the code has reached a point where the
     success rate is expected to be monotonically increasing.

  3. Tests that return deferreds may alter the default timeout period of 4.0
     seconds by adding a method attribute C{.timeout} which is the number of
     seconds as a float that trial should wait for a result.


Non-obvious rules
=================

  There are side-effects of the change in implementation of trial's internals.
  Some of the tricks you may have come to rely on will not work anymore, and
  you'll have to use slightly different tricks to gain the same effect. In the
  same respect, there are some new features that may not work quite the way you
  expect, and we'll try to document potential gotchas here.

    1. Setting a classes C{.skip} attribute in C{setUpClass} will not cause all of that
       C{TestCase}'s methods to be skipped. To get this behavior, you must instead raise
       unittest.SkipTest with the reason for the skip. The C{.skip} attribute is only
       considered once, when the class is first imported, before C{setUpClass} is run.
       Also, if you raise SkipTest in C{setUpClass}, the C{tearDownClass} method B{will}
       still be run (just be aware of this fact).
  
    2. If a method is C{.skip}-ed, it's C{setUp} and C{tearDown} methods will never be
       called.
  
    3. Setting the C{.skip} attribute on a C{TestCase} is equivalent to setting each of
       that class' methods C{.skip} attribute to the value assigned the class' C{.skip}.
       The same holds true for the C{.todo} or C{.timeout} attribute.
  
       example::
  
           # this
           
           class Foo(unittest.TestCase):
               def test_one(self):
                   print 'I test one'
               def test_two(self):
                   print 'I test two'
           Foo.skip = 'this is a silly test'
  
           # is the same as doing
  
           class Foo(unittest.TestCase):
               def test_one(self):
                   print 'I test one'
               test_one.skip = 'this is a silly test'
  
               def test_two(self):
                   print 'I test two'
               test_two.skip = 'this is a silly test'
  
    4. Any method may override the reason for a skip or todo by setting it's own
       attribute value, in other words, the class attribute is a default value for the
       method attribute.
  
    5. If C{setUp} runs without error, C{tearDown} is guaranteed to run, however, if C{setUp}
       raises an exception (including C{SkipTest}), C{tearDown} will B{not} be run.
 
    6. The code that decides whether or not a given object is a C{TestCase} or not works
       by calling ITestCaseFactory.providedBy(obj). Any class that subclasses
       L{twisted.trial.unittest.TestCase} automatically provides this interface so in
       99% of cases, you won't have to think about this.
  
       HOWEVER...
  
       If you are trying to do something particularly spectacular, just note that if you
       want an object that doesn't subclass unittest.TestCase in some way to be considered
       a testable object, its B{class} definition must do::
  
           >>> from twisted.trial.itrial import ITestCaseFactory
           >>> import zope.interface as zi
           >>> class MyLeetTestCase:
           ...     zi.classProvides(ITestCaseFactory)
           >>>
           >>> # or you can do
           >>>
           >>> class MyOtherLeetTestCase:
           ...     pass
           >>>
           >>> zi.directlyProvides(ITestCaseFactory, MyOtherLeetTestCase)
           
       This is being addressed here because of a concern raised by exarkun::
  
           # XXX It is important to be careful when choosing between
           #     if IFace.providedBy(testCase): # ... use testCase
           # and
           #     face = IFace(testCase, default=None)
           #     if face is not None: # ... use face
           #
           # the latter is almost always preferred.  Unless there is
           # a specific reason to restrict adapters here, it should
           # probably be used.
  
       The reason that the implementation does not follow the above advice is that there
       is a bug in either zope.interface or twisted.python.components that causes an
       infinite recursion when one attempts to adapt an t.p.c.interface using a zi
       interfaces' __call__ method.
  
    7. A known issue is that sometimes if you press C-c during a test run, trial will
       not exit. This usually caused by using reactor threads. The only sure-fire way to
       stop trial in this case is to instead try C-\ which sends a SIGQUIT to the running
       process.


Other Notes
===========

The documentation for most of the classes can be found in L{twisted.trial.interfaces}.

"""

# system imports
import sys, os, glob, types, errno, warnings

from twisted.python import reflect, log, failure, components
from twisted.internet import defer
import twisted.python.util

from twisted.trial.util import deferredResult, deferredError
from twisted.trial import util, itrial

import zope.interface as zi


# -----------------------------------------------------------------

class SkipTest(Exception):
    """Raise this (with a reason) to skip the current test. You may also set
    method.skip to a reason string to skip it, or set class.skip to skip the
    entire TestCase."""

class FailTest(AssertionError):
    """Raised to indicate the current test has failed to pass."""

#------------------------------------------------------------------------------
# DO NOT RELY ON THIS! IT IS DEPRECATED AND WILL BE REMOVED IN FUTURE RELEASES!
#
# Set this to True if you want to disambiguate between test failures and
# other assertions.  If you are in the habit of using the "assert" statement
# in your tests, you probably want to leave this false.

ASSERTION_IS_ERROR = 0
if not ASSERTION_IS_ERROR:
    FAILING_EXCEPTION = AssertionError
else:
    FAILING_EXCEPTION = FailTest

#------------------------------------------------------------------------------

def fail(msg=None):
    """absolutely fails the test, do not pass go, do not collect $200

    @param msg: the message that will be displayed as the reason for the failure
    """
    raise FailTest, msg

def failIf(condition, msg=None):
    """fails the test if C{condition} evaluates to False

    @param condition: any object that defines __nonzero__
    """
    if condition:
        raise FailTest, msg
    return condition

def failUnless(condition, msg=None):
    """fails the test if C{condition} evaluates to True

    @param condition: any object that defines __nonzero__
    """
    if not condition:
        raise FailTest, msg
    return condition

def failUnlessRaises(exception, f, *args, **kwargs):
    """fails the test unless calling the function C{f} with the given C{args}
    and C{kwargs} does not raise C{exception}. The failure will report the
    traceback and call stack of the unexpected exception.

    @param exception: exception type that is to be expected
    @param f: the function to call
    """
    try:
        if not twisted.python.util.raises(exception, f, *args, **kwargs):
            raise FailTest, '%s not raised' % exception.__name__
    except FailTest, e:
        raise
    except:
        # import traceback; traceback.print_exc()
        raise FailTest, '%s raised instead of %s:\n %s' % \
              (sys.exc_info()[0], exception.__name__,
               failure.Failure().getTraceback())

def failUnlessEqual(first, second, msg=None):
    """fail the test if C{first} and C{second} are not equal
    @param msg: if msg is None, then the failure message will be '%r != %r'
                % (first, second)
    """
    if not first == second:
        raise FailTest, (msg or '%r != %r' % (first, second))
    return first

def failUnlessIdentical(first, second, msg=None):
    """fail the test if C{first} is not C{second}. This is an
    obect-identity-equality test, not an object equality (i.e. C{__eq__}) test

    @param msg: if msg is None, then the failure message will be
                '%r is not %r' % (first, second)
    """
    if first is not second:
        raise FailTest, (msg or '%r is not %r' % (first, second))
    return first

def failIfIdentical(first, second, msg=None):
    """fail the test if C{first} is C{second}. This is an
    obect-identity-equality test, not an object equality (i.e. C{__eq__}) test

    @param msg: if msg is None, then the failure message will be
                '%r is %r' % (first, second)
    """
    if first is second:
        raise FailTest, (msg or '%r is %r' % (first, second))
    return first

def failIfEqual(first, second, msg=None):
    """fail the test if C{first} == C{second}

    @param msg: if msg is None, then the failure message will be
                '%r == %r' % (first, second)
    """
    if not first != second:
        raise FailTest, (msg or '%r == %r' % (first, second))
    return first

def failUnlessIn(containee, container, msg=None):
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

def failIfIn(containee, container, msg=None):
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


def failIfAlmostEqual(first, second, places=7, msg=None):
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

def failUnlessAlmostEqual(first, second, places=7, msg=None):
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

def assertApproximates(first, second, tolerance, msg=None):
    """asserts that C{first} - C{second} > C{tolerance}

    @param msg: if msg is None, then the failure message will be
                '%r ~== %r' % (first, second)
    """
    if abs(first - second) > tolerance:
        raise FailTest, (msg or "%s ~== %s" % (first, second))
    return first

def assertFailure(deferred, *expectedFailures):
    """assert that deferred will errback a failure of type in expectedFailures
    """
    def _cb(ignore):
        raise FailTest, "did not catch an error, instead got %r" % (ignore,)

    return deferred.addCallbacks(_cb, lambda f: f.trap(*expectedFailures))

# ------------------------------------------------------------- #

class MetaTestCase(type):
    """registers classes that inherit from TestCase as directly providing
    ITestCaseFactory
    """
    def __init__(klass, name, bases, attrs):
        zi.directlyProvides(klass, itrial.ITestCaseFactory)
        return super(MetaTestCase, klass).__init__(klass, name, bases, attrs)
        

class TestCase(object):
    __metaclass__ = MetaTestCase
    zi.implements(itrial.ITestCase)
    
    def setUpClass(self):
        pass

    def tearDownClass(self):
        pass
    
    def setUp(self):
        pass

    def tearDown(self):
        pass

    # backwards compatability parade! ----------------

    fail = lambda self, msg: fail(msg)
    failIf = lambda self, a, msg=None: failIf(a, msg)
    failIfIn = lambda self, a, b, msg=None: failIfIn(a, b, msg)
    failUnless = lambda self, a, msg=None: failUnless(a, msg)
    failIfEqual = lambda self, a, b, msg=None: failIfEqual(a, b, msg)
    failUnlessIn = lambda self, a, b, msg=None: failUnlessIn(a, b, msg)
    failUnlessEqual = lambda self, a, b, msg=None: failUnlessEqual(a, b, msg)
    failIfIdentical = lambda self, a, b, msg=None: failIfIdentical(a, b, msg)
    failUnlessRaises = lambda self, exc, f, *a, **kw: failUnlessRaises(exc, f, *a, **kw)
    failIfAlmostEqual = lambda self, a, b, c=7, msg=None: failIfAlmostEqual(a, b, c, msg)
    assertApproximates = lambda self, a, b, c, msg=None: assertApproximates(a, b, c, msg)
    failUnlessIdentical = lambda self, a, b, msg=None: failUnlessIdentical(a, b, msg)
    failUnlessAlmostEqual = lambda self, a, b, c=7, msg=None: failUnlessAlmostEqual(a, b, c, msg)

    assertAlmostEqual = assertAlmostEquals = failUnlessAlmostEqual
    assertNotAlmostEqual = assertNotAlmostEquals = failIfAlmostEqual
    assertEqual = assertEquals = failUnlessEqual
    assertNotEqual = assertNotEquals = failIfEqual
    assertRaises = failUnlessRaises
    assert_ = failUnless
    failIfEquals = failIfEqual
    assertIdentical = failUnlessIdentical
    assertNotIdentical = failIfIdentical
    assertIn = failUnlessIn
    assertNotIn = failIfIn

    # -----------------------------------------------

    # Utility method for creating temporary names
    def mktemp(self):
        """will return a unique name that may be used as either a temporary
        directory or filename
        @note: you must call os.mkdir on the value returned from this
               method if you wish to use it as a directory!
        """
        cls = self.__class__
        base = os.path.join(cls.__module__, cls.__name__,
                            getattr(self, 'caseMethodName', 'class'))
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
        trial with just do the Right Thing.
        
        I'll iterate the reactor for a while.
        
        You probably want to use expectedAssertions with this.
        
        @type timesOrSeconds: int
        @param timesOrSeconds: Either the number of iterations to run,
               or, if `seconds' is True, the number of seconds to run for.

        @type seconds: bool
        @param seconds: If this is True, `timesOrSeconds' will be
               interpreted as seconds, rather than iterations.
        """
        warnings.warn("runReactor is deprecated. return a deferred from " +
                      "your test method, and trial will wait for results",
                      DeprecationWarning)
        from twisted.internet import reactor

        if seconds:
            reactor.callLater(timesOrSeconds, reactor.crash)
            reactor.run()
            return

        for i in xrange(timesOrSeconds):
            reactor.iterate()


_assertions = ['fail', 'failUnlessEqual', 'failIfEqual', 'failUnless',
               'failUnlessIdentical', 'failUnlessIn',  'failIfIdentical',
               'failIfIn', 'failIf', 'failUnlessAlmostEqual',
               'failIfAlmostEqual']


__all__ = (['TestCase', 'SkipTest', 'FailTest', 'ASSERTION_IS_ERROR']
           + _assertions)

del _assertions
