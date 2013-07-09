# -*- test-case-name: twisted.names.test.test_names -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Authoritative resolvers.
"""

import os
import time

from twisted.names import dns
from twisted.internet import defer
from twisted.python import failure
from twisted.python.compat import execfile

import common

def getSerial(filename = '/tmp/twisted-names.serial'):
    """Return a monotonically increasing (across program runs) integer.

    State is stored in the given file.  If it does not exist, it is
    created with rw-/---/--- permissions.
    """
    serial = time.strftime('%Y%m%d')

    o = os.umask(0177)
    try:
        if not os.path.exists(filename):
            f = file(filename, 'w')
            f.write(serial + ' 0')
            f.close()
    finally:
        os.umask(o)

    serialFile = file(filename, 'r')
    lastSerial, ID = serialFile.readline().split()
    ID = (lastSerial == serial) and (int(ID) + 1) or 0
    serialFile.close()
    serialFile = file(filename, 'w')
    serialFile.write('%s %d' % (serial, ID))
    serialFile.close()
    serial = serial + ('%02d' % (ID,))
    return serial


#class LookupCacherMixin(object):
#    _cache = None
#
#    def _lookup(self, name, cls, type, timeout = 10):
#        if not self._cache:
#            self._cache = {}
#            self._meth = super(LookupCacherMixin, self)._lookup
#
#        if self._cache.has_key((name, cls, type)):
#            return self._cache[(name, cls, type)]
#        else:
#            r = self._meth(name, cls, type, timeout)
#            self._cache[(name, cls, type)] = r
#            return r


class FileAuthority(common.ResolverBase):
    """An Authority that is loaded from a file."""

    soa = None
    records = None

    def __init__(self, filename):
        common.ResolverBase.__init__(self)
        self.loadFile(filename)
        self._cache = {}


    def __setstate__(self, state):
        self.__dict__ = state
#        print 'setstate ', self.soa

    def _lookup(self, name, cls, type, timeout = None):
        cnames = []
        results = []
        authority = []
        additional = []
        default_ttl = max(self.soa[1].minimum, self.soa[1].expire)

        domain_records = self.records.get(name.lower())

        if domain_records:
            for record in domain_records:
                if record.ttl is not None:
                    ttl = record.ttl
                else:
                    ttl = default_ttl

                if record.TYPE == dns.NS and name.lower() != self.soa[0].lower():
                    # NS record belong to a child zone: this is a referral.  As
                    # NS records are authoritative in the child zone, ours here
                    # are not.  RFC 2181, section 6.1.
                    authority.append(
                        dns.RRHeader(name, record.TYPE, dns.IN, ttl, record, auth=False)
                    )
                elif record.TYPE == type or type == dns.ALL_RECORDS:
                    results.append(
                        dns.RRHeader(name, record.TYPE, dns.IN, ttl, record, auth=True)
                    )
                if record.TYPE == dns.CNAME:
                    cnames.append(
                        dns.RRHeader(name, record.TYPE, dns.IN, ttl, record, auth=True)
                    )
            if not results:
                results = cnames

            for record in results + authority:
                section = {dns.NS: additional, dns.CNAME: results, dns.MX: additional}.get(record.type)
                if section is not None:
                    n = str(record.payload.name)
                    for rec in self.records.get(n.lower(), ()):
                        if rec.TYPE == dns.A:
                            section.append(
                                dns.RRHeader(n, dns.A, dns.IN, rec.ttl or default_ttl, rec, auth=True)
                            )

            if not results and not authority:
                # Empty response. Include SOA record to allow clients to cache
                # this response.  RFC 1034, sections 3.7 and 4.3.4, and RFC 2181
                # section 7.1.
                authority.append(
                    dns.RRHeader(self.soa[0], dns.SOA, dns.IN, ttl, self.soa[1], auth=True)
                    )
            return defer.succeed((results, authority, additional))
        else:
            if name.lower().endswith(self.soa[0].lower()):
                # We are the authority and we didn't find it.  Goodbye.
                return defer.fail(failure.Failure(dns.AuthoritativeDomainError(name)))
            return defer.fail(failure.Failure(dns.DomainError(name)))


    def lookupZone(self, name, timeout = 10):
        if self.soa[0].lower() == name.lower():
            # Wee hee hee hooo yea
            default_ttl = max(self.soa[1].minimum, self.soa[1].expire)
            if self.soa[1].ttl is not None:
                soa_ttl = self.soa[1].ttl
            else:
                soa_ttl = default_ttl
            results = [dns.RRHeader(self.soa[0], dns.SOA, dns.IN, soa_ttl, self.soa[1], auth=True)]
            for (k, r) in self.records.items():
                for rec in r:
                    if rec.ttl is not None:
                        ttl = rec.ttl
                    else:
                        ttl = default_ttl
                    if rec.TYPE != dns.SOA:
                        results.append(dns.RRHeader(k, rec.TYPE, dns.IN, ttl, rec, auth=True))
            results.append(results[0])
            return defer.succeed((results, (), ()))
        return defer.fail(failure.Failure(dns.DomainError(name)))

    def _cbAllRecords(self, results):
        ans, auth, add = [], [], []
        for res in results:
            if res[0]:
                ans.extend(res[1][0])
                auth.extend(res[1][1])
                add.extend(res[1][2])
        return ans, auth, add


class PySourceAuthority(FileAuthority):
    """A FileAuthority that is built up from Python source code."""

    def loadFile(self, filename):
        g, l = self.setupConfigNamespace(), {}
        execfile(filename, g, l)
        if not l.has_key('zone'):
            raise ValueError, "No zone defined in " + filename

        self.records = {}
        for rr in l['zone']:
            if isinstance(rr[1], dns.Record_SOA):
                self.soa = rr
            self.records.setdefault(rr[0].lower(), []).append(rr[1])


    def wrapRecord(self, type):
        return lambda name, *arg, **kw: (name, type(*arg, **kw))


    def setupConfigNamespace(self):
        r = {}
        items = dns.__dict__.iterkeys()
        for record in [x for x in items if x.startswith('Record_')]:
            type = getattr(dns, record)
            f = self.wrapRecord(type)
            r[record[len('Record_'):]] = f
        return r


class BindAuthority(FileAuthority):
    """An Authority that loads BIND configuration files"""

    def loadFile(self, filename):
        self.origin = os.path.basename(filename) + '.' # XXX - this might suck
        lines = open(filename).readlines()
        lines = self.stripComments(lines)
        lines = self.collapseContinuations(lines)
        self.parseLines(lines)


    def stripComments(self, lines):
        return [
            a.find(';') == -1 and a or a[:a.find(';')] for a in [
                b.strip() for b in lines
            ]
        ]


    def collapseContinuations(self, lines):
        L = []
        state = 0
        for line in lines:
            if state == 0:
                if line.find('(') == -1:
                    L.append(line)
                else:
                    L.append(line[:line.find('(')])
                    state = 1
            else:
                if line.find(')') != -1:
                    L[-1] += ' ' + line[:line.find(')')]
                    state = 0
                else:
                    L[-1] += ' ' + line
        lines = L
        L = []
        for line in lines:
            L.append(line.split())
        return filter(None, L)


    def parseLines(self, lines):
        TTL = 60 * 60 * 3
        ORIGIN = self.origin

        self.records = {}

        for (line, index) in zip(lines, range(len(lines))):
            if line[0] == '$TTL':
                TTL = dns.str2time(line[1])
            elif line[0] == '$ORIGIN':
                ORIGIN = line[1]
            elif line[0] == '$INCLUDE': # XXX - oh, fuck me
                raise NotImplementedError('$INCLUDE directive not implemented')
            elif line[0] == '$GENERATE':
                raise NotImplementedError('$GENERATE directive not implemented')
            else:
                self.parseRecordLine(ORIGIN, TTL, line)


    def addRecord(self, owner, ttl, type, domain, cls, rdata):
        if not domain.endswith('.'):
            domain = domain + '.' + owner
        else:
            domain = domain[:-1]
        f = getattr(self, 'class_%s' % cls, None)
        if f:
            f(ttl, type, domain, rdata)
        else:
            raise NotImplementedError, "Record class %r not supported" % cls


    def class_IN(self, ttl, type, domain, rdata):
        record = getattr(dns, 'Record_%s' % type, None)
        if record:
            r = record(*rdata)
            r.ttl = ttl
            self.records.setdefault(domain.lower(), []).append(r)

            print 'Adding IN Record', domain, ttl, r
            if type == 'SOA':
                self.soa = (domain, r)
        else:
            raise NotImplementedError, "Record type %r not supported" % type


    #
    # This file ends here.  Read no further.
    #
    def parseRecordLine(self, origin, ttl, line):
        MARKERS = dns.QUERY_CLASSES.values() + dns.QUERY_TYPES.values()
        cls = 'IN'
        owner = origin

        if line[0] == '@':
            line = line[1:]
            owner = origin
#            print 'default owner'
        elif not line[0].isdigit() and line[0] not in MARKERS:
            owner = line[0]
            line = line[1:]
#            print 'owner is ', owner

        if line[0].isdigit() or line[0] in MARKERS:
            domain = owner
            owner = origin
#            print 'woops, owner is ', owner, ' domain is ', domain
        else:
            domain = line[0]
            line = line[1:]
#            print 'domain is ', domain

        if line[0] in dns.QUERY_CLASSES.values():
            cls = line[0]
            line = line[1:]
#            print 'cls is ', cls
            if line[0].isdigit():
                ttl = int(line[0])
                line = line[1:]
#                print 'ttl is ', ttl
        elif line[0].isdigit():
            ttl = int(line[0])
            line = line[1:]
#            print 'ttl is ', ttl
            if line[0] in dns.QUERY_CLASSES.values():
                cls = line[0]
                line = line[1:]
#                print 'cls is ', cls

        type = line[0]
#        print 'type is ', type
        rdata = line[1:]
#        print 'rdata is ', rdata

        self.addRecord(owner, ttl, type, domain, cls, rdata)
