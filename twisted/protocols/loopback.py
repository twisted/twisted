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

# These class's names should have been based on Onanism, but were
# censored by the PSU

# Twisted Imports
from twisted.internet import interfaces, protocol, main
from twisted.python import hook, failure


class LoopbackRelay:

    __implements__ = interfaces.ITransport
    
    buffer = ''
    shouldLose = 0
    disconnecting = 0
    
    def __init__(self, target, logFile=None):
        self.target = target
        self.logFile = logFile

    def write(self, data):
        self.buffer = self.buffer + data
        if self.logFile:
            self.logFile.write("loopback writing %s\n" % repr(data))

    def writeSequence(self, iovec):
        self.write("".join(iovec))

    def clearBuffer(self):
        if self.logFile:
            self.logFile.write("loopback receiving %s\n" % repr(self.buffer))
        try:
            self.target.dataReceived(self.buffer)
        finally:
            self.buffer = ''
        if self.shouldLose:
            self.target.connectionLost(failure.Failure(main.CONNECTION_DONE))

    def loseConnection(self):
        self.shouldLose = 1

    def getHost(self):
        return 'loopback'

    def getPeer(self):
        return 'loopback'


def loopback(server, client, logFile=None):
    """Run session between server and client.
    """
    from twisted.internet import reactor
    serverToClient = LoopbackRelay(client, logFile)
    clientToServer = LoopbackRelay(server, logFile)
    server.makeConnection(serverToClient)
    client.makeConnection(clientToServer)
    while 1:
        reactor.iterate() # this is to clear any deferreds
        serverToClient.clearBuffer()
        clientToServer.clearBuffer()
        if serverToClient.shouldLose:
            serverToClient.clearBuffer()
            break
        elif clientToServer.shouldLose:
            break
    client.connectionLost(failure.Failure(main.CONNECTION_DONE))
    server.connectionLost(failure.Failure(main.CONNECTION_DONE))
    reactor.iterate() # last gasp before I go away


class LoopbackClientFactory(protocol.ClientFactory):

    def __init__(self, protocol):
        self.disconnected = 0
        self.protocol = protocol

    def buildProtocol(self, addr):
        return self.protocol

    def clientConnectionLost(self, connector, reason):
        self.disconnected = 1


def loopbackTCP(server, client, port=64124):
    """Run session between server and client protocol instances over TCP."""
    from twisted.internet import reactor
    f = protocol.Factory()
    f.buildProtocol = lambda addr, p=server: p
    serverPort = reactor.listenTCP(port, f, interface='127.0.0.1')
    reactor.iterate()
    clientF = LoopbackClientFactory(client)
    reactor.connectTCP('127.0.0.1', port, clientF)
    
    while not clientF.disconnected:
        reactor.iterate()

    serverPort.stopListening()
    reactor.iterate()
