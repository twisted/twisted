
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
from twisted.internet import tcp
from twisted.protocols import protocol
from twisted.manhole import coil

# System imports
import types


class StupidProtocol(protocol.Protocol):

    def setPeer(self, peer):
        self.peer = peer

    def connectionLost(self):
        self.peer.loseConnection()
        del self.peer

    def dataReceived(self, data):
        print `data`
        self.peer.write(data)


class StupidProtocolServer(StupidProtocol):

    def connectionMade(self):
        clientProtocol = StupidProtocol()
        clientProtocol.setPeer(self.transport)
        client = tcp.Client(self.factory.host, self.factory.port,
                            clientProtocol)
        self.setPeer(client)


class StupidFactory(protocol.Factory, coil.Configurable):
    """Factory for port forwarder."""
    
    protocol = StupidProtocolServer
    
    def __init__(self, host="localhost", port=80):
        self.host = host
        self.port = port
    
    # configuration
    
    configName = 'TCP Port Forwarder'
    configTypes = {'host': types.StringType,
                   'port': types.IntType
                  }
    
    def config_host(self, host):
        self.host = host

    def config_port(self, port):
        if not (65536 > port > 0):
            raise ValueError, "not a valid IP port"
        self.port = port
    
    def getConfiguration(self):
        return {"host": self.host, "port": self.port}

coil.registerClass(StupidFactory)

# backwards compatible interface
makeStupidFactory = StupidFactory
