
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
from twisted.internet import reactor
from twisted.protocols import protocol


class Proxy(protocol.Protocol):

    def setPeer(self, peer):
        self.peer = peer

    def connectionLost(self):
        self.peer.loseConnection()
        del self.peer

    def dataReceived(self, data):
        self.peer.write(data)


class ProxyServer(Proxy):

    clientProtocol = Proxy

    def connectionMade(self):
        clientProtocol = self.clientProtocol()
        clientProtocol.setPeer(self.transport)
        client = reactor.clientTCP(self.factory.host, self.factory.port,
                                   clientProtocol)
        self.setPeer(client)


class ProxyFactory(protocol.Factory):
    """Factory for port forwarder."""
    
    protocol = ProxyServer
    
    def __init__(self, host, port):
        self.host = host
        self.port = port
