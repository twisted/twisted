# -*- test-case-name: twisted.names.test.test_names,twisted.names.test.test_server -*-
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
    Server factory and tracker for L{DNSProtocol} connections.  This class also
    provides records for responses to DNS queries.

    @ivar cache: A L{Cache<twisted.names.cache.Cache>} instance whose
        C{cacheResult} method is called when a response is received from one of
        C{clients}. Defaults to L{None} if no caches are specified. See
        C{caches} of L{__init__} for more details.
    @type cache: L{Cache<twisted.names.cache.Cache} or L{None}

    @ivar canRecurse: A flag indicating whether this server is capable of
        performing recursive DNS resolution.
    @type canRecurse: L{bool}

    @ivar resolver: A L{resolve.ResolverChain} containing an ordered list of
        C{authorities}, C{caches} and C{clients} to which queries will be
        dispatched.
    @type resolver: L{resolve.ResolverChain}

    @ivar verbose: See L{__init__}

    @ivar connections: A list of all the connected L{DNSProtocol} instances
        using this object as their controller.
    @type connections: C{list} of L{DNSProtocol} instances

    @ivar protocol: A callable used for building a DNS stream protocol. Called
        by L{DNSServerFactory.buildProtocol} and passed the L{DNSServerFactory}
        instance as the one and only positional argument.  Defaults to
        L{dns.DNSProtocol}.
    @type protocol: L{IProtocolFactory} constructor
    """

    protocol = dns.DNSProtocol
    cache = None

    def __init__(self, authorities=None, caches=None, clients=None, verbose=0):
        """
        @param authorities: Resolvers which provide authoritative answers.
        @type authorities: L{list} of L{IResolver} providers

        @param caches: Resolvers which provide cached non-authoritative
            answers. The first cache instance is assigned to
            C{DNSServerFactory.cache} and its C{cacheResult} method will be
            called when a response is received from one of C{clients}.
        @type caches: L{list} of L{Cache<twisted.names.cache.Cache} instances

        @param clients: Resolvers which are capable of performing recursive DNS
            lookups.
        @type clients: L{list} of L{IResolver} providers

        @param verbose: An integer controlling the verbosity of logging of
            queries and responses. Default is C{0} which means no logging. Set
            to C{2} to enable logging of full query and response messages.
        @param verbose: L{int}
        """
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


    def _verboseLog(self, *args, **kwargs):
        """
        Log a message only if verbose logging is enabled.

        @param args: Positional arguments which will be passed to C{log.msg}
        @param kwargs: Keyword arguments which will be passed to C{log.msg}
        """
        if self.verbose > 0:
            log.msg(*args, **kwargs)


    def buildProtocol(self, addr):
        p = self.protocol(self)
        p.factory = self
        return p


    def connectionMade(self, protocol):
        """
        Track a newly connected L{DNSProtocol}.

        @param protocol: The protocol instance to be tracked.
        @type protocol: L{dns.DNSProtocol}
        """
        self.connections.append(protocol)


    def connectionLost(self, protocol):
        """
        Stop tracking a no-longer connected L{DNSProtocol}.

        @param protocol: The tracked protocol instance to be which has been
            lost.
        @type protocol: L{dns.DNSProtocol}
        """
        self.connections.remove(protocol)


    def sendReply(self, protocol, message, address):
        """
        Send a response C{message} to a given C{address} via the supplied
        C{protocol}.

        Message payload will be logged if C{DNSServerFactory.verbose} is C{>1}.

        @param protocol: The DNS protocol instance to which to send the message.
        @type protocol: L{dns.DNSDatagramProtocol} or L{dns.DNSProtocol}

        @param message: The DNS message to be sent.
        @type message: L{dns.Message}

        @param address: The address to which the message will be sent or L{None}
            if C{protocol} is a stream protocol.
        @type address: L{tuple} or L{None}
        """
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

        self._verboseLog(
            "Processed query in %0.3f seconds" % (
                time.time() - message.timeReceived))


    def gotResolverResponse(self, (ans, auth, add), protocol, message, address):
        """
        A callback used by L{DNSServerFactory.handleQuery} for handling the
        deferred response from C{self.resolver.query}.

        Constructs a response message by combining the original query message
        with the resolved answer, authority and additional records.

        Marks the response message as authoritative if any of the resolved
        answers are found to be authoritative.

        The resolved answers count will be logged if C{DNSServerFactory.verbose}
        is C{>1}.

        @param ans: A list of answer records
        @type ans: L{list} of L{dns.RRHeader} instances

        @param auth: A list of authority records
        @type auth: L{list} of L{dns.RRHeader} instances

        @param add: A list of additional records
        @type add: L{list} of L{dns.RRHeader} instances

        @param protocol: The DNS protocol instance to which to send a response
            message.
        @type protocol: L{dns.DNSDatagramProtocol} or L{dns.DNSProtocol}

        @param message: The original DNS query message for which a response
            message will be constructed.
        @type message: L{dns.Message}

        @param address: The address to which the response message will be sent
            or L{None} if C{protocol} is a stream protocol.
        @type address: L{tuple} or L{None}
        """
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
        self._verboseLog("Lookup found %d record%s" % (l, l != 1 and "s" or ""))

        if self.cache and l:
            self.cache.cacheResult(
                message.queries[0], (ans, auth, add)
            )


    def gotResolverError(self, failure, protocol, message, address):
        """
        A callback used by L{DNSServerFactory.handleQuery} for handling deferred
        errors from C{self.resolver.query}.

        Constructs a response message from the original query message by
        assigning a suitable error code to C{rCode}.

        An error message will be logged if C{DNSServerFactory.verbose} is C{>1}.

        @param failure: The reason for the failed resolution (as reported by
            C{self.resolver.query}).
        @type failure: L{Failure<twisted.python.failure.Failure>}

        @param protocol: The DNS protocol instance to which to send a response
            message.
        @type protocol: L{dns.DNSDatagramProtocol} or L{dns.DNSProtocol}

        @param message: The original DNS query message for which a response
            message will be constructed.
        @type message: L{dns.Message}

        @param address: The address to which the response message will be sent
            or L{None} if C{protocol} is a stream protocol.
        @type address: L{tuple} or L{None}
        """
        if failure.check(dns.DomainError, dns.AuthoritativeDomainError):
            message.rCode = dns.ENAME
        else:
            message.rCode = dns.ESERVER
            log.err(failure)

        self.sendReply(protocol, message, address)
        self._verboseLog("Lookup failed")


    def handleQuery(self, message, protocol, address):
        """
        Called by L{DNSServerFactory.messageReceived} when a query message is
        received.

        Takes the first query from the received message and dispatches it to
        C{self.resolver.query}.

        Adds callbacks L{DNSServerFactory.gotResolverResponse} and
        L{DNSServerFactory.gotResolverError} to the resulting deferred.

        Note: Multiple queries in a single message are not supported because
        there is no standard way to respond with multiple rCodes, auth,
        etc. This is consistent with other DNS server implementations. See
        U{http://tools.ietf.org/html/draft-ietf-dnsext-edns1-03} for a proposed
        solution.

        @param protocol: The DNS protocol instance to which to send a response
            message.
        @type protocol: L{dns.DNSDatagramProtocol} or L{dns.DNSProtocol}

        @param message: The original DNS query message for which a response
            message will be constructed.
        @type message: L{dns.Message}

        @param address: The address to which the response message will be sent
            or L{None} if C{protocol} is a stream protocol.
        @type address: L{tuple} or L{None}

        @return: A C{deferred} which fires with the resolved result or error of
            the first query in C{message}.
        @rtype: L{Deferred<twisted.internet.defer.Deferred>}
        """
        query = message.queries[0]

        return self.resolver.query(query).addCallback(
            self.gotResolverResponse, protocol, message, address
        ).addErrback(
            self.gotResolverError, protocol, message, address
        )


    def handleInverseQuery(self, message, protocol, address):
        """
        Called by L{DNSServerFactory.messageReceived} when an inverse query
        message is received.

        Replies with a I{Not Implemented} error by default.

        An error message will be logged if C{DNSServerFactory.verbose} is C{>1}.

        Override in a subclass.

        @param protocol: The DNS protocol instance to which to send a response
            message.
        @type protocol: L{dns.DNSDatagramProtocol} or L{dns.DNSProtocol}

        @param message: The original DNS query message for which a response
            message will be constructed.
        @type message: L{dns.Message}

        @param address: The address to which the response message will be sent
            or L{None} if C{protocol} is a stream protocol.
        @type address: L{tuple} or L{None}
        """
        message.rCode = dns.ENOTIMP
        self.sendReply(protocol, message, address)
        self._verboseLog("Inverse query from %r" % (address,))


    def handleStatus(self, message, protocol, address):
        """
        Called by L{DNSServerFactory.messageReceived} when a status message is
        received.

        Replies with a I{Not Implemented} error by default.

        An error message will be logged if C{DNSServerFactory.verbose} is C{>1}.

        Override in a subclass.

        @param protocol: The DNS protocol instance to which to send a response
            message.
        @type protocol: L{dns.DNSDatagramProtocol} or L{dns.DNSProtocol}

        @param message: The original DNS query message for which a response
            message will be constructed.
        @type message: L{dns.Message}

        @param address: The address to which the response message will be sent
            or L{None} if C{protocol} is a stream protocol.
        @type address: L{tuple} or L{None}
        """
        message.rCode = dns.ENOTIMP
        self.sendReply(protocol, message, address)
        self._verboseLog("Status request from %r" % (address,))


    def handleNotify(self, message, protocol, address):
        """
        Called by L{DNSServerFactory.messageReceived} when a notify message is
        received.

        Replies with a I{Not Implemented} error by default.

        An error message will be logged if C{DNSServerFactory.verbose} is C{>1}.

        Override in a subclass.

        @param protocol: The DNS protocol instance to which to send a response
            message.
        @type protocol: L{dns.DNSDatagramProtocol} or L{dns.DNSProtocol}

        @param message: The original DNS query message for which a response
            message will be constructed.
        @type message: L{dns.Message}

        @param address: The address to which the response message will be sent
            or L{None} if C{protocol} is a stream protocol.
        @type address: L{tuple} or L{None}
        """
        message.rCode = dns.ENOTIMP
        self.sendReply(protocol, message, address)
        self._verboseLog("Notify message from %r" % (address,))


    def handleOther(self, message, protocol, address):
        """
        Called by L{DNSServerFactory.messageReceived} when a message with
        unrecognised I{OPCODE} is received.

        Replies with a I{Not Implemented} error by default.

        An error message will be logged if C{DNSServerFactory.verbose} is C{>1}.

        Override in a subclass.

        @param protocol: The DNS protocol instance to which to send a response
            message.
        @type protocol: L{dns.DNSDatagramProtocol} or L{dns.DNSProtocol}

        @param message: The original DNS query message for which a response
            message will be constructed.
        @type message: L{dns.Message}

        @param address: The address to which the response message will be sent
            or L{None} if C{protocol} is a stream protocol.
        @type address: L{tuple} or L{None}
        """
        message.rCode = dns.ENOTIMP
        self.sendReply(protocol, message, address)
        self._verboseLog(
            "Unknown op code (%d) from %r" % (message.opCode, address))


    def messageReceived(self, message, proto, address=None):
        """
        L{DNSServerFactory.messageReceived} is called by protocols which are
        under the control of this L{DNSServerFactory} whenever they receive a
        DNS query message or an unexpected / duplicate / late DNS response
        message.

        L{DNSServerFactory.allowQuery} is called with the received message,
        protocol and origin address. If it returns L{False}, a C{dns.EREFUSED}
        response is sent back to the client.

        Otherwise the received message is dispatched to one of
        L{DNSServerFactory.handleQuery}, L{DNSServerFactory.handleInverseQuery},
        L{DNSServerFactory.handleStatus}, L{DNSServerFactory.handleNotify}, or
        L{DNSServerFactory.handleOther} depending on the I{OPCODE} of the
        received message.

        If C{DNSServerFactory.verbose} is C{>0} all received messages will be
        logged in more or less detail depending on the value of C{verbose}.

        @param message: The DNS message that was received.
        @type message: L{dns.Message}

        @param proto: The DNS protocol instance which received the message
        @type proto: L{dns.DNSDatagramProtocol} or L{dns.DNSProtocol}

        @param address: The address from which the message was received. Only
            provided for messages received by datagram protocols. The origin of
            Messages received from stream protocols can be gleaned from the
            protocol C{transport} attribute.
        @type address: L{tuple} or L{None}
        """
        message.timeReceived = time.time()

        if self.verbose:
            if self.verbose > 1:
                s = ' '.join([str(q) for q in message.queries])
            else:
                s = ' '.join([dns.QUERY_TYPES.get(q.type, 'UNKNOWN')
                              for q in message.queries])
            if not len(s):
                log.msg(
                    "Empty query from %r" % (
                        (address or proto.transport.getPeer()),))
            else:
                log.msg(
                    "%s query from %r" % (
                        s, address or proto.transport.getPeer()))

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
        """
        Called by L{DNSServerFactory.messageReceived} to decide whether to
        process a received message or to reply with C{dns.EREFUSED}.

        This default implementation permits anything but empty queries.

        Override in a subclass to implement alternative policies.

        @param message: The DNS message that was received.
        @type message: L{dns.Message}

        @param protocol: The DNS protocol instance which received the message
        @type protocol: L{dns.DNSDatagramProtocol} or L{dns.DNSProtocol}

        @param address: The address from which the message was received. Only
            provided for messages received by datagram protocols. The origin of
            Messages received from stream protocols can be gleaned from the
            protocol C{transport} attribute.
        @type address: L{tuple} or L{None}

        @return: L{True} if the received message contained one or more queries,
            else L{False}.
        @rtype: L{bool}
        """
        return len(message.queries)
