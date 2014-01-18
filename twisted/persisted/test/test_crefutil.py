# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.persisted.crefutil}.
"""

from twisted.trial.unittest import SynchronousTestCase
from twisted.persisted.crefutil import _DictKeyAndValue, _Defer


class CrefUtilTestCase(SynchronousTestCase):
    """
    Tests for L{crefutil}.
    """

    def test_dictUnknownKey(self):
        """
        L{crefutil._DictKeyAndValue} only support keys C{0} and C{1}.
        """
        d = _DictKeyAndValue({})
        self.assertRaises(RuntimeError, d.__setitem__, 2, 3)


    def test_deferSetMultipleTimes(self):
        """
        L{crefutil._Defer} can be assigned a key only one time.
        """
        d = _Defer()
        d[0] = 1
        self.assertRaises(RuntimeError, d.__setitem__, 0, 1)
