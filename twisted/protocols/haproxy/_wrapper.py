# -*- test-case-name: twisted.protocols.haproxy.test.test_wrapper -*-

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Protocol wrapper that provides HAProxy PROXY protocol support.
"""

from twisted.protocols import policies
from twisted.internet import interfaces
from twisted.internet.endpoints import _WrapperServerEndpoint

from ._exc import InvalidProxyHeader
from ._v1parser import V1Parser
from ._v2parser import V2Parser



class HAProxyProtocolWrapper(policies.ProtocolWrapper, object):
    """
    A Protocol wrapper that provides HAProxy support.

    This protocol reads the PROXY stream header, v1 or v2, parses the provided
    connection data, and modifies the behavior of getPeer and getHost to return
    the data provided by the PROXY header.
    """

    V1PARSER = V1Parser
    V1BYTES = V1PARSER.PROXYSTR
    V2PARSER = V2Parser
    V2BYTES = V2PARSER.PREFIX

    def __init__(self, factory, wrappedProtocol):
        policies.ProtocolWrapper.__init__(self, factory, wrappedProtocol)
        self._proxyInfo = None
        self._parser = None


    def dataReceived(self, data):
        if self._proxyInfo:
            return self.wrappedProtocol.dataReceived(data)

        if not self._parser:
            if (
                    len(data) >= 16 and
                    data[:12] == self.V2BYTES and
                    ord(data[12:13]) & 0b11110000 == 0x20
            ):
                self._parser = self.V2PARSER()
            elif len(data) >= 8 and data[:5] == self.V1BYTES:
                self._parser = self.V1PARSER()
            else:
                self.loseConnection()
                return None

        try:
            self._proxyInfo, remaining = self._parser.feed(data)
            if remaining:
                self.wrappedProtocol.dataReceived(remaining)
        except InvalidProxyHeader:
            self.loseConnection()


    def getPeer(self):
        if self._proxyInfo and self._proxyInfo.source:
            return self._proxyInfo.source
        return self.transport.getPeer()


    def getHost(self):
        if self._proxyInfo and self._proxyInfo.destination:
            return self._proxyInfo.destination
        return self.transport.getHost()



class HAProxyWrappingFactory(policies.WrappingFactory):
    """
    A Factory wrapper that adds PROXY protocol support to connections.
    """
    protocol = HAProxyProtocolWrapper

    def logPrefix(self):
        """
        Annotate the wrapped factory's log prefix with some text indicating
        the PROXY protocol is in use.

        @rtype: C{str}
        """
        if interfaces.ILoggingContext.providedBy(self.wrappedFactory):
            logPrefix = self.wrappedFactory.logPrefix()
        else:
            logPrefix = self.wrappedFactory.__class__.__name__
        return "%s (PROXY)" % (logPrefix,)



def proxyEndpoint(wrappedEndpoint):
    """
    Wrap an endpoint with PROXY protocol support, so that the transport's
    C{getHost} and C{getPeer} methods reflect the attributes of the proxied
    connection rather than the underlying connection.

    @param wrappedEndpoint: The underlying listening endpoint.
    @type wrappedEndpoint: L{IStreamServerEndpoint}

    @return: a new listening endpoint that speaks the PROXY protocol.
    @rtype: L{IStreamServerEndpoint}
    """
    return _WrapperServerEndpoint(wrappedEndpoint, HAProxyWrappingFactory)
