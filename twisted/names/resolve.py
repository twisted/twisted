
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

class ResolverChain(common.ResolverBase):
    """Lookup an address using multiple C{IResolver}s"""
    
    __implements__ = (interfaces.IResolver,)


    def __init__(self, resolvers):
        common.ResolverBase.__init__(self)
        self.resolvers = resolvers


    def _lookup(self, name, cls, type, timeout):
        d = self.resolvers[0]._lookup(name, cls, type, timeout)
        for r in self.resolvers[1:]:
            d = d.addErrback(
                lambda f, r=r, n=name, c=cls, t=type, i=timeout: r._lookup(n, c, t, i)
            )
        return d
