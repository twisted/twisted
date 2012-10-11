# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Lookup a name using multiple resolvers.

Future Plans: This needs someway to specify which resolver answered
the query, or someway to specify (authority|ttl|cache behavior|more?)
"""

from __future__ import division, absolute_import

from zope.interface import implementer

from twisted.internet import defer, interfaces
from twisted.names import dns, common


class FailureHandler:
    def __init__(self, resolver, query, timeout):
        self.resolver = resolver
        self.query = query
        self.timeout = timeout


    def __call__(self, failure):
        # AuthoritativeDomainErrors should halt resolution attempts
        failure.trap(dns.DomainError, defer.TimeoutError, NotImplementedError)
        return self.resolver(self.query, self.timeout)



@implementer(interfaces.IResolver)
class ResolverChain(common.ResolverBase):
    """
    Lookup an address using multiple C{IResolver}s
    """
    def __init__(self, resolvers):
        common.ResolverBase.__init__(self)
        self.resolvers = resolvers


    def _lookup(self, name, cls, type, timeout):
        q = dns.Query(name, type, cls)
        d = self.resolvers[0].query(q, timeout)
        for r in self.resolvers[1:]:
            d = d.addErrback(
                FailureHandler(r.query, q, timeout)
            )
        return d


    def lookupAllRecords(self, name, timeout = None):
        d = self.resolvers[0].lookupAllRecords(name, timeout)
        for r in self.resolvers[1:]:
            d = d.addErrback(
                FailureHandler(r.lookupAllRecords, name, timeout)
            )
        return d
