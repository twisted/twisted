
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
Asynchronous client DNS

API Stability: Unstable

Future plans: Proper nameserver acquisition on Windows/MacOS,
  caching, other lookup* methods.

@author: U{Jp Calderone <exarkun@twistedmatrix.com>}
"""


# System imports
import struct

# Twisted imports
from twisted.python.runtime import platform
from twisted.internet import defer, protocol
from twisted.python import log
from twisted.protocols import dns

class Resolver:
    index = 0

    pending = None
    connections = None

    def __init__(self, resolv = None, servers = None):
        """
        @type servers: C{list} of C{str} or C{None}
        @param servers: If not None, interpreted as a list of addresses of
        domain name servers to attempt to use for this lookup.  Addresses
        should be in dotted-quad form.  If specified, overrides C{resolv}.
        
        @type resolv: C{str}
        @param resolv: Filename to read and parse as a resolver(5)
        configuration file.
        """
        if servers is None:
            self.servers = []
        else:
            self.servers = servers
        
        if resolv:
            self.parseConfig(resolv)
        
        if not len(self.servers):
            raise ValueError, "No nameservers specified"
        
        from twisted.internet import reactor
        self.protocol = dns.DNSClientProtocol(self)
        reactor.listenUDP(0, self.protocol, maxPacketSize=512)

        self.factory = DNSClientFactory(self)
        self.connections = []
        self.pending = []


    def parseConfig(self, conf):
        lines = file(conf).readlines()
        for l in lines:
            l = l.strip()
            if l.startswith('nameserver'):
                self.servers.append(l.split()[1])
                #log.msg("Resolver added %s to server list" % (self.servers[-1],))


    def pickServer(self):
        """
        Return the address of a namserver.
        
        TODO: Weight servers for response time so faster ones can be
        preferred.
        """
        self.index = (self.index + 1) % len(self.servers)
        return self.servers[self.index]


    def connectionMade(self, protocol):
        self.connections.append(protocol)
        for (d, q) in self.pending:
            protocol.query(q).chainDeferred(d)
        del self.pending[:]


    def queryUDP(self, *queries):
        """
        Make a number of DNS queries via UDP.

        @type queries: Any non-zero number of C{dns.Query} instances
        @param queries: The queries to make.
        
        @rtype: C{Deferred}
        """
        return self.protocol.query((self.pickServer(), dns.PORT), queries)


    def queryTCP(self, *queries):
        """
        Make a number of DNS queries via TCP.

        @type queries: Any non-zero number of C{dns.Query} instances
        @param queries: The queries to make.
        
        @rtype: C{Deferred}
        """
        if not len(self.connections):
            from twisted.internet import reactor
            reactor.connectTCP(self.pickServer(), dns.PORT, self.factory)
            self.pending.append((defer.Deferred(), queries))
            return self.pending[-1][0]
        else:
            return self.connections[0].query(queries)


    def filterAnswers(self, type):
        def getOfType(message, type=type):
            if message.trunc:
                return self.queryTCP(message.queries).addCallback(self.filterAnswers(type))
            else:
                return [n.payload for n in message.answers if n.type == type]
        return getOfType


    def lookupAddress(self, name):
        return self.queryUDP(dns.Query(name, dns.A, dns.IN)).addCallback(self.filterAnswers(dns.A))


    def lookupMailExchange(self, name):
        return self.queryUDP(dns.Query(name, dns.MX, dns.IN)).addCallback(self.filterAnswers(dns.MX))


    def lookupNameservers(self, name):
        return self.queryUDP(dns.Query(name, dns.NS, dns.IN)).addCallback(self.filterAnswers(dns.NS))


class ThreadedResolver(Resolver):
    def lookup(self, name, type = dns.ALL_RECORDS, cls = dns.ANY):
        assert type == dns.A and cls == dns.IN, \
            "No support for query types other than A IN"
        return defer.deferToThread(socket.gethostbyname, name)


class DNSClientFactory(protocol.ClientFactory):
    def __init__(self, controller):
        self.controller = controller
    

    def clientConnectionLost(self, connector, reason):
        print connector, reason


    def buildProtocol(self, addr):
        p = dns.TCPDNSClientProtocol(self.controller)
        p.factory = self
        return p


try:
    theResolver
except NameError:
    if platform.getType() == 'posix':
        theResolver = Resolver('/etc/resolv.conf')
    else:
        theResolver = ThreadedResolver()

    lookupAddress = theResolver.lookupAddress
    lookupMailExchange = theResolver.lookupMailExchange
    lookupNameservers = theResolver.lookupNameservers
