
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
Test cases for Twisted.names' root resolver.
"""

from twisted.flow import flow
from twisted.internet import defer
from twisted.protocols import dns
from twisted.names import root
from twisted.trial import unittest

# We import t.names.client, so we need this hack
from twisted.test import test_names

class FakeProtocol:
    def __init__(self, responses):
        self.args = []
        self.responses = responses
    def query(self, *args):
        if not self.responses:
            import pdb; pdb.Pdb().set_trace()
        self.args.append(args)
        return defer.succeed(self.responses.pop(0))

class RootResolverTestCase(unittest.TestCase):
    def setUp(self):
        self.msgs = []
        self.p = FakeProtocol(self.msgs)

    def testSingleLevel(self):
        # Just look up domain.tld
        host = 'domain.tld'
        
        m = dns.Message()
        rr = dns.RRHeader('tld', dns.NS, payload=dns.Record_NS(host))
        m.answers.append(rr)
        self.msgs.append(m)
        m = dns.Message()
        rr = dns.RRHeader(host, dns.NS, payload=dns.Record_NS(host))
        m.answers.append(rr)
        self.msgs.append(m)
        
        d = root.discoverAuthority(host, ['root.server'], p=self.p)
        r = unittest.deferredResult(flow.Deferred(d))

        self.assertEquals(len(r), 2)
        self.assertEquals(r[1], 'root.server')
        
        m = r[0]
        self.assertEquals(len(m.answers), 1)
        self.assertEquals(len(m.additional), 0)
        self.assertEquals(len(m.authority), 0)
        
        a = m.answers[0]
        self.assertEquals(a, rr)

        a = self.p.args
        self.assertEquals(len(a), 2)

        r = a[0]
        self.assertEquals(len(r), 3)
        self.assertEquals(r[1], [dns.Query('tld.', dns.NS)])
        
        r = a[1]
        self.assertEquals(len(r), 3)
        self.assertEquals(r[1], [dns.Query('domain.tld', dns.NS)])

    def testMultiLevel(self):
        host = 'big.long.host.name.with.many.many.many.different.parts.tld'

        dots = host.count('.')
        for i in range(dots + 1):
            m = dns.Message()
            p = host.split('.', dots - i)
            rr = dns.RRHeader(p[-1], dns.NS, payload=dns.Record_NS('.'.join(p[-2:])))
            m.answers.append(rr)
            self.msgs.append(m)
        
        d = root.discoverAuthority(host, ['root.server'], p=self.p)
        r = unittest.deferredResult(flow.Deferred(d))
        
        self.assertEquals(len(r), 2)
        self.assertEquals(r[1], 'root.server')
        
        m = r[0]
        self.assertEquals(len(m.answers), 1)
        self.assertEquals(len(m.additional), 0)
        self.assertEquals(len(m.authority), 0)
        
        a = m.answers[0]
        self.assertEquals(a, rr)
        
        r = self.p.args[0]
        self.assertEquals(len(r), 3)
        self.assertEquals(r[1], [dns.Query('tld.', dns.NS)])
        for i in range(1, dots + 1):
            r = self.p.args[i]
            self.assertEquals(len(r), 3)
            self.assertEquals(r[1], [dns.Query(host.split('.', dots - i)[-1], dns.NS)])
            
