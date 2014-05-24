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


    def assertAdditionalRecords(self, expectedRecords, **suppliedArguments):
        """
        Assert that L{MemoryAuthority._additionalRecords} yields the expected
        records for the supplied answers and authority records.
        """
        expectedHeaders = []
        for name, records in expectedRecords.items():
            for record in records:
                expectedHeaders.append(
                    dns.RRHeader(name=name,
                                 type=record.TYPE,
                                 payload=record,
                                 auth=True)
                )
        actualRecords = list(
            self.factory(records=expectedRecords)._additionalRecords(
                **suppliedArguments)
        )

        sortBy = lambda r: (r.name.name, r.type)
        self.assertEqual(sorted(expectedHeaders, key=sortBy),
                         sorted(actualRecords, key=sortBy))


    def test_additionalRecordsCNAME(self):
        """
        L{MemoryAuthority._additionalRecords} yields the A and AAAA records
        corresponding to the domain name value of a supplied CNAME record.
        """
        self.assertAdditionalRecords(
            expectedRecords={
                b'example.com': [
                    dns.Record_A(address="192.0.2.100"),
                    dns.Record_AAAA(address="::1")
                ]
            },
            answer=[
                dns.RRHeader(
                    type=dns.CNAME,
                    payload=dns.Record_CNAME(name=b'example.com')
                )
            ],
            authority=[],
            ttl=0
        )


    def test_additionalRecordsNS(self):
        """
        L{MemoryAuthority._additionalRecords} yields the A and AAAA records
        corresponding to the domain name value of a supplied NS record.
        """
        self.assertAdditionalRecords(
            expectedRecords={
                b'ns1.example.com': [
                    dns.Record_A(address="192.0.2.100"),
                    dns.Record_AAAA(address="::1")
                ]
            },
            answer=[
                dns.RRHeader(
                    type=dns.NS,
                    payload=dns.Record_NS(name=b'ns1.example.com')
                )
            ],
            authority=[],
            ttl=0
        )


    def test_additionalRecordsMX(self):
        """
        L{MemoryAuthority._additionalRecords} yields the A and AAAA records
        corresponding to the domain name value of a supplied MX record.
        """
        self.assertAdditionalRecords(
            expectedRecords={
                b'mail.example.com': [
                    dns.Record_A(address="192.0.2.100"),
                    dns.Record_AAAA(address="::1")
                ]
            },
            answer=[
                dns.RRHeader(
                    type=dns.MX,
                    payload=dns.Record_MX(name=b'mail.example.com')
                )
            ],
            authority=[],
            ttl=0
        )


    def test_additionalRecordsMixed(self):
        """
        L{MemoryAuthority._additionalRecords} yields the A and AAAA records
        corresponding to the domain name values of all the supplied name
        records.
        """
        self.assertAdditionalRecords(
            expectedRecords={
                b'example.com': [
                    dns.Record_A(address="192.0.2.101"),
                    dns.Record_AAAA(address="::1")
                ],
                b'ns1.example.com': [
                    dns.Record_A(address="192.0.2.102"),
                    dns.Record_AAAA(address="::2")
                ],
                b'mail.example.com': [
                    dns.Record_A(address="192.0.2.103"),
                    dns.Record_AAAA(address="::3")
                ]
            },
            answer=[
                dns.RRHeader(
                    type=dns.CNAME,
                    payload=dns.Record_CNAME(name=b'example.com')
                ),
                dns.RRHeader(
                    type=dns.MX,
                    payload=dns.Record_MX(name=b'mail.example.com')
                )
            ],
            authority=[
                dns.RRHeader(
                    type=dns.NS,
                    payload=dns.Record_NS(name=b'ns1.example.com')
                )
            ],
            ttl=0
        )




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


    def test_soaDefault(self):
        """
        L{MemoryAuthority._soa} defaults to C{b''}.
        """
        self.assertEqual(b'', self.factory()._soa)


    def test_soaOverride(self):
        """
        L{MemoryAuthority._soa} can be set from the initialiser.
        """
        expectedSOA = b'example.com'
        self.assertEqual(expectedSOA, self.factory(soa=expectedSOA)._soa)



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
