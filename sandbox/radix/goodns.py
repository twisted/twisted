# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2004 Matthew W. Lefkowitz
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
#

"""
GooDNS, a high-level DNS lookup library.
"""

from twisted.names import client, common
from twisted.protocols import dns
from twisted.internet.abstract import isIPAddress
from twisted.internet import defer

import operator

D_CNAME = 4
D_NS = 4


def _scroungeRecords((answers, authority, additional), reqkey, dnstype,
                     cnameLevel, nsLevel, resolver):
    """
    Find relevant records in a list of RRs, following CNAME and NS
    records if necessary. Inspired by
    L{twisted.names.common.extractRecord}.

    @return: [] or the RRHeaders matching dnstype and reqkey
    @rtype: (Maybe a Deferred resulting in) a list or []
    """
    
    r = []
    cnames = []
    nses = []

    for rec in answers:
        if rec.name.name == reqkey:
            if rec.type == dnstype:
                r.append(rec)
            elif rec.type == dns.CNAME:
                cnames.append(rec.payload)

    if r:
        return r

    # XXX - timeouts? Need more state. :(

    if cnames:
        if not cnameLevel:
            return []
        m = getattr(resolver, common.typeToMethod[dnstype])
        # XXX - hey! what if they were nice enough to give the A of
        # the CNAME already?
        newkey = cnames[0].name.name
        d = m(cnames[0].name.name)
        d.addCallback(_scroungeRecords, newkey, dnstype,
                      cnameLevel-1, nsLevel, resolver)
        return d

    if nses:
        if not nsLevel:
            return []
        # XXX - what about multiple NSes? Maybe randomly choose one.
        r = client.Resolver(servers=[(str(authority[0].name), dns.PORT)])
        m = getattr(r, common.typeToMethod[dnstype])
        d = m(reqkey)
        d.addCallback(_scroungeRecords, reqkey, dnstype,
                      cnameLevel, nsLevel-1, resolver)
        return d


def lookupText(domain, cnameLevel=D_CNAME, nsLevel=D_NS,
               resolver=client, timeout=None):
    """
    Look up TXT records for a given domain.

    @rtype: list of lists
    @return: A list of lists of the TXT data.
    """
    d = resolver.lookupText(domain, timeout)
    d.addCallback(_scroungeRecords, domain, dns.TXT,
                  cnameLevel, nsLevel, resolver)
    d.addCallback(_cbGotTxt, domain, cnameLevel, resolver)
    return d


def _cbGotTxt(result, name, followCNAME, resolver):
    if not result:
        return []
    return [x.payload.data for x in result]


def lookupMailExchange(domain, resolveResults=True,
                       cnameLevel=D_CNAME, nsLevel=D_NS,
                       resolver=client, timeout=None):
    """
    Look up MX records for a given domain.

    @rtype: list of two-tuples
    @return: a list of (priority, hostname) sorted by their MX
    priority (low -> high).
    """
    d = resolver.lookupMailExchange(domain, timeout)
    d.addCallback(_scroungeRecords, domain, dns.MX,
                  cnameLevel, nsLevel, resolver)
    d.addCallback(_cbGotMX, domain)
    if resolveResults:
        d.addCallback(_cbResolveResults, resolver)
    return d

def _cbGotMX(result, name):
    if not result:
        return []
    mxes = [(r.payload.preference, r.payload.exchange) for r in result]
    mxes.sort()
    return [(x[0], x[1].name) for x in mxes]

def _cbResolveResults(result, resolver):
    if not result:
        return []
    dl = []
    for pri, val in result:
        if not isIPAddress(val):
            d = resolver.getHostByName(val)
            d.addCallback(lambda x, pri=pri: (pri, x))
            dl.append(d)
        else:
            dl.append(defer.succeed((pri, val)))
    return defer.gatherResults(dl)


def lookupNameservers(name, cnameLevel=D_CNAME, nsLevel=D_NS,
                      resolver=client, timeout=None):
    d = resolver.lookupNameservers(name, timeout)
    d.addCallback(_scroungeRecords, name, dns.NS, cnameLevel, nsLevel, resolver)
    d.addCallback(_cbExtractNames, name)
    return d


def ptrize(ip):
    """
    Convert an IP address to something you can pass to L{lookupPointer}.

    @rtype: str
    """
    parts = ip.split('.')
    parts.reverse()
    return '.'.join(parts) + '.in-addr.arpa'


def lookupPointer(name, cnameLevel=D_CNAME, nsLevel=D_NS,
                  resolver=client, timeout=None):
    """
    Look up a PTR record for a given name. You probably want to pass
    an IP address to L{ptrize} and pass the result to this function.

    @param name: The name to look up the PTR record for.
    
    @rtype: list of str
    @return: hostnames.
    """
    d = resolver.lookupPointer(name, timeout)
    d.addCallback(_scroungeRecords, name, dns.PTR,
                  cnameLevel, nsLevel, resolver)
    d.addCallback(_cbExtractNames, name)
    return d

def _cbExtractNames(result, name):
    if not result:
        return []
    return [x.payload.name.name for x in result]


def lookupAddress(name, cnameLevel=D_CNAME, nsLevel=D_NS,
                  resolver=client, timeout=None):
    """
    Look up an A record for a given name.

    @rtype: list of str
    @return: IPv4 addresses.
    """
    d = resolver.lookupAddress(name, timeout)
    d.addCallback(_scroungeRecords, name, dns.A,
                  cnameLevel, nsLevel, resolver)
    d.addCallback(_cbExtractAddresses, name)
    return d

def _cbExtractAddresses(result, name):
    if not result:
        return []
    return [x.payload.dottedQuad() for x in result]


def lookupService(protocol, transport, hostname, cnameLevel=D_CNAME, nsLevel=D_NS,
                  resolver=client, timeout=None):
    """
    Look up a SVC record for a given name.

    @param protocol: The protocol that you want to look up a port for.
    @param transport: The transport that the protocol will run on.
    @param hostname: The hostname.

    @rtype: list of four-tuples
    @return: A list of (priority, weight, port, name).
    """
    name = '_%s._%s.%s' % (protocol, transport, hostname)
    d = resolver.lookupService(name, timeout)
    d.addCallback(_scroungeRecords, name, dns.SRV,
                  cnameLevel, nsLevel, resolver)
    d.addCallback(_cbExtractServices, name)
    return d

def _cbExtractServices(result, name):
    if not result:
        return []
    # DSU
    result = [ ( x.payload.priority, x.payload ) for x in result ]
    result.sort()
    result = [ ( x[1].priority, x[1].weight, 
               x[1].port, x[1].target.name ) for x in result ]
    return result


globalParameters = """
    @param cnameLevel: (optional) The number of CNAMEs to follow.
    @param nsLevel: (optional) The number of NSes to follow.
    @param resolver: (optional) The resolver to use. The default is the
           L{twisted.names.client} module.
    @param timeout: (optional) How long to wait for a result before
           timing out.
"""

for fname,func in globals().items():
    if fname.startswith('lookup') and callable(func):
        if func.__doc__:
            func.__doc__ += globalParameters
            continue
        func.__doc__ = globalParameters

del func
del fname
del globalParameters
del D_NS
del D_CNAME
