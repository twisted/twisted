
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
Async DNS server

API Stability: Unstable

Future plans: Have this work.  Better config file format maybe;
  Make sure to differentiate between different classes; handle
  recursive lookups; notice truncation bit; probably other stuff.

@author: U{Jp Calderone <exarkun@twistedmatrix.com>}
"""

from __future__ import nested_scopes

# System imports
import struct

# Twisted imports
from twisted.internet import protocol
from twisted.protocols import dns
from twisted.python import log

import client

class Authority:
    """
    Guess.
    """

    def __init__(self, filename):
        g, l = self.setupConfigNamespace(), {}
        execfile(filename, g, l)
        if not l.has_key('zone'):
            raise ValueError, "No zone defined in " + filename
        
        self.records = {}
        for rr in l['zone']:
            if isinstance(rr[1], dns.Record_SOA):
                self.soa = rr
            self.records.setdefault(rr[0], []).append(rr[1])


    def wrapRecord(self, type):
        return lambda name, *arg, **kw: (name, type(*arg, **kw))


    def setupConfigNamespace(self):
        r = {}
        for record in [x for x in dir(dns) if x.startswith('Record_')]:
            type = getattr(dns, record)
            f = self.wrapRecord(type)
            r[record[len('Record_'):]] = f
        return r


class DNSServerFactory(protocol.ServerFactory):
    def __init__(self, authorities, verbose = 0):
        self.authorities = authorities
        self.verbose = verbose


    def startFactory(self):
        self.resolver = client.theResolver


    def stopFactory(self):
        del self.resolver


    def buildProtocol(self, addr):
        p = dns.TCPDNSClientProtocol(self)
        p.factory = self
        return p


    def connectionMade(self, protocol):
        pass


    def sendReply(self, protocol, message, address):
        if self.verbose > 1:
            s = ' '.join([str(a) for a in message.answers])
            if not s:
                log.msg("Replying with no answers")
            else:
                log.msg("Answers are " + s)

        if address is None:
            protocol.writeMessage(message)
        else:
            protocol.writeMessage(message, address)


    def gotRecursiveResponse(self, answers, message, protocol, address):
        answers = answers.answers
        message.auth = 0
        if len(answers):
            message.answers = answers
        else:
            message.rCode = dns.ENAME
        self.sendReply(protocol, message, address)
        if self.verbose:
            log.msg(
                "Recursive lookup found %d record%s" % (
                    len(answers), len(answers) != 1 and "s" or ""
                )
            )
            
    
    def recursiveLookupFailed(self, failure, message, protocol, address):
        message.rCode = dns.ESERVER
        self.sendReply(protocol, message, protocol, address)
        if self.verbose:
            log.msg("Recursive lookup failed")


    def handleQuery(self, message, protocol, address):
        answers = []
        for q in message.queries:
            for a in self.authorities:
                for r in a.records.get(str(q.name).lower(), ()):
                    if q.type == r.TYPE or q.type == dns.ALL_RECORDS:
                        answers.append(dns.RRHeader(str(q.name), r.TYPE, q.cls, 10))
                        answers[-1].payload = r
        if len(answers):
            message.answers = answers
            message.auth = 1
            self.sendReply(protocol, message, address)
        elif self.resolver:
            # Try a recursive lookup!  Hoot!
            if address:
                self.resolver.queryUDP(message.queries).addCallback(
                    self.gotRecursiveResponse, message, protocol, address
                )
            else:
                self.resolver.queryTCP(message.queries).addCallback(
                    self.gotRecursiveResponse, protocol, None
                ).addErrback(
                    self.recursiveLookupFailed, message, protocol, address
                )
            log.msg("Handling query recursively")
        else:
            mesage.answers = []
            self.sendReply(protocol, message, address)


    def handleInverseQuery(self, message, protocol, address):
        message.rCode = dns.ENOTIMP
        self.sendReply(protocol, message, address)


    def handleStatus(self, message, protocol, address):
        message.rCode = dns.ENOTIMP
        self.sendReply(protocol, message, address)


    def handleOther(self, message, protocol, address):
        message.rCode = dns.ENOTIMP
        self.sendReply(protocol, message, address)


    def messageReceived(self, message, protocol, address = None):
        if self.verbose:
            if self.verbose > 1:
                s = ' '.join([str(q) for q in message.queries])
            elif self.verbose > 0:
                s = ' '.join([dns.QUERY_TYPES.get(q.type, 'UNKNOWN') for q in message.queries])

            if not len(s):
                log.msg("Empty query from %r" % ((address or protocol.transport.getPeer()),))
            else:
                log.msg("%s query from %r" % (s, address or protocol.transport.getPeer()))

        message.recAv = self.resolver is not None
        message.answer = 1

        if message.opCode == dns.OP_QUERY:
            self.handleQuery(message, protocol, address)
        elif message.opCode == dns.OP_INVERSE:
            self.handleInverseQuery(message, protocol, address)
        elif message.opCode == dns.OP_STATUS:
            self.handleStatus(message, protocol, address)
        else:
            self.handleOther(message, protocol, address)
