
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA


"""
Test cases for twisted.names.
"""
from __future__ import nested_scopes

import sys, socket, operator, copy
from twisted.trial import unittest
from twisted.trial.util import deferredResult as dR
from twisted.trial.util import wait

from twisted.internet import reactor, protocol, defer, error
from twisted.names import client, server, common, authority, hosts
from twisted.protocols import dns
from twisted.python import log, failure

# IPv6 support is spotty at best!
try:
    socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
except:
    IPv6 = False
else:
    IPv6 = True

def justPayload(results):
    return [r.payload for r in results[0]]

class NoFileAuthority(authority.FileAuthority):
    def __init__(self, soa, records):
        # Yes, skip FileAuthority
        common.ResolverBase.__init__(self)
        self.soa, self.records = soa, records


soa_record = dns.Record_SOA(
                    mname = 'test-domain.com',
                    rname = 'root.test-domain.com',
                    serial = 100,
                    refresh = 1234,
                    minimum = 7654,
                    expire = 19283784,
                    retry = 15,
                    ttl=1
                )

reverse_soa = dns.Record_SOA(
                     mname = '93.84.28.in-addr.arpa',
                     rname = '93.84.28.in-addr.arpa',
                     serial = 120,
                     refresh = 54321,
                     minimum = 382,
                     expire = 11193983,
                     retry = 30,
                     ttl=3
                )

my_soa = dns.Record_SOA(
    mname = 'my-domain.com',
    rname = 'postmaster.test-domain.com',
    serial = 130,
    refresh = 12345,
    minimum = 1,
    expire = 999999,
    retry = 100,
    )
    

test_domain_com = NoFileAuthority(
    soa = ('test-domain.com', soa_record),
    records = {
        'test-domain.com': [
            soa_record,
            dns.Record_A('127.0.0.1'),
            dns.Record_NS('39.28.189.39'),
            dns.Record_MX(10, 'host.test-domain.com'),
            dns.Record_HINFO(os='Linux', cpu='A Fast One, Dontcha know'),
            dns.Record_CNAME('canonical.name.com'),
            dns.Record_MB('mailbox.test-domain.com'),
            dns.Record_MG('mail.group.someplace'),
            dns.Record_TXT('A First piece of Text', 'a SecoNd piece')
        ] + (IPv6 and [
            dns.Record_A6(0, 'ABCD::4321', ''),
            dns.Record_A6(12, '0:0069::0', 'some.network.tld'),
            dns.Record_A6(8, '0:5634:1294:AFCB:56AC:48EF:34C3:01FF', 'tra.la.la.net')
        ] or []) + [
            dns.Record_TXT('Some more text, haha!  Yes.  \0  Still here?'),
            dns.Record_MR('mail.redirect.or.whatever'),
            dns.Record_MINFO(rmailbx='r mail box', emailbx='e mail box'),
            dns.Record_AFSDB(subtype=1, hostname='afsdb.test-domain.com'),
            dns.Record_RP(mbox='whatever.i.dunno', txt='some.more.text'),
            dns.Record_WKS('12.54.78.12', socket.IPPROTO_TCP, '\x12\x01\x16\xfe\xc1\x00\x01'),
        ] + (IPv6 and [dns.Record_AAAA('AF43:5634:1294:AFCB:56AC:48EF:34C3:01FF')] or []),
        'http.tcp.test-domain.com': [
            dns.Record_SRV(257, 16383, 43690, 'some.other.place.fool')
        ],
        'host.test-domain.com': [
            dns.Record_A('123.242.1.5'),
            dns.Record_A('0.255.0.255'),
        ],
        'host-two.test-domain.com': [
#
#  Python bug
#           dns.Record_A('255.255.255.255'),
#
            dns.Record_A('255.255.255.254'),
            dns.Record_A('0.0.0.0')
        ],
    }
)

reverse_domain = NoFileAuthority(
    soa = ('93.84.28.in-addr.arpa', reverse_soa),
    records = {
        '123.93.84.28.in-addr.arpa': [
             dns.Record_PTR('test.host-reverse.lookup.com'),
             reverse_soa
        ]
    }
)


