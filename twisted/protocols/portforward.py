
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
A simple port forwarder.
"""

# Twisted imports
from twisted.internet import reactor, protocol


class Proxy(protocol.Protocol):

    peer = None
    buf = ''

    def setPeer(self, peer):
        self.peer = peer
        self.peer.transport.write(self.buf)
        self.buf = ''

    def connectionLost(self, reason):
        self.peer.transport.loseConnection()
        del self.peer

    def dataReceived(self, data):
        if self.peer:
            self.peer.transport.write(data)
        else:
            self.buf += data


class ProxyClient(Proxy):

    def connectionMade(self):
        self.peer.setPeer(self)


class ProxyClientFactory(protocol.ClientFactory):

    protocol = ProxyClient

    def setServer(self, server):
        self.server = server

    def buildProtocol(self, *args, **kw):
        prot = protocol.ClientFactory.buildProtocol(self, *args, **kw)
        prot.setPeer(self.server)
        return prot

    def clientConnectionFailed(self, connector, reason):
        self.server.transport.loseConnection()


class ProxyServer(Proxy):

    clientProtocolFactory = ProxyClientFactory

    def connectionMade(self):
        client = self.clientProtocolFactory()
        client.setServer(self)
        client = reactor.connectTCP(self.factory.host, self.factory.port,
                                    client)


class ProxyFactory(protocol.Factory):
    """Factory for port forwarder."""
    
    protocol = ProxyServer
    
    def __init__(self, host, port):
        self.host = host
        self.port = port
