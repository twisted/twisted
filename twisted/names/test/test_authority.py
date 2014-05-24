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



class MemoryAuthorityTestsMixin(object):
    """
    Common tests for L{twisted.names.authority.MemoryAuthority} and its
    subclasses.
    """
    def test_interface(self):
        """
        L{MemoryAuthority} implements L{IResolver}.
        """
        self.assertTrue(verifyClass(IResolver, self.factoryClass))


    def test_recordsDefault(self):
        """
        L{MemoryAuthority.records} is an empty dict by default.
        """
        self.assertEqual(
            {},
            self.factory().records
        )


    def test_additionalProcessingTypes(self):
        """
        L{MemoryAuthority._ADDITIONAL_PROCESSING_TYPES} is a list of DNS record
        types for which additional records will need to be looked up.
        """
        self.assertEqual(
            (dns.CNAME, dns.MX, dns.NS),
            self.factoryClass._ADDITIONAL_PROCESSING_TYPES
        )


    def test_addressTypes(self):
        """
        L{MemoryAuthority._ADDRESS_TYPES} is a list of DNS record types which
        are useful for inclusion in the additional section generated during
        additional processing.
        """
        self.assertEqual(
            (dns.A, dns.AAAA),
            self.factoryClass._ADDRESS_TYPES
        )



class MemoryAuthorityTests(MemoryAuthorityTestsMixin, SynchronousTestCase):
    """
    Tests for L{MemoryAuthority}.
    """
    factoryClass = MemoryAuthority
    factory = factoryClass



class NoFileAuthority(FileAuthority):
    """
    A L{FileAuthority} with a noop C{loadFile} method for use in tests.
    """
    def __init__(self):
        """
        Initialise L{FileAuthority} with an empty filename.
        """
        FileAuthority.__init__(self, filename='')


    def loadFile(self, filename):
        """
        Noop loadFile to allow L{FileAuthority.__init__} to run without error.
        """



class FileAuthorityTests(MemoryAuthorityTestsMixin, SynchronousTestCase):
    """
    Tests for L{FileAuthority}.
    """
    factoryClass = NoFileAuthority
    factory = factoryClass
