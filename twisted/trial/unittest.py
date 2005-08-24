# -*- test-case-name: twisted.trial.test.test_trial -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#

"""
Twisted Test Framework v2.0::

    The Cadillac of Python Unittesting


Author/Maintainer: Jonathan D. Simms U{slyphon@twistedmatrix.com<mailto:slyphon@twistedmatrix.com>}

Original Author: Jonathan 'jml' Lange <jml@twistedmatrix.com>

changes in trial v2.0:
======================
  B{Trial now understands deferreds!}
  -----------------------------------
    - Write your deferred handling code as you normally would, make your
      assertions in your callbacks and errbacks, then I{return the deferred
      from your test method}. Trial will spin the reactor (correctly) and will
      wait for the results before running the next test. This will allow
      developers to write more natural-looking tests for their asynchronous
      code.

    - There is a new attribute that has been introduced, C{.timeout}. Trial
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

    There are some B{important caveats} to this new functionality:

    - When returning a Deferred from a setUp, tearDown, or test
      method to trial, it is important to note that there may be some
      restrictions placed on the callbacks which may appear on this Deferred.
      Specifically, depending on the implementation of API which created them,
      they may not be allowed to invoke deferredResult, deferredError, or wait.
      Whether they can or cannot is unknowable from only the interface and, as
      mentioned above, depends solely on the implementation which is
      responsible for firing the Deferred.  If the methods are restricted, a
      L{twisted.trial.util.WaitIsNotReentrantError} exception will be called
      upon their invocation.

    - Since even when the methods do work, changes to their implementation which do
      not otherwise effect their interface could break unit tests which rely on
      deferredResult, deferredError, and wait, it is recommended that none of these
      methods be used in _any_ callback on a Deferred which is returned to trial.


  B{Trial is now 100% compatible with new-style classes and zope interfaces}
  --------------------------------------------------------------------------
    - Some people (the maintainer included), have been bitten in the past by
      trial's mediocre support for new-style classes (classes which inherit
      from object). In v2.0, nearly all of the classes that comprise the
      framework inherit from object, so support is built-in. Whereas before
      the C{TestCase} finding machinery used a test for inheritance from
      L{twisted.trial.unittest.TestCase}, the new mechanism tests that
      L{twisted.trial.itrial.ITestCaseFactory} is supplied by your class
      B{type}. You can write a custom C{TestCase}, and trial will detect it and
      use it as a class to test, if you do:

          >>> import zope.interface as zi 
          >>> from twisted.trial.itrial import ITestCaseFactory, ITestCase
          >>> class MyTestCase(object):
          ...     zi.classProvides(ITestCaseFactory)
          ...     zi.implements(ITestCase)
          >>>

      Naturally, the class should actually provide an implementation of
      L{twisted.trial.itrial.ITestCase}.
    - To avoid any possible conflicts (and to provide component
      de-registration), trial uses it's own private adapter registry, see
      L{twisted.trial.__init__} for details.
    - Trial makes use of zope.interface.Interfaces to allow flexibility and
      adaptation. All objects implement interfaces, and those interfaces are
      centralized and documented in L{twisted.trial.itrial}.
      

  B{All assert* and fail* methods are now top-level functions of the assertions module}
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
      
  B{Trial now supports doctests}
  ------------------------------
    To run doctests as part of your unittests: 
      - either use an existing or create a standard test module 
        (i.e. a file named test_*.py)
      - create a top-level module sequence __doctests__, which should contain
        either python modules, classes, or methodds, or fully-qualified names
        of python objects as strings
      - run trial as normal, and doctests will be run and treated the same as
        unittests
        
    Limitations:
      - skip, todo, timeout, and suppress attributes have no effect on 
        doctests (this is because we are not running the tests ourselves, but
        rather using the doctest module's runner)
      - raising SkipTest or FailTest in a doctest is not supported, and its
        behavior is undefined.
      - all setUp/tearDown methods are ignored, even if the doctest is 
        defined in a unittest.

  B{The trial script now accepts a --reporter option}
  ---------------------------------------------------
    - This is to allow for custom reporter classes. If you want to run a
      trial process remotely, and gain access to the output, or if you would
      just like to have your reporting formatted differently, you can supply
      the fully-qualified class name (of a class that implements
      L{twisted.trial.itrial.IReporter}) to --reporter, and trial will
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
      an EXPECTED_FAILURE. 'msg' is the message you want printed out if the
      test is reported with status [TODO].
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

  B{expectedAssertions} is no longer supported
  --------------------------------------------
    - it was just too difficult to make radix's clever deferred-doublecheck
      feature work with this code revision. With his permisison, this feature
      has been removed.

  B{intelligent and sane warnings suppression}
  --------------------------------------------
    - warnings suppression now takes the form of a .suppress attribute or a 
      module-level variable named 'suppress'. The suppress attribute is a list
      that contains tuples returned from the L{twisted.trial.util.suppress}
      method. For example usage, see the suppress() docstring.
      

Trial's 'special' attributes:
=============================
  1. 'Special' attributes exist on three levels: module, class, and method.
     Setting a special attribute at the module level makes that value act as the
     default value for that attribute of classes and methods contained within that
     module. The same applies to a class' attribute acting as a default for it's
     contained methods.  So when running project.test.test_foo.MyTest.testMethod
     the search would look like::

       getattr(testMethod, 'todo', 
           getattr(MyTest, 'todo', 
               getattr(test_foo, 'todo', None))) 

  2. C{.todo} attributes indicate that the test is expected to fail. New tests
     (for which the underlying functionality has not yet been added) should set
     this flag while the code is being written. Once the feature is added and the
     test starts to pass, the flag should be removed.

  3. Tests of highly-unstable in-development code should consider using
     C{.skip} to turn off the tests until the code has reached a point where
     the success rate is expected to be monotonically increasing.

  4. Tests that return deferreds may alter the default timeout period of 4.0
     seconds by adding a method attribute C{.timeout} which is the number of
     seconds as a float that trial should wait for a result. To turn off the
     timeout for a given test (which is not recommended), set timeout = None.
    
     The timeout attribute also gives you the option of setting it to a tuple,
     (timeoutvalue, TimeoutExceptionClass, exception_arg) for more control over
     the type of exception and message delivered when the method times out.

  5. If you don't want to or if you want to explicitly specify the
     classes-to-be-run in a module, you should make a module-level sequence 
     named __unittests__ that contains the classes and methods that are to 
     be run by trial.


Non-obvious rules
=================

  There are side-effects of the change in implementation of trial's internals.
  Some of the tricks you may have come to rely on will not work anymore, and
  you'll have to use slightly different tricks to gain the same effect. In the
  same respect, there are some new features that may not work quite the way you
  expect, and we'll try to document potential gotchas here.

    1. Setting a classes C{.skip} attribute in C{setUpClass} will not cause
       all of that C{TestCase}'s methods to be skipped. To get this
       behavior, you must instead raise unittest.SkipTest with the reason
       for the skip. The C{.skip} attribute is only considered once, when
       the class is first imported, before C{setUpClass} is run. Also, if
       you raise SkipTest in C{setUpClass}, the C{tearDownClass} method
       B{will} still be run (just be aware of this fact).
  
    2. If a method is C{.skip}-ed, it's C{setUp} and C{tearDown} methods
       will never be called.
  
    3. Setting the C{.skip} attribute on a C{TestCase} is equivalent to
       setting each of that class' methods C{.skip} attribute to the value
       assigned the class' C{.skip}. The same holds true for the C{.todo} or
       C{.timeout} attribute.
  
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
  
    4. Any method may override the reason for a skip or todo by setting it's
       own attribute value, in other words, the class attribute is a default
       value for the method attribute.
  
    5. If C{setUp} runs without error, C{tearDown} is guaranteed to run,
       however, if C{setUp} raises an exception (including C{SkipTest}),
       C{tearDown} will B{not} be run.
 
    6. The code that decides whether or not a given object is a C{TestCase}
       or not works by calling ITestCaseFactory.providedBy(obj). Any class
       that subclasses L{twisted.trial.unittest.TestCase} automatically
       provides this interface so in 99% of cases, you won't have to think
       about this.
  
       HOWEVER...
  
       If you are trying to do something particularly spectacular, just note
       that if you want an object that doesn't subclass unittest.TestCase in
       some way to be considered a testable object, its B{class} definition
       must do::
  
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
  
    7. A known issue is that sometimes if you press C-c during a test run,
       trial will not exit. This usually caused by using reactor threads.
       The only sure-fire way to stop trial in this case is to instead try
       C-\ which sends a SIGQUIT to the running process.


Other Notes
===========

The documentation for most of the classes can be found in
L{twisted.trial.itrial}.

"""

# system imports
import os, errno, warnings

from twisted.trial import itrial

# get assert* methods, fail* methods, FailTest and SkipTest
from twisted.trial.assertions import *
from twisted.trial.util import deferredResult, deferredError, wait

import zope.interface as zi


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

class _MetaTestCase(type):
    """registers classes that inherit from TestCase as directly providing
    ITestCaseFactory
    """
    zi.implements(itrial.ITestCaseFactory)


class TestCase(object):
    __metaclass__ = _MetaTestCase
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


class TestResult(object):

    def __init__(self):
        self.shouldStop = False


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

    def visitSuite(self, testSuite):
        """Visit the TestSuite testSuite."""

    def visitSuiteAfter(self, testSuite):
        """Visit the TestSuite testSuite after its children."""


__all__ = [
    'TestCase', 'deferredResult', 'deferredError', 'wait', 'TestResult'
    ]
