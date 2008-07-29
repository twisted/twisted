# -*- test-case-name: twisted.names.test.test_rootresolve -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Resolver implementation for querying successive authoritative servers to
lookup a record, starting from the root nameservers.

@author: Jp Calderone

todo::
    robustify it
    break discoverAuthority into several smaller functions
    documentation
"""

from __future__ import generators

import sys

from twisted.python import log
from twisted.internet import defer
from twisted.names import dns
from twisted.names import common

def retry(t, p, *args):
    assert t, "Timeout is required"
    t = list(t)
    def errback(failure):
        failure.trap(defer.TimeoutError)
        if not t:
            return failure
        return p.query(timeout=t.pop(0), *args
            ).addErrback(errback
            )
    return p.query(timeout=t.pop(0), *args
        ).addErrback(errback
        )

class _DummyController:
    def messageReceived(self, *args):
        pass

class Resolver(common.ResolverBase):
    def __init__(self, hints):
        common.ResolverBase.__init__(self)
        self.hints = hints

    def _lookup(self, name, cls, type, timeout):
        d = discoverAuthority(name, self.hints
            ).addCallback(self.discoveredAuthority, name, cls, type, timeout
            )
        return d

    def discoveredAuthority(self, auth, name, cls, type, timeout):
        from twisted.names import client
        q = dns.Query(name, type, cls)
        r = client.Resolver(servers=[(auth, dns.PORT)])
        d = r.queryUDP([q], timeout)
        d.addCallback(r.filterAnswers)
        return d

def lookupNameservers(host, atServer, p=None):
    # print 'Nameserver lookup for', host, 'at', atServer, 'with', p
    if p is None:
        p = dns.DNSDatagramProtocol(_DummyController())
        p.noisy = False
    return retry(
        (1, 3, 11, 45),                     # Timeouts
        p,                                  # Protocol instance
        (atServer, dns.PORT),               # Server to query
        [dns.Query(host, dns.NS, dns.IN)]   # Question to ask
    )

def lookupAddress(host, atServer, p=None):
    # print 'Address lookup for', host, 'at', atServer, 'with', p
    if p is None:
        p = dns.DNSDatagramProtocol(_DummyController())
        p.noisy = False
    return retry(
        (1, 3, 11, 45),                     # Timeouts
        p,                                  # Protocol instance
        (atServer, dns.PORT),               # Server to query
        [dns.Query(host, dns.A, dns.IN)]    # Question to ask
    )

def extractAuthority(msg, cache):
    records = msg.answers + msg.authority + msg.additional
    nameservers = [r for r in records if r.type == dns.NS]

    # print 'Records for', soFar, ':', records
    # print 'NS for', soFar, ':', nameservers

    if not nameservers:
        return None, nameservers
    if not records:
        raise IOError("No records")
    for r in records:
        if r.type == dns.A:
            cache[str(r.name)] = r.payload.dottedQuad()
    for r in records:
        if r.type == dns.NS:
            if str(r.payload.name) in cache:
                return cache[str(r.payload.name)], nameservers
    for addr in records:
        if addr.type == dns.A and addr.name == r.name:
            return addr.payload.dottedQuad(), nameservers
    return None, nameservers

def discoverAuthority(host, roots, cache=None, p=None):
    if cache is None:
        cache = {}

    rootAuths = list(roots)

    parts = host.rstrip('.').split('.')
    parts.reverse()

    authority = rootAuths.pop()

    soFar = ''
    for part in parts:
        soFar = part + '.' + soFar
        # print '///////',  soFar, authority, p
        msg = defer.waitForDeferred(lookupNameservers(soFar, authority, p))
        yield msg
        msg = msg.getResult()

        newAuth, nameservers = extractAuthority(msg, cache)

        if newAuth is not None:
            # print "newAuth is not None"
            authority = newAuth
        else:
            if nameservers:
                r = str(nameservers[0].payload.name)
                # print 'Recursively discovering authority for', r
                authority = defer.waitForDeferred(discoverAuthority(r, roots, cache, p))
                yield authority
                authority = authority.getResult()
                # print 'Discovered to be', authority, 'for', r
##            else:
##                # print 'Doing address lookup for', soFar, 'at', authority
##                msg = defer.waitForDeferred(lookupAddress(soFar, authority, p))
##                yield msg
##                msg = msg.getResult()
##                records = msg.answers + msg.authority + msg.additional
##                addresses = [r for r in records if r.type == dns.A]
##                if addresses:
##                    authority = addresses[0].payload.dottedQuad()
##                else:
##                    raise IOError("Resolution error")
    # print "Yielding authority", authority
    yield authority

discoverAuthority = defer.deferredGenerator(discoverAuthority)

def makePlaceholder(deferred, name):
    def placeholder(*args, **kw):
        deferred.addCallback(lambda r: getattr(r, name)(*args, **kw))
        return deferred
    return placeholder

class DeferredResolver:
    def __init__(self, resolverDeferred):
        self.waiting = []
        resolverDeferred.addCallback(self.gotRealResolver)

    def gotRealResolver(self, resolver):
        w = self.waiting
        self.__dict__ = resolver.__dict__
        self.__class__ = resolver.__class__
        for d in w:
            d.callback(resolver)

    def __getattr__(self, name):
        if name.startswith('lookup') or name in ('getHostByName', 'query'):
            self.waiting.append(defer.Deferred())
            return makePlaceholder(self.waiting[-1], name)
        raise AttributeError(name)

def bootstrap(resolver):
    """Lookup the root nameserver addresses using the given resolver

    Return a Resolver which will eventually become a C{root.Resolver}
    instance that has references to all the root servers that we were able
    to look up.
    """
    domains = [chr(ord('a') + i) for i in range(13)]
    # f = lambda r: (log.msg('Root server address: ' + str(r)), r)[1]
    f = lambda r: r
    L = [resolver.getHostByName('%s.root-servers.net' % d).addCallback(f) for d in domains]
    d = defer.DeferredList(L)
    d.addCallback(lambda r: Resolver([e[1] for e in r if e[0]]))
    return DeferredResolver(d)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print 'Specify a domain'
    else:
        log.startLogging(sys.stdout)
        from twisted.names.client import ThreadedResolver
        r = bootstrap(ThreadedResolver())
        d = r.lookupAddress(sys.argv[1])
        d.addCallbacks(log.msg, log.err).addBoth(lambda _: reactor.stop())
        from twisted.internet import reactor
        reactor.run()
