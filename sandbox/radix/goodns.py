"""
XXX - should these raise an error instead of returning None when no
      appropriate records can be found?
"""
from twisted.names import client, common
from twisted.protocols import dns
from twisted.internet.abstract import isIPAddress
from twisted.internet import defer

import operator


def _scroungeRecords(result, reqkey, dnstype, cnameLevel, nsLevel, resolver):
    """
    Inspired by twisted.names.common.extractRecords.

    @return: [] or the RRHeaders matching dnstype and reqkey
    @rtype: (Maybe a Deferred resulting in) a list or []
    """
##    print "** Scrounging (%s, %s) **" % (dns.QUERY_TYPES[dnstype], reqkey)
##    print result
##    print
    
    r = []
    cnames = []
    nses = []

    for rec in reduce(operator.add, result):
        if rec.type == dnstype and rec.name.name == reqkey:
            r.append(rec)
        elif rec.type == dns.CNAME:
            cnames.append(rec.payload)
        elif rec.type == dns.NS:
            nses.append(rec.payload)

    if r:
        return r

    # XXX - timeouts??

    if cnames:
        if not cnameLevel:
            return []
        m = getattr(resolver, common.typeToMethod[dnstype])
##        print "== CNAME =="
##        print "trying to look up", dns.QUERY_TYPES[dnstype], "with", cnames[0].name.name
##        print
        # XXX what about multiple CNAMEs?
        newkey = cnames[0].name.name
        d = m(cnames[0].name.name)
        d.addCallback(_scroungeRecords, newkey, dnstype, cnameLevel-1, nsLevel, resolver)
        return d

    if nses:
        if not nsLevel:
            return []
        from twisted.names import client
##        print "== NS =="
##        print "trying to look up", dns.QUERY_TYPES[dnstype], "with", reqkey
##        print
        # XXX - what about multiple NSes?
        r = client.Resolver(servers=[(str(nses[0].name), dns.PORT)])
        m = getattr(r, common.typeToMethod[dnstype])
        d = m(reqkey)
        d.addCallback(_scroungeRecords, reqkey, dnstype, cnameLevel, nsLevel-1, resolver)
        return d


def lookupText(domain, cnameLevel=4, nsLevel=4, resolver=client, timeout=None):
    d = resolver.lookupText(domain, timeout)
    d.addCallback(_scroungeRecords, domain, dns.TXT, cnameLevel, nsLevel, resolver)
    d.addCallback(_cbGotTxt, domain, cnameLevel, resolver)
    return d


def _cbGotTxt(result, name, followCNAME, resolver):
    if not result:
        return []
    return [x.payload.data for x in result]


def lookupMailExchange(domain, resolveResults=True, cnameLevel=4, nsLevel=4, resolver=client, timeout=None):
    """
    I return a list of hosts sorted by their MX priority (low -> high).
    XXX - is having the actual numeric priorities ever relevant?
    """
    d = resolver.lookupMailExchange(domain, timeout)
    d.addCallback(_scroungeRecords, domain, dns.MX, cnameLevel, nsLevel, resolver)
    d.addCallback(_cbGotMX, domain)
    if resolveResults:
        d.addCallback(_cbResolveResults, resolver)
    return d

def _cbGotMX(result, name):
    if not result:
        return []
    mxes = [(r.payload.preference, r.payload.exchange) for r in result]
    mxes.sort()
    return [x[1].name for x in mxes]

def _cbResolveResults(result, resolver):
    if not result:
        return []
    dl = []
    for val in result:
        if not isIPAddress(val):
            dl.append(resolver.getHostByName(val))
        else:
            dl.append(defer.succeed(val))
    return defer.gatherResults(dl)

def ptrize(ip):
    parts = ip.split('.')
    parts.reverse()
    return '.'.join(parts) + '.in-addr.arpa'

def lookupPointer(name, cnameLevel=4, nsLevel=4, resolver=client, timeout=None):
    d = resolver.lookupPointer(name, timeout)
    d.addCallback(_scroungeRecords, name, dns.PTR, cnameLevel, nsLevel, resolver)
    d.addCallback(_cbExtractNames, name)
    return d

def _cbExtractNames(result, name):
    if not result:
        return []
    return [x.payload.name.name for x in result]

def lookupAddress(name, cnameLevel=4, nsLevel=4, resolver=client, timeout=None):
    d = resolver.lookupAddress(name, timeout)
    d.addCallback(_scroungeRecords, name, dns.A, cnameLevel, nsLevel, resolver)
    d.addCallback(_cbExtractAddresses, name)
    return d

def _cbExtractAddresses(result, name):
    if not result:
        return []
    return [x.payload.dottedQuad() for x in result]

def lookupService(name, cnameLevel=4, nsLevel=4, resolver=client, timeout=None):
    d = resolver.lookupService(name, timeout)
    d.addCallback(_scroungeRecords, name, dns.SRV, cnameLevel, nsLevel, resolver)
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
