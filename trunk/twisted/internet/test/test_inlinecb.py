# -*- test-case-name: twisted.internet.test.test_inlinecb -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.defer.inlineCallbacks}.

Some tests for inlineCallbacks are defined in L{twisted.test.test_defgen} as
well.
"""

from __future__ import division, absolute_import

from twisted.trial.unittest import TestCase
from twisted.internet.defer import Deferred, returnValue, inlineCallbacks

class NonLocalExitTests(TestCase):
    """
    It's possible for L{returnValue} to be (accidentally) invoked at a stack
    level below the L{inlineCallbacks}-decorated function which it is exiting.
    If this happens, L{returnValue} should report useful errors.

    If L{returnValue} is invoked from a function not decorated by
    L{inlineCallbacks}, it will emit a warning if it causes an
    L{inlineCallbacks} function further up the stack to exit.
    """

    def mistakenMethod(self):
        """
        This method mistakenly invokes L{returnValue}, despite the fact that it
        is not decorated with L{inlineCallbacks}.
        """
        returnValue(1)


    def assertMistakenMethodWarning(self, resultList):
        """
        Flush the current warnings and assert that we have been told that
        C{mistakenMethod} was invoked, and that the result from the Deferred
        that was fired (appended to the given list) is C{mistakenMethod}'s
        result.  The warning should indicate that an inlineCallbacks function
        called 'inline' was made to exit.
        """
        self.assertEqual(resultList, [1])
        warnings = self.flushWarnings(offendingFunctions=[self.mistakenMethod])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(
            warnings[0]['message'],
            "returnValue() in 'mistakenMethod' causing 'inline' to exit: "
            "returnValue should only be invoked by functions decorated with "
            "inlineCallbacks")


    def test_returnValueNonLocalWarning(self):
        """
        L{returnValue} will emit a non-local exit warning in the simplest case,
        where the offending function is invoked immediately.
        """
        @inlineCallbacks
        def inline():
            self.mistakenMethod()
            returnValue(2)
            yield 0
        d = inline()
        results = []
        d.addCallback(results.append)
        self.assertMistakenMethodWarning(results)


    def test_returnValueNonLocalDeferred(self):
        """
        L{returnValue} will emit a non-local warning in the case where the
        L{inlineCallbacks}-decorated function has already yielded a Deferred
        and therefore moved its generator function along.
        """
        cause = Deferred()
        @inlineCallbacks
        def inline():
            yield cause
            self.mistakenMethod()
            returnValue(2)
        effect = inline()
        results = []
        effect.addCallback(results.append)
        self.assertEqual(results, [])
        cause.callback(1)
        self.assertMistakenMethodWarning(results)


