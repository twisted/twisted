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

"""
Async DNS server

API Stability: Unstable

Future plans: Better config file format maybe;
  Make sure to differentiate between different classes;
  notice truncation bit; zone transfers, oh man, how will
  I do this!  I have no idea.  Also, authorization probably
  needs to go in a better place, and be expanded to more than
  it is now, obviously.
  
  Important: No additional processing is done on any record type.
    This violates the most basic RFC and is just plain annoying
    for resolvers to deal with.  Fix it.


@author: U{Jp Calderone <exarkun@twistedmatrix.com>}
"""

from __future__ import nested_scopes
import copy

# Twisted imports
from twisted.internet import protocol, defer
from twisted.protocols import dns
from twisted.python import failure, log

import resolve, common

class DNSServerFactory(protocol.ServerFactory):
    cache = None

    def __init__(self, authorities = None, caches = None, clients = None, verbose = 0):
        resolvers = []
        if authorities is not None:
            resolvers.extend(authorities)
        if caches is not None:
            resolvers.extend(caches)
        if clients is not None:
            resolvers.extend(clients)

        self.canRecurse = not not clients
        self.resolver = resolve.ResolverChain(resolvers)
        self.verbose = verbose
        if caches:
            self.cache = caches[-1]


    def startFactory(self):
        pass
        # self.resolver = client.theResolver


    def stopFactory(self):
        pass
        # del self.resolver


    def buildProtocol(self, addr):
        p = dns.DNSProtocol(self)
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


    def gotResolverResponse(self, responses, protocol, message, address):
        message.rCode = dns.OK
        message.answers = responses
        self.sendReply(protocol, message, address)
        if self.verbose:
            log.msg(
                "Lookup found %d record%s" % (
                    len(responses), len(responses) != 1 and "s" or ""
                )
            )
        if self.cache:
            for res in responses:
                if not res.cachedResponse:
                    self.cache.cacheResult(
                        res.name, res.type, res.cls, res.payload
                    )


    def gotResolverError(self, failure, protocol, message, address):
        if isinstance(failure.value, (dns.DomainError, dns.AuthoritativeDomainError)):
            message.rCode = dns.ENAME
        else:
            message.rCode = dns.ESERVER
            failure.printTraceback()
        self.sendReply(protocol, message, address)
        if self.verbose:
            log.msg("Lookup failed")


    def handleQuery(self, message, protocol, address):
        # Discard all but the first query!  HOO-AAH HOOOOO-AAAAH
        query = message.queries[0]
        
        return self.resolver.query(query).addCallback(
            self.gotResolverResponse, protocol, message, address
        ).addErrback(
            self.gotResolverError, protocol, message, address
        )


    def handleInverseQuery(self, message, protocol, address):
        message.rCode = dns.ENOTIMP
        self.sendReply(protocol, message, address)
        if self.verbose:
            log.msg("Inverse query from %r" % (address,))


    def handleStatus(self, message, protocol, address):
        message.rCode = dns.ENOTIMP
        self.sendReply(protocol, message, address)
        if self.verbose:
            log.msg("Status request from %r" % (address,))


    def handleNotify(self, message, protocol, address):
        message.rCode = dns.ENOTIMP
        self.sendReply(protocol, message, address)
        if self.verbose:
            log.msg("Notify message from %r" % (address,))


    def handleOther(self, message, protocol, address):
        message.rCode = dns.ENOTIMP
        self.sendReply(protocol, message, address)
        if self.verbose:
            log.msg("Unknown op code (%d) from %r" % (message.opCode, address))


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

        message.recAv = self.canRecurse
        message.answer = 1

        if not self.allowQuery(message, protocol, address):
            message.rCode = dns.EREFUSED
            self.sendReply(protocol, message, address)
        elif message.opCode == dns.OP_QUERY:
            self.handleQuery(message, protocol, address)
        elif message.opCode == dns.OP_INVERSE:
            self.handleInverseQuery(message, protocol, address)
        elif message.opCode == dns.OP_STATUS:
            self.handleStatus(message, protocol, address)
        elif message.opCode == dns.OP_NOTIFY:
            self.handleNotify(message, protocol, address)
        else:
            self.handleOther(message, protocol, address)


    def allowQuery(self, message, protocol, address):
        return 1
