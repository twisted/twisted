
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

from twisted.protocols import dns
from twisted.python import failure
from twisted.internet import interfaces


class CacheResolver:
    __implements__ = (interfaces.IResolver,)
    
    cache = None
    
    def __init__(self, cache = None):
        if cache is None:
            cache = {}
        self.cache = cache
    
    
    def lookupAddress(self, name, timeout=10):
        try:
            return self.cache[name.lower()][dns.A]
        except KeyError:
            return []


    def cacheResult(self, name, type, payload):
        self.cache.setdefault(name.lower(), {}).setdefault(type, []).append(payload)
