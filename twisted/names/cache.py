
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

import operator, time, copy

from twisted.protocols import dns
from twisted.python import failure, log
from twisted.internet import interfaces, defer

import common

class CacheResolver(common.ResolverBase):
    """A resolver that serves records from a local, memory cache."""

    __implements__ = (interfaces.IResolver,)
    
    cache = None
    
    def __init__(self, cache = None, verbose = 0):
        common.ResolverBase.__init__(self)

        if cache is None:
            cache = {}
        self.cache = cache
        self.verbose = verbose


    def addHeader(self, results, name, cls):
        """Mark all these results as cache hits"""
        for r in results:
            r = copy.copy(r)
            r.cachedResponse = 1
            r.ttl = r.ttl - time.time()
        results = common.ResolverBase.addHeader(self, results, name, cls)
        return [r for r in results if r.ttl > 0]


    def _lookup(self, name, cls, type, timeout):
        now = time.time()
        try:
            records = self.cache[name.lower()][cls][type] = [r for r in self.cache[name.lower()][cls][type] if r.ttl > now]
        except KeyError:
            if self.verbose > 1:
                log.msg('Cache miss for ' + repr(name))
            return defer.fail(failure.Failure(dns.DomainError(name)))
        else:
            if records:
                if self.verbose:
                    log.msg('Cache hit for ' + repr(name))
                return defer.succeed([
                    dns.RRHeader(name, type, cls, r.ttl - now, r) for r in records
                ])
            else:
                if self.verbose:
                    log.msg('Cache miss (expired) for ' + repr(name))
                return defer.fail(failure.Failure(dns.DomainError(name)))


    def lookupAllRecords(self, name, timeout = 10):
        now = time.time()
        try:
            rec = reduce(
                operator.add,
                self.cache[name.lower()][dns.IN].values(),
            )
            if self.verbose:
                log.msg('Cache hit for ' + repr(name))
            return defer.succeed([
                dns.RRHeader(name, r.TYPE, dns.IN, r.ttl - now, r) for r in rec
            ])
        except (KeyError, TypeError), e:
            if self.verbose > 1:
                log.msg('Cache miss for ' + repr(name))
            return defer.fail(failure.Failure(dns.DomainError(name)))


    def cacheResult(self, name, ttl, type, cls, payload):
        l = self.cache.setdefault(
            str(name).lower(), {}
        ).setdefault(
            cls, {}
        ).setdefault(
            type, []
        )
        if payload not in l:
            payload = copy.copy(payload)
            payload.ttl = time.time() + ttl
            if self.verbose > 1:
                log.msg('Adding %r to cache' % name)
            l.append(payload)
