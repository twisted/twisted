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


    def test_additionalRecordsCNAME(self):
        """
        L{MemoryAuthority._additionalRecords} yields the A and AAAA records
        corresponding to the domain name value of a supplied CNAME record.
        """
        expectedRecords = [
            dns.Record_A(address="192.0.2.100"),
            dns.Record_AAAA(address="::1")
        ]
        expectedName = b"example.com"
        expectedHeaders = [
            dns.RRHeader(name=expectedName, type=r.TYPE, payload=r, auth=True)
            for r in expectedRecords
        ]
        actualRecords = list(
            self.factory(
                records={expectedName: expectedRecords}
            )._additionalRecords(
                answer=[
                    dns.RRHeader(
                        type=dns.CNAME,
                        payload=dns.Record_CNAME(name=expectedName)
                    )
                ],
                authority=[],
                ttl=0
            )
        )

        self.assertEqual(expectedHeaders, actualRecords)



class MemoryAuthorityTests(MemoryAuthorityTestsMixin, SynchronousTestCase):
    """
    Tests for L{MemoryAuthority}.
    """
    factoryClass = MemoryAuthority
    factory = factoryClass


    def test_recordsOverride(self):
        """
        L{MemoryAuthority.records} can be set from the initialiser.
        """
        expectedRecords = {b'www.example.com': [dns.Record_A()]}
        self.assertEqual(
            expectedRecords,
            self.factory(records=expectedRecords).records
        )




class NoFileAuthority(FileAuthority):
    """
    A L{FileAuthority} with a noop C{loadFile} method for use in tests.
    """
    def __init__(self, records=None):
        """
        Initialise L{FileAuthority} with an empty filename and allow records to
        be passed in.
        """
        FileAuthority.__init__(self, filename='')
        if records is None:
            records = {}
        self.records = records


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
