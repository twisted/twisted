# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
_EDNSMessage copied from #5675.

Plus subclasses of dns.DNSDatagramProtocol, dns.DNSProtocol and
client.Resolver which integrate EDNSMessage.
"""

from twisted.internet import error
from twisted.names import client, dns
from twisted.names.dns import EFORMAT, Message, OPT, _OPTHeader, OP_QUERY
from twisted.python import util as tputil



class EDNSDatagramProtocol(dns.DNSDatagramProtocol):
    """
    This hack is necessary because dns.DNSDatagramProtocol is
    hardcoded to use dns.Message for building outbound query datagrams
    and for decoding incoming datagrams.

    It would be easier to integrate new EDNS components if DNS
    protocols had a convenient way of specifying an alternative
    message factory.
    """
    def __init__(self, *args, **kwargs):
        """
        This seems ugly too. If I could provide a messageFactory
        function, these EDNSMessage arguments needn't be passed
        explicitly to the DNS protocols. Instead just pass
        partial(EDNSMessage, ednsVersion=x, maxSize=y).
        """
        self.ednsVersion = kwargs.pop('ednsVersion', 0)
        self.maxSize = kwargs.pop('maxSize', 4096)
        self.dnssecOK = kwargs.pop('dnssecOK', False)

        dns.DNSDatagramProtocol.__init__(self, *args, **kwargs)


    def writeMessage(self, message, address):
        """
        Again, this is a hack, but it demonstrates the usefulness of
        _EDNSMessage.fromMessage for wrapping dns.Message.

        It might be convenient if I could provide EDNS specific
        keyword arguments to fromMessage - ednsVersion, maxSize, etc.
        """
        message = _EDNSMessage.fromMessage(message)

        message.ednsVersion = self.ednsVersion
        message.maxSize = self.maxSize
        message.dnssecOK = self.dnssecOK

        return dns.DNSDatagramProtocol.writeMessage(self, message, address)


    def _query(self, *args, **kwargs):
        d = dns.DNSDatagramProtocol._query(self, *args, **kwargs)

        return d.addCallback(_EDNSMessage.fromMessage)



class EDNSStreamProtocol(dns.DNSProtocol):
    """
    See comments for EDNSDatagramProtocol.

    It's a shame we have to duplicate the same hacks for the TCP DNS
    protocol.

    If DNSDatagramProtocol used connected UDP instead, there would be
    less difference between the UDP and TCP protocols eg writeMessage
    would have a consistent signature and maybe this duplication
    wouldn't be necessary.
    """
    def __init__(self, *args, **kwargs):
        self.ednsVersion = kwargs.pop('ednsVersion', 0)
        self.maxSize = kwargs.pop('maxSize', 4096)
        self.dnssecOK = kwargs.pop('dnssecOK', False)

        dns.DNSProtocol.__init__(self, *args, **kwargs)


    def writeMessage(self, message):
        message = _EDNSMessage.fromMessage(message)
        message.ednsVersion = self.controller.ednsVersion
        message.maxSize = self.controller.maxSize
        message.dnssecOK = self.controller.dnssecOK

        return dns.DNSProtocol.writeMessage(self, message)


    def _query(self, *args, **kwargs):
        d = dns.DNSProtocol._query(self, *args, **kwargs)
        d.addCallback(_EDNSMessage.fromMessage)
        return d



class EDNSClientFactory(client.DNSClientFactory):
    def buildProtocol(self, addr):
        p = EDNSStreamProtocol(controller=self.controller)
        p.factory = self
        return p



class EDNSResolver(client.Resolver):
    """
    client.Resolver is hardcoded to use dns.DNSDatagramProtcol and
    dns.DNSProtocol (via client.DNSClientFactory).

    It would be nice if I could specify dnsDatagramProtocolFactory and
    dnsStreamProtocolFactory as arguments to client.Resolver.

    Also need to consider whether client.Resolver is a suitable place
    to do EDNS buffer size detection.

    The IResolver methods of client.Resolver currently respond to
    truncated UDP messages by issuing a follow up TCP query.

    In addition they could respond to timeouts by re-issue a UDP query
    with a smaller advertised EDNS buffersize.

    See
     * https://tools.ietf.org/html/rfc6891#section-6.2.2
     * https://www.dns-oarc.net/oarc/services/replysizetest
    """
    def __init__(self, *args, **kwargs):
        self.ednsVersion = kwargs.pop('ednsVersion', 0)
        self.maxSize = kwargs.pop('maxSize', 4096)
        self.dnssecOK = kwargs.pop('dnssecOK', False)

        client.Resolver.__init__(self, *args, **kwargs)

        self.factory = EDNSClientFactory(self, self.timeout)


    def _connectedProtocol(self):
        proto = EDNSDatagramProtocol(
            ednsVersion=self.ednsVersion,
            maxSize=self.maxSize,
            dnssecOK=self.dnssecOK,
            controller=self,
            reactor=self._reactor)

        while True:
            try:
                self._reactor.listenUDP(dns.randomSource(), proto)
            except error.CannotListenError:
                pass
            else:
                return proto



class _EDNSMessage(tputil.FancyStrMixin, tputil.FancyEqMixin, object):
    """
    An C{EDNS} message.

    Designed for compatibility with L{Message} but with a narrower
    public interface.

    Most importantly, L{_EDNSMessage.fromStr} will interpret and
    remove OPT records that are present in the additional records
    section.

    The OPT records are used to populate certain EDNS specific
    attributes.

    L{_EDNSMessage.toStr} will add suitable OPT records to the
    additional section to represent the extended EDNS information.

    @see: U{https://tools.ietf.org/html/rfc6891}

    @ivar id: A 16 bit identifier assigned by the program that
        generates any kind of query.  This identifier is copied the
        corresponding reply and can be used by the requester to match
        up replies to outstanding queries.

    @ivar answer: A one bit field that specifies whether this message
        is a query (0), or a response (1).

    @ivar opCode: A four bit field that specifies kind of query in
        this message.  This value is set by the originator of a query
        and copied into the response.  The values are:
                0               a standard query (QUERY)
                1               an inverse query (IQUERY)
                2               a server status request (STATUS)
                3-15            reserved for future use

    @ivar auth: Authoritative Answer - this bit is valid in responses,
        and specifies that the responding name server is an authority
        for the domain name in question section.

    @ivar trunc: TrunCation - specifies that this message was
        truncated due to length greater than that permitted on the
        transmission channel.

    @ivar recDes: Recursion Desired - this bit may be set in a query
        and is copied into the response.  If RD is set, it directs the
        name server to pursue the query recursively.  Recursive query
        support is optional.

    @ivar recAv: Recursion Available - this be is set or cleared in a
        response, and denotes whether recursive query support is
        available in the name server.

    @ivar rCode: Response code - this 4 bit field is set as part of
        responses.  The values have the following interpretation:
                0               No error condition

                1               Format error - The name server was
                                unable to interpret the query.
                2               Server failure - The name server was
                                unable to process this query due to a
                                problem with the name server.

                3               Name Error - Meaningful only for
                                responses from an authoritative name
                                server, this code signifies that the
                                domain name referenced in the query does
                                not exist.

                4               Not Implemented - The name server does
                                not support the requested kind of query.

                5               Refused - The name server refuses to
                                perform the specified operation for
                                policy reasons.  For example, a name
                                server may not wish to provide the
                                information to the particular requester,
                                or a name server may not wish to perform
                                a particular operation (e.g., zone
                                transfer) for particular data.

    @ivar ednsVersion: Indicates the EDNS implementation level. Set to
        C{None} to prevent any EDNS attributes and options being added
        to the encoded byte string.

    @ivar queries: A L{list} of L{Query} instances.

    @ivar answers: A L{list} of L{RRHeader} instances.

    @ivar authority: A L{list} of L{RRHeader} instances.

    @ivar additional: A L{list} of L{RRHeader} instances.
    """

    showAttributes = (
        'id', 'answer', 'opCode', 'auth', 'trunc',
        'recDes', 'recAv', 'rCode', 'ednsVersion', 'dnssecOK',
        'maxSize',
        'queries', 'answers', 'authority', 'additional')

    compareAttributes = showAttributes

    def __init__(self, id=0, answer=0,
                 opCode=OP_QUERY, auth=0,
                 trunc=0, recDes=0,
                 recAv=0, rCode=0, ednsVersion=0, dnssecOK=False, maxSize=512,
                 queries=None, answers=None, authority=None, additional=None):
        """
        All arguments are stored as attributes with the same names.

        @see: L{_EDNSMessage} for an explanation of the meaning of
            each attribute.

        @type id: C{int}
        @type answer: C{int}
        @type opCode: C{int}
        @type auth: C{int}
        @type trunc: C{int}
        @type recDes: C{int}
        @type recAv: C{int}
        @type rCode: C{int}
        @type ednsVersion: C{int} or C{None}
        @type queries: C{list} of L{Query}
        @type answers: C{list} of L{RRHeader}
        @type authority: C{list} of L{RRHeader}
        @type additional: C{list} of L{RRHeader}
        """
        self.id = id
        self.answer = answer
        self.opCode = opCode

        # XXX: AA bit can be determined by checking for an
        # authoritative answer record whose name matches the query
        # name - perhaps in a higher level EDNSResponse class?
        self.auth = auth

        # XXX: TC bit can be determined during encoding based on EDNS max
        # packet size.
        self.trunc = trunc

        self.recDes = recDes
        self.recAv = recAv
        self.rCode = rCode
        self.ednsVersion = ednsVersion
        self.dnssecOK = dnssecOK
        self.maxSize = maxSize

        self.queries = queries or []
        self.answers = answers or []
        self.authority = authority or []
        self.additional = additional or []

        self._decodingErrors = []


    def toStr(self):
        """
        Encode to wire format.

        If C{ednsVersion} is not None, an L{_OPTHeader} instance
        containing all the I{EDNS} specific attributes and options
        will be appended to the list of C{additional} records and this
        will be encoded into the byte string as an C{OPT} record byte
        string.

        @return: A L{bytes} string.
        """
        m = Message(
            id=self.id,
            answer=self.answer,
            opCode=self.opCode,
            auth=self.auth,
            trunc=self.trunc,
            recDes=self.recDes,
            recAv=self.recAv,
            rCode=self.rCode,
            maxSize=self.maxSize)

        m.queries = list(self.queries)
        m.answers = list(self.answers)
        m.authority = list(self.authority)
        m.additional = list(self.additional)

        if self.ednsVersion is not None:
            o = _OPTHeader(version=self.ednsVersion,
                           udpPayloadSize=self.maxSize,
                           dnssecOK=self.dnssecOK)
            m.additional.append(o)

        return m.toStr()


    @classmethod
    def fromMessage(cls, message):
        """
        Construct and return a new L(_EDNSMessage} whose attributes
        and records are derived from the attributes and records of
        C{message} (a L{Message} instance)

        If present, an I{OPT} record will be extracted from the
        C{additional} section and its attributes and options will be
        used to set the EDNS specific attributes C{extendedRCODE},
        c{ednsVersion}, c{dnssecOK}, c{ednsOptions}.

        The C{extendedRCODE} will be combined with C{message.rCode}
        and assigned to C{self.rCode}.

        If multiple I{OPT} records are found, this is considered an
        error and no EDNS specific attributes will be
        set. Additionally, an L{EFORMAT} error will be appended to
        C{_decodingErrors}.
        """
        additional = []
        optRecords = []
        for r in message.additional:
            if r.type == OPT:
                optRecords.append(_OPTHeader.fromRRHeader(r))
            else:
                additional.append(r)

        newMessage = cls(
            id=message.id,
            answer=message.answer,
            opCode=message.opCode,
            auth=message.auth,
            trunc=message.trunc,
            recDes=message.recDes,
            recAv=message.recAv,
            rCode=message.rCode,
            # Default to None, it will be updated later when the OPT
            # records are parsed.
            ednsVersion=None,
            queries=list(message.queries),
            answers=list(message.answers),
            authority=list(message.authority),
            additional=additional,
            )

        if optRecords:
            if len(optRecords) > 1:
                newMessage._decodingErrors.append(EFORMAT)
            else:
                opt = optRecords[0]
                newMessage.ednsVersion = opt.version
                newMessage.maxSize = opt.udpPayloadSize
                newMessage.dnssecOK = opt.dnssecOK

        return newMessage


    def fromStr(self, bytes):
        """
        Decode from wire format, saving flags, values and records to
        this L{_EDNSMessage} instance in place.

        @type bytes: L{bytes}
        @param bytes: The full byte string to be decoded.
        """
        m = Message()
        m.fromStr(bytes)

        ednsMessage = self.fromMessage(m)
        self.__dict__ = ednsMessage.__dict__
