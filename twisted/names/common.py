
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

import operator, sys

from twisted.protocols import dns
from twisted.internet import defer
from twisted.python import failure

class ResolverBase:
    typeToMethod = None

    def __init__(self):
        self.typeToMethod = {}
        for (k, v) in typeToMethod.items():
            self.typeToMethod[k] = getattr(self, v)


    def addHeader(self, results, name, cls):
        """Add the RR header to each of a list of answers"""
        return [
            dns.RRHeader(
                name, r.TYPE, cls,
                r.ttl, r
            ) for r in results
        ]

    def query(self, query, timeout = 10):
        try:
            d = self.typeToMethod[query.type](str(query.name), timeout)
            return d.addCallback(self.addHeader, str(query.name), query.cls)
        except KeyError:
            return defer.fail(failure.Failure(ValueError(dns.ENOTIMP)))

    def _lookup(self, name, cls, type, timeout):
        raise NotImplementedError("ResolverBase._lookup")

    def lookupAddress(self, name, timeout = 10):
        return self._lookup(name, dns.IN, dns.A, timeout)

    def lookupMailExchange(self, name, timeout = 10):
        return self._lookup(name, dns.IN, dns.MX, timeout)

    def lookupNameservers(self, name, timeout = 10):
        return self._lookup(name, dns.IN, dns.NS, timeout)

    def lookupCanonicalName(self, name, timeout = 10):
        return self._lookup(name, dns.IN, dns.CNAME, timeout)

    def lookupMailBox(self, name, timeout = 10):
        return self._lookup(name, dns.IN, dns.MB, timeout)

    def lookupMailGroup(self, name, timeout = 10):
        return self._lookup(name, dns.IN, dns.MG, timeout)

    def lookupMailRename(self, name, timeout = 10):
        return self._lookup(name, dns.IN, dns.MR, timeout)

    def lookupPointer(self, name, timeout = 10):
        return self._lookup(name, dns.IN, dns.PTR, timeout)

    def lookupAuthority(self, name, timeout = 10):
        return self._lookup(name, dns.IN, dns.SOA, timeout)

    def lookupNull(self, name, timeout = 10):
        return self._lookup(name, dns.IN, dns.NULL, timeout)

    def lookupWellKnownServices(self, name, timeout = 10):
        return self._lookup(name, dns.IN, dns.WKS, timeout)

    def lookupService(self, name, timeout = 10):
        return self._lookup(name, dns.IN, dns.SRV, timeout)

    def lookupHostInfo(self, name, timeout = 10):
        return self._lookup(name, dns.IN, dns.HINFO, timeout)

    def lookupMailboxInfo(self, name, timeout = 10):
        return self._lookup(name, dns.IN, dns.MINFO, timeout)

    def lookupText(self, name, timeout = 10):
        return self._lookup(name, dns.IN, dns.TXT, timeout)

    def lookupResponsibility(self, name, timeout = 10):
        return self._lookup(name, dns.IN, dns.RP, timeout)

    def lookupAFSDatabase(self, name, timeout = 10):
        return self._lookup(name, dns.IN, dns.AFSDB, timeout)

    def lookupAllRecords(self, name, timeout = 10):
        return defer.DeferredList([
            self._lookup(name, dns.IN, type, timeout).addErrback(
                lambda f: f.trap(NotImplementedError) and []
            ) for type in range(1, 17)
        ]).addCallback(
            lambda r: reduce(operator.add, [res[1] for res in r if res[0]], [])
        )


typeToMethod = {
    dns.A:     'lookupAddress',
    dns.NS:    'lookupNameservers',
    dns.CNAME: 'lookupCanonicalName',
    dns.SOA:   'lookupAuthority',
    dns.MB:    'lookupMailBox',
    dns.MG:    'lookupMailGroup',
    dns.MR:    'lookupMailRename',
    dns.NULL:  'lookupNull',
    dns.WKS:   'lookupWellKnownServices',
    dns.PTR:   'lookupPointer',
    dns.HINFO: 'lookupHostInfo',
    dns.MINFO: 'lookupMailboxInfo',
    dns.MX:    'lookupMailExchange',
    dns.TXT:   'lookupText',
    
    dns.RP:    'lookupResponsibility',
    dns.AFSDB: 'lookupAFSDatabase',
    dns.SRV:   'lookupService',
    
    dns.ALL_RECORDS:  'lookupAllRecords',
}
