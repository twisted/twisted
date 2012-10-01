# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet._utilspy3}.
"""

from __future__ import division, absolute_import

import warnings

from twisted.trial import unittest
from twisted.internet import _utilspy3 as utils
from twisted.internet.defer import Deferred
from twisted.python.test.test_utilpy3 import SuppressedWarningsTests

class SuppressWarningsTests(unittest.SynchronousTestCase):
    """
    Tests for L{utils.suppressWarnings}.
    """
    def test_suppressWarnings(self):
        """
        L{utils.suppressWarnings} decorates a function so that the given
        warnings are suppressed.
        """
        result = []
        def showwarning(self, *a, **kw):
            result.append((a, kw))
        self.patch(warnings, "showwarning", showwarning)

        def f(msg):
            warnings.warn(msg)
        g = utils.suppressWarnings(f, (('ignore',), dict(message="This is message")))

        # Start off with a sanity check - calling the original function
        # should emit the warning.
        f("Sanity check message")
        self.assertEqual(len(result), 1)

        # Now that that's out of the way, call the wrapped function, and
        # make sure no new warnings show up.
        g("This is message")
        self.assertEqual(len(result), 1)

        # Finally, emit another warning which should not be ignored, and
        # make sure it is not.
        g("Unignored message")
        self.assertEqual(len(result), 2)



class DeferredSuppressedWarningsTests(SuppressedWarningsTests):
    """
    Tests for L{utils.runWithWarningsSuppressed}, the version that supports
    Deferreds.
    """
    # Override the non-Deferred-supporting function from the base class with
    # the function we are testing in this class:
    runWithWarningsSuppressed = staticmethod(utils.runWithWarningsSuppressed)

    def test_deferredCallback(self):
        """
        If the function called by L{utils.runWithWarningsSuppressed} returns a
        C{Deferred}, the warning filters aren't removed until the Deferred
        fires.
        """
        filters = [(("ignore", ".*foo.*"), {}),
                   (("ignore", ".*bar.*"), {})]
        result = Deferred()
        self.runWithWarningsSuppressed(filters, lambda: result)
        warnings.warn("ignore foo")
        result.callback(3)
        warnings.warn("ignore foo 2")
        self.assertEqual(
            ["ignore foo 2"], [w['message'] for w in self.flushWarnings()])

    def test_deferredErrback(self):
        """
        If the function called by L{utils.runWithWarningsSuppressed} returns a
        C{Deferred}, the warning filters aren't removed until the Deferred
        fires with an errback.
        """
        filters = [(("ignore", ".*foo.*"), {}),
                   (("ignore", ".*bar.*"), {})]
        result = Deferred()
        d = self.runWithWarningsSuppressed(filters, lambda: result)
        warnings.warn("ignore foo")
        result.errback(ZeroDivisionError())
        d.addErrback(lambda f: f.trap(ZeroDivisionError))
        warnings.warn("ignore foo 2")
        self.assertEqual(
            ["ignore foo 2"], [w['message'] for w in self.flushWarnings()])
