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
    
    @return: None or the RRHeaders matching dnstype
    @rtype: (Maybe a Deferred resulting in) a list or None
    """
    r = []
    cnames = []
    nses = []

    for rec in reduce(operator.add, result):
        if rec.type == dnstype:
            r.append(rec)
        elif rec.type == dns.CNAME:
            cnames.append(rec.payload)
        elif rec.type == dns.NS:
            nses.append(rec.payload)

    if r:
        return r

    # XXX - timeouts??

    # XXX - CNAME support is totally broken, I think. When return the
    # ultimate records, the code that rummages through them (the
    # callbacks down below) will check that rrheader.name ==
    # nameIRequested. But it won't be! it'll be the target of the
    # CNAME.
    
    if cnames:
        if not cnameLevel:
            return None
        m = getattr(resolver, common.typeToMethod[dnstype])
        # XXX what about multiple CNAMEs?
        d = m(cnames[0].payload.name.name)
        d.addCallback(_scroungeRecords, reqkey, dnstype, cnameLevel-1, nsLevel, resolver)
        return d

    if nses:
        if not nsLevel:
            return None
        from twisted.names import client
        # XXX - what about multiple NSes?
        r = client.Resolver(servers=[(str(nses[0].payload.name), dns.PORT)])
        m = getattr(r, common.typeToMethod[dnstype])
        d = m(reqkey)
        d.addCallback(_scroungeRecords, reqkey, dnstype, cnameLevel, nsLevel-1, resolver)
        return d


def lookupText(domain, cnameLevel=10, nsLevel=10, resolver=client, timeout=None):
    d = resolver.lookupText(domain, timeout)
    d.addCallback(_scroungeRecords, domain, dns.TXT, cnameLevel, nsLevel, resolver)
    d.addCallback(_cbGotTxt, domain, cnameLevel, resolver)
    return d


def _cbGotTxt(result, name, followCNAME, resolver):
    if not result:
        return None
    return [x.payload.data for x in result if x.name.name == name]


def lookupMailExchange(domain, resolveResults=True, cnameLevel=10, nsLevel=10, resolver=client, timeout=None):
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
        return None
    mxes = [(r.payload.preference, r.payload.exchange) for r in result if r.name.name == name]
    mxes.sort()
    return [x[1].name for x in mxes]

def _cbResolveResults(result, resolver):
    if not result:
        return None
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

def lookupPointer(name, cnameLevel=10, nsLevel=10, resolver=client, timeout=None):
    d = resolver.lookupPointer(name, timeout)
    d.addCallback(_scroungeRecords, name, dns.PTR, cnameLevel, nsLevel, resolver)
    d.addCallback(_cbExtractNames, name)
    return d

def _cbExtractNames(result, name):
    if not result:
        return None
    return [x.payload.name.name for x in result if x.name.name == name]

def lookupAddress(name, cnameLevel=10, nsLevel=10, resolver=client, timeout=None):
    d = resolver.lookupAddress(name, timeout)
    d.addCallback(_scroungeRecords, name, dns.A, cnameLevel, nsLevel, resolver)
    d.addCallback(_cbExtractAddresses, name)
    return d

def _cbExtractAddresses(result, name):
    if not result:
        return None
    return [x.payload.dottedQuad() for x in result if x.name.name == name]
