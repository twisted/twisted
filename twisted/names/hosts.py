# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
hosts(5) support.
"""

from twisted.names import dns
from twisted.persisted import styles
from twisted.python import failure
from twisted.internet import defer

from twisted.names import common


def searchFileFor(file, name):
    """
    Grep given file, which is in hosts(5) standard format, for an address
    entry with a given name.

    @param file: The name of the hosts(5)-format file to search.

    @param name: The name to search for.
    @type name: C{str}

    @return: C{None} if the name is not found in the file, otherwise a
        C{str} giving the address in the file associated with the name.
    """
    try:
        fp = open(file)
    except:
        return None
    try:
        lines = fp.readlines()
    finally:
        fp.close()
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
