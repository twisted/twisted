
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
Tests for twisted.protocols.dns.
"""

import socket

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from twisted.trial import unittest
from twisted.protocols import dns
from twisted.test.test_names import IPv6


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
            dns.Record_HINFO, dns.Record_MINFO, dns.Record_MX, dns.Record_TXT
        ]
        
        if IPv6:
            records.extend([dns.Record_AAAA, dns.Record_A6])

        for k in records:
            k1, k2 = k(), k()
            hk1 = hash(k1)
            hk2 = hash(k2)
            self.assertEquals(hk1, hk2, "%s != %s (for %s)" % (hk1,hk2,k))
