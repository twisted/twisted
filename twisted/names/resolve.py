
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
Lookup a name using multiple resolvers.

API Stability: Unstable

Future Plans: This needs someway to specify which resolver answered
the query, or someway to specify (authority|ttl|cache behavior|more?)

@author: U{Jp Calderone<mailto:exarkun@twistedmatrix.com}
"""

from twisted.internet import defer, interfaces
from twisted.protocols import dns

import common

class FailureHandler:
    def __init__(self, resolver, query, timeout):
        self.resolver = resolver
        self.query = query
        self.timeout = timeout


    def __call__(self, failure):
        # AuthoritativeDomainErrors should halt resolution attempts
        failure.trap(dns.DomainError, defer.TimeoutError, NotImplementedError)
        return self.resolver(self.query, self.timeout)


class ResolverChain(common.ResolverBase):
    """Lookup an address using multiple C{IResolver}s"""
    
    __implements__ = (interfaces.IResolver,)


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


    def lookupAllRecords(self, name, timeout = 10):
        d = self.resolvers[0].lookupAllRecords(name, timeout)
        for r in self.resolvers[1:]:
            d = d.addErrback(
                FailureHandler(r.lookupAllRecords, name, timeout)
            )
        return d
