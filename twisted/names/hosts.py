
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
from twisted.persisted import styles
from twisted.python import failure
from twisted.internet import interfaces, defer

from twisted.names import common

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



class Resolver(common.ResolverBase, styles.Versioned):
    """A resolver that services hosts(5) format files."""
    #TODO: IPv6 support

    persistenceVersion = 1

    def upgradeToVersion1(self):
        # <3 exarkun
        self.typeToMethod = {}
        for (k, v) in common.typeToMethod.items():
            self.typeToMethod[k] = getattr(self, v)
    

    def __init__(self, file='/etc/hosts', ttl = 60 * 60):
        common.ResolverBase.__init__(self)
        self.file = file
        self.ttl = ttl


    def lookupAddress(self, name, timeout = None):
        res = searchFileFor(self.file, name)
        if res:
            return defer.succeed([
                (dns.RRHeader(name, dns.A, dns.IN, self.ttl, dns.Record_A(res, self.ttl)),), (), ()
            ])
        return defer.fail(failure.Failure(dns.DomainError(name)))


    # When we put IPv6 support in, this'll need a real impl
    lookupAllRecords = lookupAddress 
