
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
import sys
from pyunit import unittest

from twisted.internet import reactor, protocol
from twisted.names import client, server
from twisted.protocols import dns
from twisted.python import log


PORT = 2053

class NoFileAuthority:
    def __init__(self, soa, records):
        self.soa, self.records = soa, records


class ServerDNSTestCase(unittest.DeferredTestCase):
    """Test cases for DNS server and client."""
    
    def setUp(self):
        self.factory = server.DNSServerFactory([
            NoFileAuthority(
                soa = dns.Record_SOA(
                    mname = 'test-domain.com',
                    rname = 'root.test-domain.com',
                    serial = 100,
                    refresh = 1234,
                    minimum = 7654,
                    expire = 19283784,
                    retry = 15
                ),
                records = {
                    'test-domain.com': [
                        dns.Record_A('127.0.0.1'),
                        dns.Record_NS('39.28.189.39'),
                        dns.Record_MX(10, 'host.test-domain.com'),
                        dns.Record_HINFO(os='Linux', cpu='A Fast One, Dontcha know')
                    ],
                    'host.test-domain.com': [
                        dns.Record_A('123.242.1.5'),
                        dns.Record_A('0.255.0.255')
                    ],
                    'host-two.test-domain.com': [
#
#  Python bug
#                        dns.Record_A('255.255.255.255'),
#
                        dns.Record_A('255.255.255.254'),
                        dns.Record_A('0.0.0.0')
                    ]
                }
            )
        ])
        
        from twisted.internet import reactor
        reactor.listenTCP(PORT, self.factory)
        
        p = dns.DNSClientProtocol(self.factory)
        reactor.listenUDP(PORT, p)
        
        self.resolver = client.Resolver(servers=[('127.0.0.1', PORT)])


    def tearDown(self):
        pass


    def testAddressRecord(self):
        r = self.resolver

        self.deferredFailUnlessEqual(
            r.lookupAddress('test-domain.com'),
            [dns.Record_A('127.0.0.1')]
        )
        self.deferredFailUnlessEqual(
            r.lookupAddress('host.test-domain.com'),
            [dns.Record_A('123.242.1.5'), dns.Record_A('0.255.0.255')]
        )
        self.deferredFailUnlessEqual(
            r.lookupAddress('host-two.test-domain.com'),
            [dns.Record_A('255.255.255.254'), dns.Record_A('0.0.0.0')]
        )

        from twisted.internet import reactor
        for i in range(10):
            reactor.iterate(0.1)


    def testMailExchangeRecord(self):
        r = self.resolver
        self.deferredFailUnlessEqual(
            r.lookupMailExchange('test-domain.com'),
            [dns.Record_MX(10, 'host.test-domain.com')]
        )

        from twisted.internet import reactor
        for i in range(10):
            reactor.iterate(0.1)


    def testNameserver(self):
        r = self.resolver
        self.deferredFailUnlessEqual(
            r.lookupNameserver('test-domain.com'),
            [dns.Record_NS('39.28.189.39')]
        )

        from twisted.internet import reactor
        for i in range(10):
            reactor.iterate(0.1)
