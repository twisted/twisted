# test-case-name: twisted.names.test.test_dns
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for twisted.names.dns.
"""

import socket

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

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


class Encoding(unittest.TestCase):
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

