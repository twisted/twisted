# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.names.server}.
"""

import socket, operator, copy

from twisted.internet import error, reactor
from twisted.names.dns import Message
from twisted.names import client, dns, server
from twisted.python.compat import reduce
from twisted.python import failure
from twisted.trial import unittest

from twisted.names.test.test_names import (
    test_domain_com, reverse_domain, my_domain_com, my_soa, soa_record)



def justPayload(results):
    return [r.payload for r in results[0]]



class ServerDNSTestCase(unittest.TestCase):
    """
    Test cases for DNS server and client.
    """

    def setUp(self):
        self.factory = server.DNSServerFactory([
            test_domain_com, reverse_domain, my_domain_com
        ], verbose=2)

        p = dns.DNSDatagramProtocol(self.factory)

        while 1:
            listenerTCP = reactor.listenTCP(0, self.factory, interface="127.0.0.1")
            # It's simpler to do the stop listening with addCleanup,
            # even though we might not end up using this TCP port in
            # the test (if the listenUDP below fails).  Cleaning up
            # this TCP port sooner than "cleanup time" would mean
            # adding more code to keep track of the Deferred returned
            # by stopListening.
            self.addCleanup(listenerTCP.stopListening)
            port = listenerTCP.getHost().port

            try:
                listenerUDP = reactor.listenUDP(port, p, interface="127.0.0.1")
            except error.CannotListenError:
                pass
            else:
                self.addCleanup(listenerUDP.stopListening)
                break

        self.listenerTCP = listenerTCP
        self.listenerUDP = listenerUDP
        self.resolver = client.Resolver(servers=[('127.0.0.1', port)])


    def tearDown(self):
        """
        Clean up any server connections associated with the
        L{DNSServerFactory} created in L{setUp}
        """
        # It'd be great if DNSServerFactory had a method that
        # encapsulated this task.  At least the necessary data is
        # available, though.
        for conn in self.factory.connections[:]:
            conn.transport.loseConnection()


    def namesTest(self, d, r):
        self.response = None
        def setDone(response):
            self.response = response

        def checkResults(ignored):
            if isinstance(self.response, failure.Failure):
                raise self.response
            results = justPayload(self.response)
            assert len(results) == len(r), "%s != %s" % (map(str, results), map(str, r))
            for rec in results:
                assert rec in r, "%s not in %s" % (rec, map(str, r))

        d.addBoth(setDone)
        d.addCallback(checkResults)
        return d

    def testAddressRecord1(self):
        """Test simple DNS 'A' record queries"""
        return self.namesTest(
            self.resolver.lookupAddress('test-domain.com'),
            [dns.Record_A('127.0.0.1', ttl=19283784)]
        )


    def testAddressRecord2(self):
        """Test DNS 'A' record queries with multiple answers"""
        return self.namesTest(
            self.resolver.lookupAddress('host.test-domain.com'),
            [dns.Record_A('123.242.1.5', ttl=19283784), dns.Record_A('0.255.0.255', ttl=19283784)]
        )


    def testAddressRecord3(self):
        """Test DNS 'A' record queries with edge cases"""
        return self.namesTest(
            self.resolver.lookupAddress('host-two.test-domain.com'),
            [dns.Record_A('255.255.255.254', ttl=19283784), dns.Record_A('0.0.0.0', ttl=19283784)]
        )


    def testAuthority(self):
        """Test DNS 'SOA' record queries"""
        return self.namesTest(
            self.resolver.lookupAuthority('test-domain.com'),
            [soa_record]
        )


    def testMailExchangeRecord(self):
        """Test DNS 'MX' record queries"""
        return self.namesTest(
            self.resolver.lookupMailExchange('test-domain.com'),
            [dns.Record_MX(10, 'host.test-domain.com', ttl=19283784)]
        )


    def testNameserver(self):
        """Test DNS 'NS' record queries"""
        return self.namesTest(
            self.resolver.lookupNameservers('test-domain.com'),
            [dns.Record_NS('39.28.189.39', ttl=19283784)]
        )


    def testHINFO(self):
        """Test DNS 'HINFO' record queries"""
        return self.namesTest(
            self.resolver.lookupHostInfo('test-domain.com'),
            [dns.Record_HINFO(os='Linux', cpu='A Fast One, Dontcha know', ttl=19283784)]
        )

    def testPTR(self):
        """Test DNS 'PTR' record queries"""
        return self.namesTest(
            self.resolver.lookupPointer('123.93.84.28.in-addr.arpa'),
            [dns.Record_PTR('test.host-reverse.lookup.com', ttl=11193983)]
        )


    def testCNAME(self):
        """Test DNS 'CNAME' record queries"""
        return self.namesTest(
            self.resolver.lookupCanonicalName('test-domain.com'),
            [dns.Record_CNAME('canonical.name.com', ttl=19283784)]
        )

    def testCNAMEAdditional(self):
        """Test additional processing for CNAME records"""
        return self.namesTest(
        self.resolver.lookupAddress('cname.test-domain.com'),
        [dns.Record_CNAME('test-domain.com', ttl=19283784), dns.Record_A('127.0.0.1', ttl=19283784)]
    )

    def testMB(self):
        """Test DNS 'MB' record queries"""
        return self.namesTest(
            self.resolver.lookupMailBox('test-domain.com'),
            [dns.Record_MB('mailbox.test-domain.com', ttl=19283784)]
        )


    def testMG(self):
        """Test DNS 'MG' record queries"""
        return self.namesTest(
            self.resolver.lookupMailGroup('test-domain.com'),
            [dns.Record_MG('mail.group.someplace', ttl=19283784)]
        )


    def testMR(self):
        """Test DNS 'MR' record queries"""
        return self.namesTest(
            self.resolver.lookupMailRename('test-domain.com'),
            [dns.Record_MR('mail.redirect.or.whatever', ttl=19283784)]
        )


    def testMINFO(self):
        """Test DNS 'MINFO' record queries"""
        return self.namesTest(
            self.resolver.lookupMailboxInfo('test-domain.com'),
            [dns.Record_MINFO(rmailbx='r mail box', emailbx='e mail box', ttl=19283784)]
        )


    def testSRV(self):
        """Test DNS 'SRV' record queries"""
        return self.namesTest(
            self.resolver.lookupService('http.tcp.test-domain.com'),
            [dns.Record_SRV(257, 16383, 43690, 'some.other.place.fool', ttl=19283784)]
        )

    def testAFSDB(self):
        """Test DNS 'AFSDB' record queries"""
        return self.namesTest(
            self.resolver.lookupAFSDatabase('test-domain.com'),
            [dns.Record_AFSDB(subtype=1, hostname='afsdb.test-domain.com', ttl=19283784)]
        )


    def testRP(self):
        """Test DNS 'RP' record queries"""
        return self.namesTest(
            self.resolver.lookupResponsibility('test-domain.com'),
            [dns.Record_RP(mbox='whatever.i.dunno', txt='some.more.text', ttl=19283784)]
        )


    def testTXT(self):
        """Test DNS 'TXT' record queries"""
        return self.namesTest(
            self.resolver.lookupText('test-domain.com'),
            [dns.Record_TXT('A First piece of Text', 'a SecoNd piece', ttl=19283784),
             dns.Record_TXT('Some more text, haha!  Yes.  \0  Still here?', ttl=19283784)]
        )


    def test_spf(self):
        """
        L{DNSServerFactory} can serve I{SPF} resource records.
        """
        return self.namesTest(
            self.resolver.lookupSenderPolicy('test-domain.com'),
            [dns.Record_SPF('v=spf1 mx/30 mx:example.org/30 -all', ttl=19283784),
            dns.Record_SPF('v=spf1 +mx a:\0colo', '.example.com/28 -all not valid', ttl=19283784)]
        )


    def testWKS(self):
        """Test DNS 'WKS' record queries"""
        return self.namesTest(
            self.resolver.lookupWellKnownServices('test-domain.com'),
            [dns.Record_WKS('12.54.78.12', socket.IPPROTO_TCP, '\x12\x01\x16\xfe\xc1\x00\x01', ttl=19283784)]
        )


    def testSomeRecordsWithTTLs(self):
        result_soa = copy.copy(my_soa)
        result_soa.ttl = my_soa.expire
        return self.namesTest(
            self.resolver.lookupAllRecords('my-domain.com'),
            [result_soa,
             dns.Record_A('1.2.3.4', ttl='1S'),
             dns.Record_NS('ns1.domain', ttl='2M'),
             dns.Record_NS('ns2.domain', ttl='3H'),
             dns.Record_SRV(257, 16383, 43690, 'some.other.place.fool', ttl='4D')]
            )


    def testAAAA(self):
        """Test DNS 'AAAA' record queries (IPv6)"""
        return self.namesTest(
            self.resolver.lookupIPV6Address('test-domain.com'),
            [dns.Record_AAAA('AF43:5634:1294:AFCB:56AC:48EF:34C3:01FF', ttl=19283784)]
        )

    def testA6(self):
        """Test DNS 'A6' record queries (IPv6)"""
        return self.namesTest(
            self.resolver.lookupAddress6('test-domain.com'),
            [dns.Record_A6(0, 'ABCD::4321', '', ttl=19283784),
             dns.Record_A6(12, '0:0069::0', 'some.network.tld', ttl=19283784),
             dns.Record_A6(8, '0:5634:1294:AFCB:56AC:48EF:34C3:01FF', 'tra.la.la.net', ttl=19283784)]
         )


    def test_zoneTransfer(self):
        """
        Test DNS 'AXFR' queries (Zone transfer)
        """
        default_ttl = soa_record.expire
        results = [copy.copy(r) for r in reduce(operator.add, test_domain_com.records.values())]
        for r in results:
            if r.ttl is None:
                r.ttl = default_ttl
        return self.namesTest(
            self.resolver.lookupZone('test-domain.com').addCallback(lambda r: (r[0][:-1],)),
            results
        )


    def testSimilarZonesDontInterfere(self):
        """Tests that unrelated zones don't mess with each other."""
        return self.namesTest(
            self.resolver.lookupAddress("anothertest-domain.com"),
            [dns.Record_A('1.2.3.4', ttl=19283784)]
        )


    def test_NAPTR(self):
        """
        Test DNS 'NAPTR' record queries.
        """
        return self.namesTest(
            self.resolver.lookupNamingAuthorityPointer('test-domain.com'),
            [dns.Record_NAPTR(100, 10, "u", "sip+E2U",
                              "!^.*$!sip:information@domain.tld!",
                              ttl=19283784)])



