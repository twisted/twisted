
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

Stability: Unstable

Future plans: Proper nameserver acquisition on Windows/MacOS,
  caching, other lookup* methods.

@author: U{Jp Calderone <exarkun@twistedmatrix.com>}
"""


# System imports
import struct

# Twisted imports
from twisted.internet import defer
from twisted.python import log
from twisted.protocols import dns

class Resolver:
    index = 0

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


    def parseConfig(self, conf):
        lines = file(conf).readlines()
        for l in lines:
            l = l.strip()
            if l.startswith('nameserver'):
                self.servers.append(l.split()[1])
                #log.msg("Resolver added %s to server list" % (self.servers[-1],))


    def lookup(self, name, type = dns.ALL_RECORDS, cls = dns.ANY):
        """
        @type name: C{str}
        @param name: The hostname to look up
        
        @type type: C{int}
        @param type: Specify the query type.  Must be one of:
        
        A NS MD MF CNAME SOA MB MG MR NULL MKS PTR
        HINFO MX TXTAFRX MAILB MAILA ALL_RECORDS
        
        @type cls: C{int}
        @param cls: Specify the query class.  Must be one of:
        
        IN CS CH HS ANY
        
        @rtype: C{Deferred}
        """
        p = dns.DNSClientProtocol()

        from twisted.internet import reactor
        reactor.connectUDP(self.servers[self.index], 53, p)
        self.index = (self.index + 1) % len(self.servers)
        return p.query(name, type, cls)


    def filterAnswers(self, type):
        def getOfType(message, type=type):
            return [n.data for n in message.answers if n.type == type]
        return getOfType


    def lookupAddress(self, name):
        return self.lookup(name, dns.A, dns.IN).addCallback(self.filterAnswers(dns.A))


    def lookupMailExchange(self, name):
        return self.lookup(name, dns.MX, dns.IN).addCallback(self.filterAnswers(dns.MX))


try:
    theResolver
except NameError:
    theResolver = Resolver('/etc/resolv.conf')
    lookupAddress = theResolver.lookupAddress
    lookupMailExchange = theResolver.lookupMailExchange
