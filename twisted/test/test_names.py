
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

from pyunit import unittest

from twisted.names import dns
from twisted.internet import main, udp
from twisted.protocols import protocol

# hack until moshez lets me set the port for queries
dns.DNS_PORT = 2053


class DNSFactory(protocol.ServerFactory):

    protocol = dns.DNS
    
    def __init__(self):
        self.boss = dns.DNSServerBoss()
    
    
class DNSTestCase(unittest.TestCase):
    """Test cases for DNS server and client."""
    
    def testServer(self):
        factory = DNSFactory()
        factory.boss.addDomain("example.foo", dns.SimpleDomain("example.foo", "1.1.1.1"))
        p = udp.Port(2053, factory)
        p.startListening()
        
        resolver = dns.Resolver(["localhost"])
        d = resolver.resolve("example.foo")
        d.addCallback(self.tS_result).addErrback(self.tS_error)
        d.arm()
        main.iterate()
        main.iterate()
        main.iterate()
        main.iterate()
        
        self.assertEquals(self.gotAnswer, 1)
        del self.gotAnswer
        p.loseConnection()
        main.iterate()
    
    def tS_result(self, result):
        self.assertEquals(result, "1.1.1.1")
        self.gotAnswer = 1
    
    def tS_error(self, error):
        raise RuntimeError, error
    
