
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

from pyunit import unittest
from StringIO import StringIO

from twisted.protocols import dns


class RountripDNSTestCase(unittest.TestCase):
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
        dns.RR("test.org", 3, 4, 17, "foobar").encode(f)
        
        # decode the result
        f.seek(0, 0)
        result = dns.RR()
        result.decode(f)
        self.assertEquals(result.name.name, "test.org")
        self.assertEquals(result.type, 3)
        self.assertEquals(result.cls, 4)
        self.assertEquals(result.ttl, 17)
        self.assertEquals(result.data, "foobar")

