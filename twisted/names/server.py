# -*- test-case-name: twisted.names.test.test_names -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Async DNS server

Future plans:
    - Better config file format maybe
    - Make sure to differentiate between different classes
    - notice truncation bit

Important: No additional processing is done on some of the record types.
This violates the most basic RFC and is just plain annoying
for resolvers to deal with.  Fix it.

@author: Jp Calderone
"""

import time

from twisted.internet import protocol
from twisted.names import dns, resolve
from twisted.python import log


class DNSServerFactory(protocol.ServerFactory):
    """
    Server factory and tracker for L{DNSProtocol} connections.  This
    class also provides records for responses to DNS queries.

    @ivar connections: A list of all the connected L{DNSProtocol}
        instances using this object as their controller.
    @type connections: C{list} of L{DNSProtocol}
    """

    protocol = dns.DNSProtocol
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
        self.connections = []


    def buildProtocol(self, addr):
        p = self.protocol(self)
        p.factory = self
        return p


    def connectionMade(self, protocol):
        """
        Track a newly connected L{DNSProtocol}.
        """
        self.connections.append(protocol)


    def connectionLost(self, protocol):
        """
        Stop tracking a no-longer connected L{DNSProtocol}.
        """
        self.connections.remove(protocol)


    def sendReply(self, protocol, message, address):
        if self.verbose > 1:
            s = ' '.join([str(a.payload) for a in message.answers])
            auth = ' '.join([str(a.payload) for a in message.authority])
            add = ' '.join([str(a.payload) for a in message.additional])
            if not s:
                log.msg("Replying with no answers")
            else:
                log.msg("Answers are " + s)
                log.msg("Authority is " + auth)
                log.msg("Additional is " + add)

        if address is None:
            protocol.writeMessage(message)
        else:
            protocol.writeMessage(message, address)

        if self.verbose > 1:
            log.msg("Processed query in %0.3f seconds" % (time.time() - message.timeReceived))


    def gotResolverResponse(self, (ans, auth, add), protocol, message, address):
        message.rCode = dns.OK
        message.answers = ans
        for x in ans:
            if x.isAuthoritative():
                message.auth = 1
                break
        message.authority = auth
        message.additional = add
        self.sendReply(protocol, message, address)

        l = len(ans) + len(auth) + len(add)
        if self.verbose:
            log.msg("Lookup found %d record%s" % (l, l != 1 and "s" or ""))

        if self.cache and l:
            self.cache.cacheResult(
                message.queries[0], (ans, auth, add)
            )


    def gotResolverError(self, failure, protocol, message, address):
        if failure.check(dns.DomainError, dns.AuthoritativeDomainError):
            message.rCode = dns.ENAME
        else:
            message.rCode = dns.ESERVER
            log.err(failure)

        self.sendReply(protocol, message, address)
        if self.verbose:
            log.msg("Lookup failed")


    def handleQuery(self, message, protocol, address):
        # Discard all but the first query!  HOO-AAH HOOOOO-AAAAH
        # (no other servers implement multi-query messages, so we won't either)
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


    def messageReceived(self, message, proto, address = None):
        message.timeReceived = time.time()

        if self.verbose:
            if self.verbose > 1:
                s = ' '.join([str(q) for q in message.queries])
            elif self.verbose > 0:
                s = ' '.join([dns.QUERY_TYPES.get(q.type, 'UNKNOWN') for q in message.queries])

            if not len(s):
                log.msg("Empty query from %r" % ((address or proto.transport.getPeer()),))
            else:
                log.msg("%s query from %r" % (s, address or proto.transport.getPeer()))

        message.recAv = self.canRecurse
        message.answer = 1

        if not self.allowQuery(message, proto, address):
            message.rCode = dns.EREFUSED
            self.sendReply(proto, message, address)
        elif message.opCode == dns.OP_QUERY:
            self.handleQuery(message, proto, address)
        elif message.opCode == dns.OP_INVERSE:
            self.handleInverseQuery(message, proto, address)
        elif message.opCode == dns.OP_STATUS:
            self.handleStatus(message, proto, address)
        elif message.opCode == dns.OP_NOTIFY:
            self.handleNotify(message, proto, address)
        else:
            self.handleOther(message, proto, address)


    def allowQuery(self, message, protocol, address):
        # Allow anything but empty queries
        return len(message.queries)
