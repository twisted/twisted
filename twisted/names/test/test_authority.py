# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.names.authority}.
"""
from functools import partial

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
    refresh = 1234,
    minimum = 7654,
    expire = 19283784,
    retry = 15,
    ttl=1
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


    def test_defaultTTL(self):
        """
        L{MemoryAuthority._defaultTTL} finds the highest TTL from the soa
        minimum and expires TTLs.
        """
        expected = (2222, 3333)
        actual = (
            MemoryAuthority(
                soa=(b'example.com', dns.Record_SOA(minimum=1111, expire=2222))
            )._defaultTTL(),
            MemoryAuthority(
                soa=(b'example.com', dns.Record_SOA(minimum=3333, expire=2222))
            )._defaultTTL()
        )
        self.assertEqual(expected, actual)


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



class AdditionalProcessingTests(SynchronousTestCase):
    """
    Tests for L{MemoryAuthority}'s additional processing for those record types
    which require it (MX, CNAME, etc).
    """
    _A = dns.Record_A(b"10.0.0.1")
    _AAAA = dns.Record_AAAA(b"f080::1")

    def _lookupSomeRecords(self, method, soa, makeRecord, target, addresses):
        """
        Perform a DNS lookup against a L{MemoryAuthority} configured with
        records as defined by C{makeRecord} and C{addresses}.

        @param method: The name of the lookup method to use; for example,
            C{"lookupNameservers"}.
        @type method: L{str}

        @param soa: A L{Record_SOA} for the zone for which the
            L{MemoryAuthority} is authoritative.

        @param makeRecord: A one-argument callable which accepts a name and
            returns an L{IRecord} provider.  L{MemoryAuthority} is constructed
            with this record.  The L{MemoryAuthority} is queried for a record of
            the resulting type with the given name.

        @param target: The extra name which the record returned by
            C{makeRecord} will be pointed at; this is the name which might
            require extra processing by the server so that all the available,
            useful information is returned.  For example, this is the target of
            a CNAME record or the mail exchange host pointed to by an MX record.
        @type target: L{bytes}

        @param addresses: A L{list} of records giving addresses of C{target}.

        @return: A L{Deferred} that fires with the result of the resolver
            method give by C{method}.
        """
        authority = MemoryAuthority(
            soa=(soa.mname.name, soa),
            records={
                soa.mname.name: [makeRecord(target)],
                target: addresses,
                },
            )
        return getattr(authority, method)(SOA_RECORD.mname.name)


    def assertRecordsMatch(self, expected, computed):
        """
        Assert that the L{RRHeader} instances given by C{expected} and
        C{computed} carry all the same information but without requiring the
        records appear in the same order.

        @param expected: A L{list} of L{RRHeader} instances giving the expected
            records.

        @param computed: A L{list} of L{RRHeader} instances giving the records
            computed by the scenario under test.

        @raise self.failureException: If the two collections of records
            disagree.
        """
        # RRHeader instances aren't inherently ordered.  Impose an ordering
        # that's good enough for the purposes of these tests - in which we
        # never have more than one record of a particular type.
        key = lambda rr: rr.type
        self.assertEqual(sorted(expected, key=key), sorted(computed, key=key))


    def _additionalTest(self, method, makeRecord, addresses):
        """
        Verify that certain address records are included in the I{additional}
        section of a response generated by L{MemoryAuthority}.

        @param method: See L{_lookupSomeRecords}

        @param makeRecord: See L{_lookupSomeRecords}

        @param addresses: A L{list} of L{IRecord} providers which the
            I{additional} section of the response is required to match
            (ignoring order).

        @raise self.failureException: If the I{additional} section of the
            response consists of different records than those given by
            C{addresses}.
        """
        target = b"mail." + SOA_RECORD.mname.name
        d = self._lookupSomeRecords(
            method, SOA_RECORD, makeRecord, target, addresses)
        answer, authority, additional = self.successResultOf(d)

        self.assertRecordsMatch(
            [dns.RRHeader(
                target, address.TYPE, ttl=SOA_RECORD.expire, payload=address,
                auth=True)
             for address in addresses],
            additional)


    def _additionalMXTest(self, addresses):
        """
        Verify that a response to an MX query has certain records in the
        I{additional} section.

        @param addresses: See C{_additionalTest}
        """
        self._additionalTest(
            "lookupMailExchange", partial(dns.Record_MX, 10), addresses)


    def test_mailExchangeAdditionalA(self):
        """
        If the name of the MX response has A records, they are included in the
        additional section of the response.
        """
        self._additionalMXTest([self._A])


    def test_mailExchangeAdditionalAAAA(self):
        """
        If the name of the MX response has AAAA records, they are included in
        the additional section of the response.
        """
        self._additionalMXTest([self._AAAA])


    def test_mailExchangeAdditionalBoth(self):
        """
        If the name of the MX response has both A and AAAA records, they are
        all included in the additional section of the response.
        """
        self._additionalMXTest([self._A, self._AAAA])


    def _additionalNSTest(self, addresses):
        """
        Verify that a response to an NS query has certain records in the
        I{additional} section.

        @param addresses: See C{_additionalTest}
        """
        self._additionalTest(
            "lookupNameservers", dns.Record_NS, addresses)


    def test_nameserverAdditionalA(self):
        """
        If the name of the NS response has A records, they are included in the
        additional section of the response.
        """
        self._additionalNSTest([self._A])


    def test_nameserverAdditionalAAAA(self):
        """
        If the name of the NS response has AAAA records, they are included in
        the additional section of the response.
        """
        self._additionalNSTest([self._AAAA])


    def test_nameserverAdditionalBoth(self):
        """
        If the name of the NS response has both A and AAAA records, they are
        all included in the additional section of the response.
        """
        self._additionalNSTest([self._A, self._AAAA])


    def _answerCNAMETest(self, addresses):
        """
        Verify that a response to a CNAME query has certain records in the
        I{answer} section.

        @param addresses: See C{_additionalTest}
        """
        target = b"www." + SOA_RECORD.mname.name
        d = self._lookupSomeRecords(
            "lookupCanonicalName", SOA_RECORD, dns.Record_CNAME, target,
            addresses)
        answer, authority, additional = self.successResultOf(d)

        alias = dns.RRHeader(
            SOA_RECORD.mname.name, dns.CNAME, ttl=SOA_RECORD.expire,
            payload=dns.Record_CNAME(target), auth=True)
        self.assertRecordsMatch(
            [dns.RRHeader(
                target, address.TYPE, ttl=SOA_RECORD.expire, payload=address,
                auth=True)
             for address in addresses] + [alias],
            answer)


    def test_canonicalNameAnswerA(self):
        """
        If the name of the CNAME response has A records, they are included in
        the answer section of the response.
        """
        self._answerCNAMETest([self._A])


    def test_canonicalNameAnswerAAAA(self):
        """
        If the name of the CNAME response has AAAA records, they are included
        in the answer section of the response.
        """
        self._answerCNAMETest([self._AAAA])


    def test_canonicalNameAnswerBoth(self):
        """
        If the name of the CNAME response has both A and AAAA records, they are
        all included in the answer section of the response.
        """
        self._answerCNAMETest([self._A, self._AAAA])



class TestFileAuthority(FileAuthority):
    """
    A L{FileAuthority} with a C{loadFile} method that loads some canned records
    for use in tests.
    """
    def loadFile(self, filename):
        self.soa = (SOA_NAME, SOA_RECORD)
        self.records = {
            SOA_NAME: [
                SOA_RECORD,
            ]
        }



class FileAuthorityTests(AuthorityTestsMixin, SynchronousTestCase):
    """
    Tests for L{FileAuthority}.
    """
    factoryClass = TestFileAuthority
    factory = factoryClass

    def test_soa(self):
        """
        L{FileAuthority.soa} is a 2-tuple of (SOA name, SOA record).
        """
        self.assertEqual(
            (SOA_NAME, SOA_RECORD),
            TestFileAuthority(filename='').soa
        )


    def test_records(self):
        """
        L{FileAuthority.records} is a dictionary mapping names to lists of
        records.
        """
        self.assertEqual(
            {SOA_NAME: [SOA_RECORD]},
            TestFileAuthority(filename='').records
        )
