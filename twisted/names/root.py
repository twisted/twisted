# -*- test-case-name: twisted.test.test_rootresolve -*-
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
Resolver implementation for querying successive authoritative servers to
lookup a record, starting from the root nameservers.

API Stability: Unstable

@author U{Jp Calderone<mailto:exarkun@twistedmatrix.com>}

todo: robustify it
      break discoverAuthority into several smaller functions
      documentation
"""

import random

from twisted.python import log
from twisted.internet import defer
from twisted.protocols import dns
from twisted.names import common

class _DummyController:
    def messageReceived(self, *args):
        pass

class Resolver(common.ResolverBase):
    def __init__(self, hints):
        common.ResolverBase.__init__(self)
        self.hints = hints

    def _lookup(self, name, cls, type, timeout):
        d = discoverAuthority(name, self.hints)
        d.addCallback(lambda (auth, _): _)
        d.addCallback(self.discoveredAuthority, name, cls, type, timeout)
        return d
    
    def discoveredAuthority(self, auth, name, cls, type, timeout):
        from twisted.names import client
        q = dns.Query(name, cls, type)
        r = client.Resolver(servers=[(auth, dns.PORT)])
        d = r.queryUDP([q], timeout)
        d.addCallback(r.filterAnswers)
        return d

def discoverAuthority(host, roots, timeout=10, p=None, cache=None):
    if p is None:
        p = dns.DNSDatagramProtocol(_DummyController())
    if cache is None:
        cache = {}

    parts = host.rstrip('.').split('.', 1)
    if len(parts) == 1:
        # This must be some kind of crazy top-level domain!
        host = random.choice(roots)
        d = p.query((host, dns.PORT), [dns.Query(parts[0] + '.', dns.NS)], timeout)
        d.addCallback(lambda r, h=host: (r, h))
        return d
    else:
        # We have some recursion to do!
        d = discoverAuthority(parts[1], roots, timeout, p, cache)
        
        def gotAuthority((message, previous)):
            potent = message.answers + message.authority
            all = potent + message.additional

            # Update our cache
            for a in all:
                if a.type == dns.A:
                    cache[str(a.name)] = a.payload.dottedQuad()

            ns = [a.payload for a in potent if a.type == dns.NS]
            if ns:
                ns = ns[0]
                for a in message.additional:
                    if a.type == dns.A and a.name == ns.name:
                        return (a.payload.dottedQuad(), previous)

                # Check the cache if they didn't tell us
                try:
                    return (cache[str(ns.name)], previous)
                except KeyError:
                    pass

                # They deigned to NOT FREAKING TELL US the address of the
                # authority.  Jerks.  Look for *some* A record they gave us
                # and ask it.
                for a in all:
                    if a.type == dns.A:
                        addr = (a.payload.dottedQuad(), dns.PORT)
                        query = dns.Query(ns.name, dns.A)
                        d = p.query(addr, [query], timeout)
                        d.addCallback(lambda r, h=addr[0]: (r, h))
                        return d

            # They gave us *no* A records.  They are serious wacked out.
            # Maybe the last authority we tried will give us a hand.
            return (previous, previous)

        def lookupNext((address, previous)):
            addr = (address, dns.PORT)
            query = [dns.Query(host, dns.NS)]
            d = p.query(addr, query, timeout)
            d.addCallback(lambda r: (r, address))
            return d

        d.addCallback(gotAuthority)
        d.addCallback(lookupNext)
        return d

def makePlaceholder(deferred, name):
    def placeholder(*args, **kw):
        deferred.addCallback(lambda r: getattr(r, name)(*args, **kw))
        return deferred
    return placeholder

class DeferredResolver:
    def __init__(self, resolverDeferred):
        resolverDeferred.addCallback(self.gotRealResolver)
        self.waiting = []

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
    from twisted.python import log
    f = lambda r: (log.msg('Root server address: ' + str(r)), r)[1]
    L = [resolver.getHostByName('%s.root-servers.net' % d).addCallback(f) for d in domains]
    d = defer.DeferredList(L)
    d.addCallback(lambda r: Resolver([e[1] for e in r if e[0]]))
    return DeferredResolver(d)