my_domain_com = NoFileAuthority(
    soa = ('my-domain.com', my_soa),
    records = {
        'my-domain.com': [
            my_soa,
            dns.Record_A('1.2.3.4', ttl='1S'),
            dns.Record_NS('ns1.domain', ttl='2M'),
            dns.Record_NS('ns2.domain', ttl='3H'),
            dns.Record_SRV(257, 16383, 43690, 'some.other.place.fool', ttl='4D')
            ]
        }
    )

class ServerDNSTestCase(unittest.TestCase):
    """Test cases for DNS server and client."""
    
    def setUp(self):
        self.factory = server.DNSServerFactory([
            test_domain_com, reverse_domain, my_domain_com
        ], verbose=2)
        
        p = dns.DNSDatagramProtocol(self.factory)
        
        while 1:
            self.listenerTCP = reactor.listenTCP(0, self.factory, interface="127.0.0.1")
            port = self.listenerTCP.getHost()[2]

            try:
                self.listenerUDP = reactor.listenUDP(port, p, interface="127.0.0.1")
            except error.CannotListenError:
                self.listenerTCP.stopListening()
            else:
                break

        self.resolver = client.Resolver(servers=[('127.0.0.1', port)])


    def tearDown(self):
        self.listenerTCP.stopListening()
        self.listenerUDP.stopListening()


    def namesTest(self, d, r):
        self.response = None
        def setDone(response):
            self.response = response
        d.addBoth(setDone)
        
        while not self.response:
            reactor.iterate(0.1)

        if isinstance(self.response, failure.Failure):
            raise self.response
        
        results = justPayload(self.response)
        assert len(results) == len(r), "%s != %s" % (map(str, results), map(str, r))
        for rec in results:
            assert rec in r, "%s not in %s" % (rec, map(str, r))


    def testAddressRecord1(self):
        """Test simple DNS 'A' record queries"""
        self.namesTest(
            self.resolver.lookupAddress('test-domain.com'),
            [dns.Record_A('127.0.0.1', ttl=19283784)]
        )


    def testAddressRecord2(self):
        """Test DNS 'A' record queries with multiple answers"""
        self.namesTest(
            self.resolver.lookupAddress('host.test-domain.com'),
            [dns.Record_A('123.242.1.5', ttl=19283784), dns.Record_A('0.255.0.255', ttl=19283784)]
        )


    def testAdressRecord3(self):
        """Test DNS 'A' record queries with edge cases"""
        self.namesTest(
            self.resolver.lookupAddress('host-two.test-domain.com'),
            [dns.Record_A('255.255.255.254', ttl=19283784), dns.Record_A('0.0.0.0', ttl=19283784)]
        )


    def testAuthority(self):
        """Test DNS 'SOA' record queries"""
        self.namesTest(
            self.resolver.lookupAuthority('test-domain.com'),
            [soa_record]
        )


    def testMailExchangeRecord(self):
        """Test DNS 'MX' record queries"""
        self.namesTest(
            self.resolver.lookupMailExchange('test-domain.com'),
            [dns.Record_MX(10, 'host.test-domain.com', ttl=19283784)]
        )


    def testNameserver(self):
        """Test DNS 'NS' record queries"""
        self.namesTest(
            self.resolver.lookupNameservers('test-domain.com'),
            [dns.Record_NS('39.28.189.39', ttl=19283784)]
        )


    def testHINFO(self):
        """Test DNS 'HINFO' record queries"""
        self.namesTest(
            self.resolver.lookupHostInfo('test-domain.com'),
            [dns.Record_HINFO(os='Linux', cpu='A Fast One, Dontcha know', ttl=19283784)]
        )

    def testPTR(self):
        """Test DNS 'PTR' record queries"""
        self.namesTest(
            self.resolver.lookupPointer('123.93.84.28.in-addr.arpa'),
            [dns.Record_PTR('test.host-reverse.lookup.com', ttl=11193983)]
        )


    def testCNAME(self):
        """Test DNS 'CNAME' record queries"""
        self.namesTest(
            self.resolver.lookupCanonicalName('test-domain.com'),
            [dns.Record_CNAME('canonical.name.com', ttl=19283784)]
        )
 

    def testMB(self):
        """Test DNS 'MB' record queries"""
        self.namesTest(
            self.resolver.lookupMailBox('test-domain.com'),
            [dns.Record_MB('mailbox.test-domain.com', ttl=19283784)]
        )


    def testMG(self):
        """Test DNS 'MG' record queries"""
        self.namesTest(
            self.resolver.lookupMailGroup('test-domain.com'),
            [dns.Record_MG('mail.group.someplace', ttl=19283784)]
        )


    def testMR(self):
        """Test DNS 'MR' record queries"""
        self.namesTest(
            self.resolver.lookupMailRename('test-domain.com'),
            [dns.Record_MR('mail.redirect.or.whatever', ttl=19283784)]
        )


    def testMINFO(self):
        """Test DNS 'MINFO' record queries"""
        self.namesTest(
            self.resolver.lookupMailboxInfo('test-domain.com'),
            [dns.Record_MINFO(rmailbx='r mail box', emailbx='e mail box', ttl=19283784)]
        )


    def testSRV(self):
        """Test DNS 'SRV' record queries"""
        self.namesTest(
            self.resolver.lookupService('http.tcp.test-domain.com'),
            [dns.Record_SRV(257, 16383, 43690, 'some.other.place.fool', ttl=19283784)]
        )

    def testAFSDB(self):
        """Test DNS 'AFSDB' record queries"""
        self.namesTest(
            self.resolver.lookupAFSDatabase('test-domain.com'),
            [dns.Record_AFSDB(subtype=1, hostname='afsdb.test-domain.com', ttl=19283784)]
        )


    def testRP(self):
        """Test DNS 'RP' record queries"""
        self.namesTest(
            self.resolver.lookupResponsibility('test-domain.com'),
            [dns.Record_RP(mbox='whatever.i.dunno', txt='some.more.text', ttl=19283784)]
        )


    def testTXT(self):
        """Test DNS 'TXT' record queries"""
        self.namesTest(
            self.resolver.lookupText('test-domain.com'),
            [dns.Record_TXT('A First piece of Text', 'a SecoNd piece', ttl=19283784),
             dns.Record_TXT('Some more text, haha!  Yes.  \0  Still here?', ttl=19283784)]
        )


    def testWKS(self):
        """Test DNS 'WKS' record queries"""
        self.namesTest(
            self.resolver.lookupWellKnownServices('test-domain.com'),
            [dns.Record_WKS('12.54.78.12', socket.IPPROTO_TCP, '\x12\x01\x16\xfe\xc1\x00\x01', ttl=19283784)]
        )


    def testSomeRecordsWithTTLs(self):
        result_soa = copy.copy(my_soa)
        result_soa.ttl = my_soa.expire
        self.namesTest(
            self.resolver.lookupAllRecords('my-domain.com'),
            [result_soa,
             dns.Record_A('1.2.3.4', ttl='1S'),
             dns.Record_NS('ns1.domain', ttl='2M'),
             dns.Record_NS('ns2.domain', ttl='3H'),
             dns.Record_SRV(257, 16383, 43690, 'some.other.place.fool', ttl='4D')]
            )



    if IPv6:
        def testAAAA(self):
            """Test DNS 'AAAA' record queries (IPv6)"""
            self.namesTest(
                self.resolver.lookupIPV6Address('test-domain.com'),
                [dns.Record_AAAA('AF43:5634:1294:AFCB:56AC:48EF:34C3:01FF', ttl=19283784)]
            )
        
        def testA6(self):
            """Test DNS 'A6' record queries (IPv6)"""
            self.namesTest(
                self.resolver.lookupAddress6('test-domain.com'),
                [dns.Record_A6(0, 'ABCD::4321', '', ttl=19283784),
                 dns.Record_A6(12, '0:0069::0', 'some.network.tld', ttl=19283784),
                 dns.Record_A6(8, '0:5634:1294:AFCB:56AC:48EF:34C3:01FF', 'tra.la.la.net', ttl=19283784)]
             )



    def testZoneTransfer(self):
        """Test DNS 'AXFR' queries (Zone transfer)"""
        default_ttl = soa_record.expire
        results = [copy.copy(r) for r in reduce(operator.add, test_domain_com.records.values())]
        for r in results:
            if r.ttl is None:
                r.ttl = default_ttl            
        self.namesTest(
            self.resolver.lookupZone('test-domain.com').addCallback(lambda r: (r[0][:-1],)),
            results
        )

