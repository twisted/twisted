# -*- test-case-name: twisted.test.test_names -*-
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

import os, copy, StringIO

from twisted.protocols import dns
from twisted.internet import defer
from twisted.python import failure

import common, bind

class FileAuthority(common.ResolverBase):
    """An Authority that is loaded from a file."""
    
    soa = None
    records = None

    def __init__(self, filename):
        common.ResolverBase.__init__(self)
        self.loadFile(filename)


    def _lookup(self, name, cls, type, timeout = 10):
# XXX - How to do this?  Grar, I think it needs to go through a different
# interface entirely
#
#        if type == dns.AXFR or type == dns.IXFR:
#            s = StringIO.StringIO()
#            bind.writeAuthority(self.soa, self.records, file=s)
#            return defer.succeed(s.getvalue())
#
        try:
            r = []
            for rec in self.records[name.lower()]:
                if rec.TYPE == type or type == dns.ALL_RECORDS:
                    rec = copy.copy(rec)
                    rec.ttl = max(self.soa[1].minimum, self.soa[1].expire)
                    r.append(rec)
            return defer.succeed(r)
        except KeyError:
            if name.lower().endswith(self.soa[0].lower()):
                # We are the authority and we didn't find it.  Goodbye.
                return defer.fail(failure.Failure(dns.AuthoritativeDomainError(name)))
            return defer.fail(failure.Failure(dns.DomainError(name)))


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
        for record in [x for x in dir(dns) if x.startswith('Record_')]:
            type = getattr(dns, record)
            f = self.wrapRecord(type)
            r[record[len('Record_'):]] = f
        return r


class BindAuthority(FileAuthority):
    """An Authority that loads BIND configuration files"""
    
    def loadFile(self, filename):
        self.origin = os.path.basename(filename) # XXX - this might suck
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
