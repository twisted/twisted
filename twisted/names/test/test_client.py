# -*- test-case-name: twisted.names.test.test_client -*-
# Copyright (c) 2001-2006 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for twisted.names.client
"""

from twisted.names import client, dns
from twisted.trial import unittest
from twisted.names.common import ResolverBase
from twisted.internet import defer

class FakeResolver(ResolverBase):
    
    def _lookup(self, name, cls, qtype, timeout):
        """
        The getHostByNameTest does a different type of query that requires it
        return an A record from an ALL_RECORDS lookup, so we accomodate that
        here.
        """
        if name == 'getHostByNameTest':
            rr = dns.RRHeader(name=name, type=dns.A, cls=cls, ttl=60,
                    payload=dns.Record_A(address='127.0.0.1', ttl=60))
        else:
            rr = dns.RRHeader(name=name, type=qtype, cls=cls, ttl=60)
            
        results = [rr]
        authority = []
        addtional = []
        return defer.succeed((results, authority, addtional))

class ClientTestCase(unittest.TestCase):

    def setUp(self):
        """
        Replace the resolver with a FakeResolver
        """
        client.theResolver = FakeResolver()
        self.hostname = 'example.com'
        self.ghbntest = 'getHostByNameTest'

    def tearDown(self):
        """
        By setting the resolver to None, it will be recreated next time a name
        lookup is done.
        """
        client.theResolver = None

    def checkResult(self, (results, authority, additional), qtype):
        """
        Verify that the result is the same query type as what is expected.
        """
        result = results[0]
        self.assertEquals(str(result.name), self.hostname)
        self.assertEquals(result.type, qtype)

    def checkGetHostByName(self, result):
        """
        Test that the getHostByName query returns the 127.0.0.1 address.
        """
        self.assertEquals(result, '127.0.0.1')

    def test_getHostByName(self):
        """
        do a getHostByName of a value that should return 127.0.0.1.
        """
        d = client.getHostByName(self.ghbntest)
        d.addCallback(self.checkGetHostByName)
        return d

    def test_lookupAddress(self):
        """
        Do a lookup and test that the resolver will issue the correct type of
        query type. We do this by checking that FakeResolver returns a result
        record with the same query type as what we issued.
        """
        d = client.lookupAddress(self.hostname)
        d.addCallback(self.checkResult, dns.A)
        return d

    def test_lookupIPV6Address(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupIPV6Address(self.hostname)
        d.addCallback(self.checkResult, dns.AAAA)
        return d

    def test_lookupAddress6(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupAddress6(self.hostname)
        d.addCallback(self.checkResult, dns.A6)
        return d

    def test_lookupNameservers(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupNameservers(self.hostname)
        d.addCallback(self.checkResult, dns.NS)
        return d

    def test_lookupCanonicalName(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupCanonicalName(self.hostname)
        d.addCallback(self.checkResult, dns.CNAME)
        return d

    def test_lookupAuthority(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupAuthority(self.hostname)
        d.addCallback(self.checkResult, dns.SOA)
        return d

    def test_lookupMailBox(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupMailBox(self.hostname)
        d.addCallback(self.checkResult, dns.MB)
        return d

    def test_lookupMailGroup(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupMailGroup(self.hostname)
        d.addCallback(self.checkResult, dns.MG)
        return d

    def test_lookupMailRename(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupMailRename(self.hostname)
        d.addCallback(self.checkResult, dns.MR)
        return d

    def test_lookupNull(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupNull(self.hostname)
        d.addCallback(self.checkResult, dns.NULL)
        return d

    def test_lookupWellKnownServices(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupWellKnownServices(self.hostname)
        d.addCallback(self.checkResult, dns.WKS)
        return d

    def test_lookupPointer(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupPointer(self.hostname)
        d.addCallback(self.checkResult, dns.PTR)
        return d

    def test_lookupHostInfo(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupHostInfo(self.hostname)
        d.addCallback(self.checkResult, dns.HINFO)
        return d

    def test_lookupMailboxInfo(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupMailboxInfo(self.hostname)
        d.addCallback(self.checkResult, dns.MINFO)
        return d

    def test_lookupMailExchange(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupMailExchange(self.hostname)
        d.addCallback(self.checkResult, dns.MX)
        return d

    def test_lookupText(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupText(self.hostname)
        d.addCallback(self.checkResult, dns.TXT)
        return d

    def test_lookupResponsibility(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupResponsibility(self.hostname)
        d.addCallback(self.checkResult, dns.RP)
        return d

    def test_lookupAFSDatabase(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupAFSDatabase(self.hostname)
        d.addCallback(self.checkResult, dns.AFSDB)
        return d

    def test_lookupService(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupService(self.hostname)
        d.addCallback(self.checkResult, dns.SRV)
        return d

    def test_lookupZone(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupZone(self.hostname)
        d.addCallback(self.checkResult, dns.AXFR)
        return d

    def test_lookupAllRecords(self):
        """
        See L{test_lookupAddress}
        """
        d = client.lookupAllRecords(self.hostname)
        d.addCallback(self.checkResult, dns.ALL_RECORDS)
        return d