class HelperTestCase(unittest.TestCase):
    def testSerialGenerator(self):
        f = self.mktemp()
        a = authority.getSerial(f)
        for i in range(20):
            b = authority.getSerial(f)
            self.failUnless(a < b)
            a = b


class AXFRTest(unittest.TestCase):
    def setUp(self):
        self.results = None
        self.d = defer.Deferred()
        self.d.addCallback(self._gotResults)
        self.controller = client.AXFRController('fooby.com', self.d)

        self.soa = dns.RRHeader(name='fooby.com', type=dns.SOA, cls=dns.IN, ttl=86400, auth=False,
                                payload=dns.Record_SOA(mname='fooby.com',
                                                       rname='hooj.fooby.com',
                                                       serial=100,
                                                       refresh=200,
                                                       retry=300,
                                                       expire=400,
                                                       minimum=500,
                                                       ttl=600))

        self.records = [
            self.soa,
            dns.RRHeader(name='fooby.com', type=dns.NS, cls=dns.IN, ttl=700, auth=False,
                         payload=dns.Record_NS(name='ns.twistedmatrix.com', ttl=700)),

            dns.RRHeader(name='fooby.com', type=dns.MX, cls=dns.IN, ttl=700, auth=False,
                         payload=dns.Record_MX(preference=10, exchange='mail.mv3d.com', ttl=700)),

            dns.RRHeader(name='fooby.com', type=dns.A, cls=dns.IN, ttl=700, auth=False,
                         payload=dns.Record_A(address='64.123.27.105', ttl=700)),
            self.soa
            ]

    def _makeMessage(self):
        # hooray they all have the same message format
        return dns.Message(id=999, answer=1, opCode=0, recDes=0, recAv=1, auth=1, rCode=0, trunc=0, maxSize=0)

    def testBindAndTNamesStyle(self):
        # Bind style = One big single message
        m = self._makeMessage()
        m.queries = [dns.Query('fooby.com', dns.AXFR, dns.IN)]
        m.answers = self.records
        self.controller.messageReceived(m, None)
        self.assertEquals(self.results, self.records)

    def _gotResults(self, result):
        self.results = result

    def testDJBStyle(self):
        # DJB style = message per record
        records = self.records[:]
        while records:
            m = self._makeMessage()
            m.queries = [] # DJB *doesn't* specify any queries.. hmm..
            m.answers = [records.pop(0)]
            self.controller.messageReceived(m, None)
        self.assertEquals(self.results, self.records)