class DNSServerFactoryTests(unittest.TestCase):
    """
    Tests for L{server.DNSServerFactory}.
    """
    def _messageReceivedTest(self, methodName, message):
        """
        Assert that the named method is called with the given message when
        it is passed to L{DNSServerFactory.messageReceived}.
        """
        # Make it appear to have some queries so that
        # DNSServerFactory.allowQuery allows it.
        message.queries = [None]

        receivedMessages = []
        def fakeHandler(message, protocol, address):
            receivedMessages.append((message, protocol, address))

        class FakeProtocol(object):
            def writeMessage(self, message):
                pass

        protocol = FakeProtocol()
        factory = server.DNSServerFactory(None)
        setattr(factory, methodName, fakeHandler)
        factory.messageReceived(message, protocol)
        self.assertEqual(receivedMessages, [(message, protocol, None)])


    def test_notifyMessageReceived(self):
        """
        L{DNSServerFactory.messageReceived} passes messages with an opcode
        of C{OP_NOTIFY} on to L{DNSServerFactory.handleNotify}.
        """
        # RFC 1996, section 4.5
        opCode = 4
        self._messageReceivedTest('handleNotify', Message(opCode=opCode))


    def test_updateMessageReceived(self):
        """
        L{DNSServerFactory.messageReceived} passes messages with an opcode
        of C{OP_UPDATE} on to L{DNSServerFactory.handleOther}.

        This may change if the implementation ever covers update messages.
        """
        # RFC 2136, section 1.3
        opCode = 5
        self._messageReceivedTest('handleOther', Message(opCode=opCode))


    def test_connectionTracking(self):
        """
        The C{connectionMade} and C{connectionLost} methods of
        L{DNSServerFactory} cooperate to keep track of all
        L{DNSProtocol} objects created by a factory which are
        connected.
        """
        protoA, protoB = object(), object()
        factory = server.DNSServerFactory()
        factory.connectionMade(protoA)
        self.assertEqual(factory.connections, [protoA])
        factory.connectionMade(protoB)
        self.assertEqual(factory.connections, [protoA, protoB])
        factory.connectionLost(protoA)
        self.assertEqual(factory.connections, [protoB])
        factory.connectionLost(protoB)
        self.assertEqual(factory.connections, [])
