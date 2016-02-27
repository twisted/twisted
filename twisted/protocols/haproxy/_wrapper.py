# -*- test-case-name: twisted.protocols.haproxy.test.test_wrapper -*-

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Protocol wrapper that provides HAProxy PROXY protocol support.
"""

from twisted.protocols import policies
from twisted.internet import interfaces

from . import _exc
from . import _v1parser
from . import _v2parser



class HAProxyProtocol(policies.ProtocolWrapper, object):
    """
    A Protocol wrapper that provides HAProxy support.
    """

    V1PARSER = _v1parser.V1Parser
    V1BYTES = V1PARSER.PROXYSTR
    V2PARSER = _v2parser.V2Parser
    V2BYTES = V2PARSER.PREFIX

    def __init__(self, factory, wrappedProtocol):
        policies.ProtocolWrapper.__init__(self, factory, wrappedProtocol)
        self.buffer = b''
        self.info = None
        self.parser = None


    def dataReceived(self, data):
        if self.info:
            return self.wrappedProtocol.dataReceived(data)

        if not self.parser:
            if (
                    len(data) >= 16 and
                    data[:12] == self.V2BYTES and
                    ord(data[12]) & 0b11110000 == 0x20
            ):
                self.parser = self.V2PARSER()
            elif len(data) >= 8 and data[:5] == self.V1BYTES:
                self.parser = self.V1PARSER()
            else:
                self.loseConnection()
                return None

        try:
            self.info, remaining = self.parser.feed(data)
            if remaining:
                self.wrappedProtocol.dataReceived(remaining)
        except _exc.InvalidProxyHeader:
            self.loseConnection()


    def getPeer(self):
        if self.info and self.info.source:
            return self.info.source
        return self.transport.getPeer()


    def getHost(self):
        if self.info and self.info.destination:
            return self.info.destination
        return self.transport.getHost()



class HAProxyFactory(policies.WrappingFactory):
    """
    A Factory wrapper that adds PROXY protocol support to connections.
    """
    protocol = HAProxyProtocol

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
