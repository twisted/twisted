# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.names.authority}.
"""
from twisted.internet.interfaces import IResolver
from twisted.names.authority import MemoryAuthority, FileAuthority
from twisted.names import dns, error
from twisted.trial.unittest import SynchronousTestCase

from zope.interface.verify import verifyClass



SOA_NAME = b'example.com'
SOA_RECORD = dns.Record_SOA(
    mname = 'ns1.example.com',
    rname = 'hostmaster.example.com',
    serial = 100,
    refresh = 100,
    minimum = 86400,
    expire = 86400,
    retry = 100,
    ttl=100
)



class AuthorityTestsMixin(object):
    """
    Common tests for L{twisted.names.authority.MemoryAuthority} and other
    authority classes.
    """
    def test_interface(self):
        """
        L{MemoryAuthority} implements L{IResolver}.
        """
        self.assertTrue(verifyClass(IResolver, self.factoryClass))



class MemoryAuthorityTests(AuthorityTestsMixin, SynchronousTestCase):
    """
    Tests for L{MemoryAuthority}.
    """
    factoryClass = MemoryAuthority
    factory = factoryClass

    def test_soaDefault(self):
        """
        L{MemoryAuthority.soa} defaults to (C{b''}, None).
        """
        self.assertEqual((b'', None), self.factory().soa)


    def test_soaOverride(self):
        """
        L{MemoryAuthority.soa} can be set from the initialiser.
        """
        expectedSOA = (SOA_NAME, SOA_RECORD)
        self.assertEqual(expectedSOA, self.factory(soa=expectedSOA).soa)


    def test_recordsDefault(self):
        """
        L{MemoryAuthority.records} is an empty dict by default.
        """
        self.assertEqual(
            {},
            self.factory().records
        )


    def test_recordsOverride(self):
        """
        L{MemoryAuthority.records} can be set from the initialiser.
        """
        expectedRecords = {b'www.example.com': [dns.Record_A()]}
        self.assertEqual(
            expectedRecords,
            self.factory(records=expectedRecords).records
        )


    def test_ttlDefault(self):
        """
        L{MemoryAuthority._defaultTTL} finds the highest TTL from the soa
        minimum and expires TTLs.
        """
        expected = (2222, 3333)
        actual = (
            MemoryAuthority(
                soa=(b'example.com', dns.Record_SOA(minimum=1111, expire=2222))
            )._defaultTTL,
            MemoryAuthority(
                soa=(b'example.com', dns.Record_SOA(minimum=3333, expire=2222))
            )._defaultTTL
        )
        self.assertEqual(expected, actual)


    def test_ttlOverride(self):
        """
        L{MemoryAuthority._defaultTTL} can be set from the initialiser.
        """
        expectedTTL = 60
        self.assertEqual(
            expectedTTL,
            self.factory(defaultTTL=expectedTTL)._defaultTTL
        )



class MemoryAuthorityLookupTests(SynchronousTestCase):
    """
    Tests for L{MemoryAuthority._lookup}.
    """
    def test_authoritativeDomainError(self):
        """
        L{MemoryAuthority._lookup} returns L{error.AuthoritativeDomainError} if
        the requested name has no records.
        """
        d = MemoryAuthority(
            soa=(SOA_NAME, SOA_RECORD),
            records={SOA_NAME: [SOA_RECORD]}
        )._lookup(name=b'unknown.example.com', cls=dns.IN, type=dns.A)
        self.failureResultOf(d, error.AuthoritativeDomainError)


    def test_nonAuthoritativeDomainError(self):
        """
        L{MemoryAuthority._lookup} returns L{error.DomainError} if the requested
        name is outside of the zone of authority.
        """
        # SOA_NAME is example.com so choose a different second level domain.
        d = MemoryAuthority(
            soa=(SOA_NAME, SOA_RECORD),
            records={SOA_NAME: [SOA_RECORD]}
        )._lookup(name=b'unknown.unknown.com', cls=dns.IN, type=dns.A)
        self.failureResultOf(d, error.DomainError)



class MemoryAuthorityAdditionalRecordsTests(SynchronousTestCase):
    """
    """
    factoryClass = MemoryAuthority
    factory = factoryClass

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
                                 auth=True,
                                 ttl=86400
                             )
                )
        actualHeaders = list(
            self.factory(
                records=expectedRecords,
                defaultTTL=86400
            )._additionalRecords(**suppliedArguments)
        )

        sortBy = lambda r: (r.name.name, r.type)
        self.assertEqual(sorted(expectedHeaders, key=sortBy),
                         sorted(actualHeaders, key=sortBy))


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
        )



class TestFileAuthority(FileAuthority):
    """
    A L{FileAuthority} with a C{loadFile} method that loads some canned records
    for use in tests.
    """
    def loadFile(self, filename):
        """
        A noop loadfile which allows the initialiser to run without error.

        @param filename: ignored
        """


    @classmethod
    def fromCannedRecords(cls, soa=None, records=None):
        """
        """
        authority = cls(filename='')

        if soa is None:
            soa = (SOA_NAME, SOA_RECORD)
        authority.soa = soa

        if records is None:
            records = {
                SOA_NAME: [
                    SOA_RECORD,
                ]
            }
        authority.records = records

        return authority



class FileAuthorityTests(AuthorityTestsMixin, SynchronousTestCase):
    """
    Tests for L{FileAuthority}.
    """
    factoryClass = TestFileAuthority

    def test_soa(self):
        """
        L{FileAuthority.soa} is a 2-tuple of (SOA name, SOA record).
        """
        self.assertEqual(
            (SOA_NAME, SOA_RECORD),
            TestFileAuthority.fromCannedRecords().soa
        )


    def test_records(self):
        """
        L{FileAuthority.records} is a dictionary mapping names to lists of
        records.
        """
        self.assertEqual(
            {SOA_NAME: [SOA_RECORD]},
            TestFileAuthority.fromCannedRecords().records
        )
