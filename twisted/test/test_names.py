
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

from twisted.internet import reactor, protocol, defer
from twisted.names import client, server
from twisted.protocols import dns
from twisted.python import log


gotResponse = 0
PORT = 2053

def setDone(message):
    global gotResponse
    gotResponse = 1
    return message

def getPayload(message):
    global gotResponse
    gotResponse = 1
    return [answer.payload for answer in message.answers]


class NoFileAuthority:
    def __init__(self, soa, records):
        self.soa, self.records = soa, records

soa_record = dns.Record_SOA(
                    mname = 'test-domain.com',
                    rname = 'root.test-domain.com',
                    serial = 100,
                    refresh = 1234,
                    minimum = 7654,
                    expire = 19283784,
                    retry = 15
                )


class ServerDNSTestCase(unittest.DeferredTestCase):
    """Test cases for DNS server and client."""
    
    def setUp(self):
        self.factory = server.DNSServerFactory([
            NoFileAuthority(
                soa = soa_record,
                records = {
                    'test-domain.com': [
                        dns.Record_A('127.0.0.1'),
                        dns.Record_NS('39.28.189.39'),
                        dns.Record_MX(10, 'host.test-domain.com'),
                        dns.Record_HINFO(os='Linux', cpu='A Fast One, Dontcha know'),
                        soa_record
                    ],
                    'host.test-domain.com': [
                        dns.Record_A('123.242.1.5'),
                        dns.Record_A('0.255.0.255'),
                    ],
                    'host-two.test-domain.com': [
#
#  Python bug
#                        dns.Record_A('255.255.255.255'),
#
                        dns.Record_A('255.255.255.254'),
                        dns.Record_A('0.0.0.0')
                    ],
                    '123.93.84.28.in-addr.arpa': [
                        dns.Record_PTR('test.host-reverse.lookup.com')
                    ]
                }
            )
        ], verbose=2)
        
        from twisted.internet import reactor
        self.listenerTCP = reactor.listenTCP(PORT, self.factory)
        
        p = dns.DNSClientProtocol(self.factory)
        self.listenerUDP = reactor.listenUDP(PORT, p)
        
        self.resolver = client.Resolver(servers=[('127.0.0.1', PORT)])


    def tearDown(self):
        self.listenerTCP.stopListening()
        self.listenerUDP.stopListening()


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


    def testAuthority(self):
        global gotResponse
        gotResponse = 0

        r = self.resolver
        self.deferredFailUnlessEqual(
            r.queryUDP([dns.Query('test-domain.com', dns.SOA, dns.IN)]).addCallback(getPayload),
            [soa_record]
        )
        
        while not gotResponse:
            reactor.iterate(0.05)


    def testMailExchangeRecord(self):
        global gotResponse
        gotResponse = 0

        r = self.resolver
        self.deferredFailUnlessEqual(
            r.lookupMailExchange('test-domain.com').addCallback(setDone),
            [dns.Record_MX(10, 'host.test-domain.com')]
        )

        while not gotResponse:
            reactor.iterate(0.05)


    def testNameserver(self):
        global gotResponse
        gotResponse = 0

        r = self.resolver
        self.deferredFailUnlessEqual(
            r.lookupNameservers('test-domain.com').addCallback(setDone),
            [dns.Record_NS('39.28.189.39')]
        )

        while not gotResponse:
            reactor.iterate(0.05)


    # Yea, second class citizens all the way
    def testOther(self):
        global gotResponse
        gotResponse = 0
        
        r = self.resolver
        self.deferredFailUnlessEqual(
            r.queryUDP([dns.Query('test-domain.com', dns.HINFO, dns.IN)]).addCallback(getPayload),
            [dns.Record_HINFO(os='Linux', cpu='A Fast One, Dontcha know')]
        )
        
        self.deferredFailUnlessEqual(
            r.queryUDP([dns.Query('123.93.84.28.in-addr.arpa', dns.HINFO, dns.IN)]).addCallback(getPayload),
            [dns.Record_PTR('test.host-reverse.lookup.com')]
        )

        while not gotResponse:
            reactor.iterate(0.05)
