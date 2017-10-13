# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.failure}.
"""

from ..failure import Failure

from twisted.python.compat import _PY3
from twisted.trial.unittest import SkipTest, SynchronousTestCase

class TestFailure(SynchronousTestCase):
    """
    Tests for L{Failure}.
    """

    def test_trapCatchException(self):
        """
        c{trap} returns the wrapped exception type if it is matched.
        """
        failure = Failure(ValueError())
        caught = failure.trap(ValueError)
        self.assertEqual(caught, ValueError)


    def test_trapRaiseWrappedException(self):
        """
        c{trap} raises the wrapped exception if there is no match on Python 3.
        """
        if not _PY3:
            raise SkipTest("Wrapped exceptions are only raised on Python 3.")
        failure = Failure(ValueError())
        self.assertRaises(ValueError, failure.trap, TypeError)


    def test_trapRaiseSelf(self):
        """
        c{trap} raises self (Failure) if there is no match on Python 2.
        """
        if _PY3:
            raise SkipTest("Self only raised on Python 2.")
        failure = Failure(ValueError())
        self.assertRaises(Failure, failure.trap, TypeError)
