# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Subclasses of dns.DNSDatagramProtocol, dns.DNSProtocol and
client.Resolver which integrate EDNSMessage.
"""

from twisted.internet import error
from twisted.names import client, dns
from twisted.names.dns import _EDNSMessage



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
        self._messageOptions = kwargs.pop('messageOptions', {})
        dns.DNSDatagramProtocol.__init__(self, *args, **kwargs)


    def writeMessage(self, message, address):
        """
        Again, this is a hack, but it demonstrates the usefulness of
        _EDNSMessage.fromMessage for wrapping dns.Message.

        It might be convenient if I could provide EDNS specific
        keyword arguments to fromMessage - ednsVersion, maxSize, etc.
        """
        message = _EDNSMessage.fromMessage(message)
        for k, v in self._messageOptions.items():
            setattr(message, k, v)
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
        self._messageOptions = kwargs.pop('messageOptions', {})
        dns.DNSProtocol.__init__(self, *args, **kwargs)


    def writeMessage(self, message):
        message = _EDNSMessage.fromMessage(message)
        for k, v in self._messageOptions.items():
            setattr(message, k, v)
        return dns.DNSProtocol.writeMessage(self, message)


    def _query(self, *args, **kwargs):
        d = dns.DNSProtocol._query(self, *args, **kwargs)
        d.addCallback(_EDNSMessage.fromMessage)
        return d



class EDNSClientFactory(client.DNSClientFactory):
    def __init__(self, *args, **kwargs):
        self._messageOptions = kwargs.pop('messageOptions', {})
        client.DNSClientFactory.__init__(self, *args, **kwargs)

    def buildProtocol(self, addr):
        p = EDNSStreamProtocol(controller=self.controller,
                               messageOptions=self._messageOptions)
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
        self._messageOptions = kwargs.pop('messageOptions', {})
        client.Resolver.__init__(self, *args, **kwargs)
        self.factory = EDNSClientFactory(self,
                                         timeout=self.timeout,
                                         messageOptions=self._messageOptions)


    def _connectedProtocol(self):
        proto = EDNSDatagramProtocol(controller=self,
                                     reactor=self._reactor,
                                     messageOptions=self._messageOptions)
        while True:
            try:
                self._reactor.listenUDP(dns.randomSource(), proto)
            except error.CannotListenError:
                pass
            else:
                return proto
