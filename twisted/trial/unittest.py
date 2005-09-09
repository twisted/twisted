# -*- test-case-name: twisted.trial.test.test_trial -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


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


class TestCase(object):
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
    failUnlessSubstring = lambda self, *args: failUnlessSubstring(*args)
    failIfSubstring = lambda self, *args: failIfSubstring(*args)

    assertSubstring = failUnlessSubstring
    assertNotSubstring = failIfSubstring
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
