
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
from twisted.internet import interfaces, defer

def searchFileFor(file, name):
    try:
        fp = open(file)
    except:
        return None

    lines = fp.readlines()
    for line in lines:
        idx = line.find('#')
        if idx != -1:
            line = line[:idx]
        if not line:
            continue
        parts = line.split()
        if name.lower() in [s.lower() for s in parts[1:]]:
            return parts[0]
    return None


class Resolver:
    """A resolver that services hosts(5) format files."""

    __implements__ = (interfaces.IResolverSimple,)

    def __init__(self, file='/etc/hosts', ttl = 60 * 60):
        self.file = file
        self.ttl = ttl


    def query(self, query, timeout = 10):
        return self._lookup(str(query.name), query.type, query.type, timeout)


    def _lookup(self, name, cls, type, timeout):
        if cls != dns.IN or type != dns.A:
            raise NotImplementedError, (type, cls)
        return self.lookupAddress(
            name, timeout
        )


    def lookupAddress(self, name, timeout=10):
        res = searchFileFor(self.file, name)
        if res:
            return defer.succeed([
                dns.RRHeader(name, dns.A, dns.IN, self.ttl)
            ])
        return defer.fail(failure.Failure(dns.DomainError(name)))


    lookupAllRecords = lookupAddress
