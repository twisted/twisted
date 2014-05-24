# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.names.authority}.
"""
from twisted.internet.interfaces import IResolver
from twisted.names.authority import _MemoryAuthority, FileAuthority
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
    Common tests for L{twisted.names.authority._MemoryAuthority} and other
    authority classes.
    """
    def test_interface(self):
        """
        L{_MemoryAuthority} implements L{IResolver}.
        """
        self.assertTrue(verifyClass(IResolver, self.factoryClass))



class MemoryAuthorityTests(AuthorityTestsMixin, SynchronousTestCase):
    """
    Tests for L{_MemoryAuthority}.
    """
    factoryClass = _MemoryAuthority
    factory = factoryClass

    def test_soaDefault(self):
        """
        L{_MemoryAuthority.soa} defaults to (C{b''}, None).
        """
        self.assertEqual((b'', None), self.factory().soa)


    def test_soaOverride(self):
        """
        L{_MemoryAuthority.soa} can be set from the initialiser.
        """
        expectedSOA = (SOA_NAME, SOA_RECORD)
        self.assertEqual(expectedSOA, self.factory(soa=expectedSOA).soa)


    def test_recordsDefault(self):
        """
        L{_MemoryAuthority.records} is an empty dict by default.
        """
        self.assertEqual(
            {},
            self.factory().records
        )


    def test_recordsOverride(self):
        """
        L{_MemoryAuthority.records} can be set from the initialiser.
        """
        expectedRecords = {b'www.example.com': [dns.Record_A()]}
        self.assertEqual(
            expectedRecords,
            self.factory(records=expectedRecords).records
        )


    def test_ttlDefault(self):
        """
        L{_MemoryAuthority._defaultTTL} finds the highest TTL from the soa
        minimum and expires TTLs.
        """
        expected = (2222, 3333)
        actual = (
            _MemoryAuthority(
                soa=(b'example.com', dns.Record_SOA(minimum=1111, expire=2222))
            )._defaultTTL,
            _MemoryAuthority(
                soa=(b'example.com', dns.Record_SOA(minimum=3333, expire=2222))
            )._defaultTTL
        )
        self.assertEqual(expected, actual)


    def test_ttlOverride(self):
        """
        L{_MemoryAuthority._defaultTTL} can be set from the initialiser.
        """
        expectedTTL = 60
        self.assertEqual(
            expectedTTL,
            self.factory(defaultTTL=expectedTTL)._defaultTTL
        )



class MemoryAuthorityLookupTests(SynchronousTestCase):
    """
    Tests for L{_MemoryAuthority._lookup}.
    """
    def test_authoritativeDomainError(self):
        """
        L{_MemoryAuthority._lookup} returns L{error.AuthoritativeDomainError} if
        the requested name has no records.
        """
        d = _MemoryAuthority(
            soa=(SOA_NAME, SOA_RECORD),
            records={SOA_NAME: [SOA_RECORD]}
        )._lookup(name=b'unknown.example.com', cls=dns.IN, type=dns.A)
        self.failureResultOf(d, error.AuthoritativeDomainError)


    def test_nonAuthoritativeDomainError(self):
        """
        L{_MemoryAuthority._lookup} returns L{error.DomainError} if the requested
        name is outside of the zone of authority.
        """
        # SOA_NAME is example.com so choose a different second level domain.
        d = _MemoryAuthority(
            soa=(SOA_NAME, SOA_RECORD),
            records={SOA_NAME: [SOA_RECORD]}
        )._lookup(name=b'unknown.unknown.com', cls=dns.IN, type=dns.A)
        self.failureResultOf(d, error.DomainError)



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
