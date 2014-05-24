# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.names.authority}.
"""
from twisted.internet.interfaces import IResolver
from twisted.names.authority import MemoryAuthority, FileAuthority
from twisted.names import dns
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


    def test_additionalProcessingTypes(self):
        """
        L{MemoryAuthority._ADDITIONAL_PROCESSING_TYPES} is a list of DNS record
        types for which additional records will need to be looked up.
        """
        self.assertEqual(
            (dns.CNAME, dns.MX, dns.NS),
            MemoryAuthority._ADDITIONAL_PROCESSING_TYPES
        )


    def test_addressTypes(self):
        """
        L{MemoryAuthority._ADDRESS_TYPES} is a list of DNS record types which
        are useful for inclusion in the additional section generated during
        additional processing.
        """
        self.assertEqual(
            (dns.A, dns.AAAA),
            MemoryAuthority._ADDRESS_TYPES
        )




class FileAuthorityTests(SynchronousTestCase):
    """
    Tests for L{twisted.names.authority.FileAuthority}.
    """
    def test_interface(self):
        """
        L{FileAuthority} implements L{IResolver}.
        """
        self.assertTrue(verifyClass(IResolver, FileAuthority))


    def test_memoryAuthority(self):
        """
        L{FileAuthority} is a L{MemoryAuthority}
        """
        self.assertTrue(issubclass(FileAuthority, MemoryAuthority))
