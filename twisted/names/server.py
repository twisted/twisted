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
from twisted.names.authority import FileAuthority
from twisted.names.secondary import SecondaryAuthority
from twisted.python import log



def _nameOrder(name1, name2):
    """
    A DNS name comparison function which compares names based on their
    constituent labels.

    Designed to be used as the C{cmp} parameter to L{sorted}.

    For example::
        sorted(namesList, cmp=_nameOrder)

        ['subdomainA.example.com',
         'subdomainB.example.com',
         'subdomaina.example.com',
         'example.com',
         'com',
         'net',
         'example.org']

    @type name1: C{bytes}
    @param name1: A DNS name for comparison.

    @type name2: C{bytes}
    @param name2: A DNS name for comparison.

    @return: -1 if C{name1} is a subdomain of C{name2}. 0 if C{name1}
        and C{name2} are equal. +1 if C{name1} is a parent of
        C{name2}. If C{name1} and C{name2} do not have a hierarchical
        relationship, each of their labels are compared in reverse
        order.
    """
    labels1 = name1.split('.')
    labels2 = name2.split('.')

    # Enumerate the label lists in reverse
    for l1, l2 in zip(reversed(labels1), reversed(labels2)):
        if l1 != l2:
            # Compare the mismatched labels alphabetically.
            return cmp(l1, l2)

    # The names must have different lengths and share a common tail or
    # they are equal so compare by length.  length2 goes first so that
    # longer label sequences win.
    return cmp(len(labels2), len(labels1))



def _nameOfAuthority(authority):
    """
    Get the zone root name for an authority based on its type.

    @type authority: L{FileAuthority} or L{SecondaryAuthority}
    @param authority: The authority instance to inspect for a zone
        root name.

    @return: The C{str} root domain name of the zone represented by
        C{authority} or C{b''} if C{authority} is of unknown type.
    """
    if isinstance(authority, FileAuthority):
        return authority.soa[0]
    elif isinstance(authority, SecondaryAuthority):
        return authority.domain
    else:
        return b''



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

    def __init__(self, authorities=None, caches=None, clients=None, verbose=0):
        """
        @type authorities: L{list} of L{FileAuthority} or
            L{SecondaryAuthority} instances. Default C{None}.
        @param authorities: A list of L{FileAuthority} or
            L{SecondaryAuthority} instances which implement
            L{IResolver} and return authoritative DNS responses. These
            will be re-ordered so that authorities representing child
            zones will be queried before the parent zones. These will
            be queried before the L{IResolver} providers in C{caches}
            or C{clients}.

        @type caches: L{list} of L{cache.CacheResolver} instances. Default C{None}.
        @param caches: A list of L{cache.CacheResolver} instances
            which implement L{IResolver}. Only the first cache will be
            written to so C{caches} will normally contain a single
            cache. The first cache will be assigned to C{self.cache}
            and that cache will be updated whenever a client in
            C{clients} receives a successful response.

        @type clients: L{list} of L{IResolver} providers. Default C{None}.
        @param clients: These I{IResolver} objects will be queried
            after C{authorities} and C{caches}. These may be mixture
            of L{hosts.Resolver}, L{client.Resolver} or
            L{root.Resolver} instances.

        @type verbose: C{bool}
        @param verbose: Set to C{True} to enable verbose
            logging. Default C{False}.
        """
        resolvers = []
        if authorities is not None:
            # Sort on the zone root name, which is found in
            # FileAuthority.soa ( a 2tuple(name, record) ).
            resolvers.extend(
                sorted(authorities,
                       key=_nameOfAuthority,
                       cmp=_nameOrder))
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
