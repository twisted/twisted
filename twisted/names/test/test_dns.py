# test-case-name: twisted.names.test.test_dns
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for twisted.names.dns.
"""

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from twisted.internet import address
from twisted.trial import unittest
from twisted.names import dns

class RoundtripDNSTestCase(unittest.TestCase):
    """Encoding and then decoding various objects."""

    names = ["example.org", "go-away.fish.tv", "23strikesback.net"]

    def testName(self):
        for n in self.names:
            # encode the name
            f = StringIO()
            dns.Name(n).encode(f)

            # decode the name
            f.seek(0, 0)
            result = dns.Name()
            result.decode(f)
            self.assertEquals(result.name, n)

    def testQuery(self):
        for n in self.names:
            for dnstype in range(1, 17):
                for dnscls in range(1, 5):
                    # encode the query
                    f = StringIO()
                    dns.Query(n, dnstype, dnscls).encode(f)

                    # decode the result
                    f.seek(0, 0)
                    result = dns.Query()
                    result.decode(f)
                    self.assertEquals(result.name.name, n)
                    self.assertEquals(result.type, dnstype)
                    self.assertEquals(result.cls, dnscls)

    def testRR(self):
        # encode the RR
        f = StringIO()
        dns.RRHeader("test.org", 3, 4, 17).encode(f)

        # decode the result
        f.seek(0, 0)
        result = dns.RRHeader()
        result.decode(f)
        self.assertEquals(str(result.name), "test.org")
        self.assertEquals(result.type, 3)
        self.assertEquals(result.cls, 4)
        self.assertEquals(result.ttl, 17)


    def testResources(self):
        names = (
            "this.are.test.name",
            "will.compress.will.this.will.name.will.hopefully",
            "test.CASE.preSErVatIOn.YeAH",
            "a.s.h.o.r.t.c.a.s.e.t.o.t.e.s.t",
            "singleton"
        )
        for s in names:
            f = StringIO()
            dns.SimpleRecord(s).encode(f)
            f.seek(0, 0)
            result = dns.SimpleRecord()
            result.decode(f)
            self.assertEquals(str(result.name), s)

    def testHashable(self):
        records = [
            dns.Record_NS, dns.Record_MD, dns.Record_MF, dns.Record_CNAME,
            dns.Record_MB, dns.Record_MG, dns.Record_MR, dns.Record_PTR,
            dns.Record_DNAME, dns.Record_A, dns.Record_SOA, dns.Record_NULL,
            dns.Record_WKS, dns.Record_SRV, dns.Record_AFSDB, dns.Record_RP,
            dns.Record_HINFO, dns.Record_MINFO, dns.Record_MX, dns.Record_TXT,
            dns.Record_AAAA, dns.Record_A6
        ]

        for k in records:
            k1, k2 = k(), k()
            hk1 = hash(k1)
            hk2 = hash(k2)
            self.assertEquals(hk1, hk2, "%s != %s (for %s)" % (hk1,hk2,k))



class MessageTestCase(unittest.TestCase):
    def testEmptyMessage(self):
        """
        Test that a message which has been truncated causes an EOFError to
        be raised when it is parsed.
        """
        msg = dns.Message()
        self.assertRaises(EOFError, msg.fromStr, '')


    def testEmptyQuery(self):
        """
        Test that bytes representing an empty query message can be decoded
        as such.
        """
        msg = dns.Message()
        msg.fromStr(
            '\x01\x00' # Message ID
            '\x00' # answer bit, opCode nibble, auth bit, trunc bit, recursive bit
            '\x00' # recursion bit, empty bit, empty bit, empty bit, response code nibble
            '\x00\x00' # number of queries
            '\x00\x00' # number of answers
            '\x00\x00' # number of authorities
            '\x00\x00' # number of additionals
            )
        self.assertEquals(msg.id, 256)
        self.failIf(msg.answer, "Message was not supposed to be an answer.")
        self.assertEquals(msg.opCode, dns.OP_QUERY)
        self.failIf(msg.auth, "Message was not supposed to be authoritative.")
        self.failIf(msg.trunc, "Message was not supposed to be truncated.")
        self.assertEquals(msg.queries, [])
        self.assertEquals(msg.answers, [])
        self.assertEquals(msg.authority, [])
        self.assertEquals(msg.additional, [])


    def testNULL(self):
        bytes = ''.join([chr(i) for i in range(256)])
        rec = dns.Record_NULL(bytes)
        rr = dns.RRHeader('testname', dns.NULL, payload=rec)
        msg1 = dns.Message()
        msg1.answers.append(rr)
        s = StringIO()
        msg1.encode(s)
        s.seek(0, 0)
        msg2 = dns.Message()
        msg2.decode(s)

        self.failUnless(isinstance(msg2.answers[0].payload, dns.Record_NULL))
        self.assertEquals(msg2.answers[0].payload.payload, bytes)



class TestController(object):
    """
    Pretend to be a DNS query processor for a DNSDatagramProtocol.
    """
    def __init__(self):
        self.messages = []


    def messageReceived(self, msg, proto, addr):
        self.messages.append((msg, proto, addr))



class DatagramProtocolTestCase(unittest.TestCase):
    """
    Test various aspects of DNSDatagramProtocol.
    """

    def testTruncatedPacket(self):
        """
        Test that when a short datagram is received, datagramReceived does
        not raise an exception while processing it.
        """
        controller = TestController()
        proto = dns.DNSDatagramProtocol(controller)
        proto.datagramReceived('', address.IPv4Address('UDP', '127.0.0.1', 12345))
        self.assertEquals(controller.messages, [])
