
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

import operator

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


    def _lookup(self, name, cls, type, timeout):
        try:
            r = defer.succeed(self.cache[name.lower()][cls][type])
            if self.verbose:
                log.msg('Cache hit for ' + repr(name))
            return r
        except KeyError:
            if self.verbose > 1:
                log.msg('Cache miss for ' + repr(name))
            return defer.fail(ValueError(dns.ENAME))
    
    
    def lookupAllRecords(self, name, timeout = 10):
        try:
            r = defer.succeed(
                reduce(
                    operator.add,
                    self.cache[name.lower()][dns.IN].values(),
                    []
                )
            )
            if self.verbose:
                log.msg('Cache hit for ' + repr(name))
            return r
        except KeyError:
            if self.verbose > 1:
                log.msg('Cache miss for ' + repr(name))
            return defer.fail(ValueError(dns.ENAME))


    def cacheResult(self, name, type, cls, payload):
        l = self.cache.setdefault(
            str(name).lower(), {}
        ).setdefault(
            cls, {}
        ).setdefault(
            type, []
        )
        if payload not in l:
            if self.verbose > 1:
                log.msg('Adding %r to cache' % name)
            l.append(payload)
