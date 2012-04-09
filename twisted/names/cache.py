# -*- test-case-name: twisted.names.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from zope.interface import implements

from twisted.names import dns, common
from twisted.python import failure, log
from twisted.internet import interfaces, defer



class CacheResolver(common.ResolverBase):
    """
    A resolver that serves records from a local, memory cache.

    @ivar _reactor: A provider of L{interfaces.IReactorTime}.
    """

    implements(interfaces.IResolver)

    cache = None

    def __init__(self, cache=None, verbose=0, reactor=None):
        common.ResolverBase.__init__(self)

        if cache is None:
            cache = {}
        self.cache = cache
        self.verbose = verbose
        self.cancel = {}
        if reactor is None:
            from twisted.internet import reactor
        self._reactor = reactor


    def __setstate__(self, state):
        self.__dict__ = state

        now = self._reactor.seconds()
        for (k, (when, (ans, add, ns))) in self.cache.items():
            diff = now - when
            for rec in ans + add + ns:
                if rec.ttl < diff:
                    del self.cache[k]
                    break


    def __getstate__(self):
        for c in self.cancel.values():
            c.cancel()
        self.cancel.clear()
        return self.__dict__


    def _lookup(self, name, cls, type, timeout):
        now = self._reactor.seconds()
        q = dns.Query(name, type, cls)
        try:
            when, (ans, auth, add) = self.cache[q]
        except KeyError:
            if self.verbose > 1:
                log.msg('Cache miss for ' + repr(name))
            return defer.fail(failure.Failure(dns.DomainError(name)))
        else:
            if self.verbose:
                log.msg('Cache hit for ' + repr(name))
            diff = now - when
            return defer.succeed((
                [dns.RRHeader(str(r.name), r.type, r.cls, max(0, r.ttl - diff), r.payload) for r in ans],
                [dns.RRHeader(str(r.name), r.type, r.cls, max(0, r.ttl - diff), r.payload) for r in auth],
                [dns.RRHeader(str(r.name), r.type, r.cls, max(0, r.ttl - diff), r.payload) for r in add]
            ))


    def lookupAllRecords(self, name, timeout = None):
        return defer.fail(failure.Failure(dns.DomainError(name)))


    def cacheResult(self, query, payload):
        if self.verbose > 1:
            log.msg('Adding %r to cache' % query)

        self.cache[query] = (self._reactor.seconds(), payload)

        if self.cancel.has_key(query):
            self.cancel[query].cancel()

        s = list(payload[0]) + list(payload[1]) + list(payload[2])
        m = s[0].ttl
        for r in s:
            m = min(m, r.ttl)

        self.cancel[query] = self._reactor.callLater(m, self.clearEntry, query)


    def clearEntry(self, query):
        del self.cache[query]
        del self.cancel[query]
