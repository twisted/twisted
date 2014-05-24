# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.names.authority}.
"""
from twisted.internet.interfaces import IResolver
from twisted.names.authority import MemoryAuthority
from twisted.trial.unittest import SynchronousTestCase

from zope.interface.verify import verifyClass

class MemoryAuthorityTests(SynchronousTestCase):
    """
    Tests for L{twisted.names.authority.MemoryAuthority}.
    """
    def test_interface(self):
        """
        L{MemoryAuthority} implements L{IResolver}.
        """
        self.assertTrue(verifyClass(IResolver, MemoryAuthority))