class HostsTestCase(unittest.TestCase):
    def setUp(self):
        f = open('EtcHosts', 'w')
        f.write('''
1.1.1.1    EXAMPLE EXAMPLE.EXAMPLETHING
1.1.1.2    HOOJY
::1        ip6thingy
''')
        f.close()
        self.resolver = hosts.Resolver('EtcHosts')

    def testGetHostByName(self):
        data = [('EXAMPLE', '1.1.1.1'),
                ('EXAMPLE.EXAMPLETHING', '1.1.1.1'),
                ('HOOJY', '1.1.1.2'),
                ]
        
        for name, ip in data:
            self.assertEquals(
                wait(self.resolver.getHostByName(name)),
                ip)

    def testLookupAddress(self):
        stuff = wait(self.resolver.lookupAddress('HOOJY'))
        self.assertEquals(stuff[0][0].payload.dottedQuad(), '1.1.1.2')

    def testIPv6(self):
        self.assertEquals(
            wait(self.resolver.lookupIPV6Address('ip6thingy')),
            '::1') #???

    testIPv6.skip = 'IPv6 support is not in our hosts resolver yet'

    def testNotImplemented(self):
        self.assertRaises(
            NotImplementedError,
            lambda: wait(self.resolver.lookupMailExchange('EXAMPLE')))

    def testQuery(self):
        self.assertEquals(
            wait(self.resolver.query(dns.Query('EXAMPLE')))[0][0].payload.dottedQuad(),
            '1.1.1.1')

    def testNotFound(self):
        self.assertRaises(
            dns.DomainError,
            wait, self.resolver.lookupAddress('foueoa'))
