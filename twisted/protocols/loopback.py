# -*- test-case-name: twisted.test.test_loopback -*-
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

"""Testing support for protocols -- loopback between client and server."""

# system imports
import tempfile

# Twisted Imports
from twisted.internet import interfaces, protocol, main
from twisted.python import hook, failure


class LoopbackRelay:

    __implements__ = interfaces.ITransport, interfaces.IConsumer
    
    buffer = ''
    shouldLose = 0
    disconnecting = 0
    producer = None

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
        if self.producer:
            self.producer.resumeProducing()
        if self.buffer:
            if self.logFile:
                self.logFile.write("loopback receiving %s\n" % repr(self.buffer))
            buffer = self.buffer
            self.buffer = ''
            self.target.dataReceived(buffer)
        if self.shouldLose:
            self.target.connectionLost(failure.Failure(main.CONNECTION_DONE))

    def loseConnection(self):
        self.shouldLose = 1

    def getHost(self):
        return 'loopback'

    def getPeer(self):
        return 'loopback'
    
    def registerProducer(self, producer, streaming):
        self.producer = producer
    
    def unregisterProducer(self):
        self.producer = None

def loopback(server, client, logFile=None):
    """Run session between server and client.
    """
    from twisted.internet import reactor
    serverToClient = LoopbackRelay(client, logFile)
    clientToServer = LoopbackRelay(server, logFile)
    server.makeConnection(serverToClient)
    client.makeConnection(clientToServer)
    while 1:
        reactor.iterate(0.01) # this is to clear any deferreds
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


def loopbackTCP(server, client, port=0):
    """Run session between server and client protocol instances over TCP."""
    from twisted.internet import reactor
    f = protocol.Factory()
    f.buildProtocol = lambda addr, p=server: p
    serverPort = reactor.listenTCP(port, f, interface='127.0.0.1')
    reactor.iterate()
    clientF = LoopbackClientFactory(client)
    reactor.connectTCP('127.0.0.1', serverPort.getHost()[2], clientF)
    
    while not clientF.disconnected:
        reactor.iterate(0.01)

    serverPort.stopListening()
    reactor.iterate()


def loopbackUNIX(server, client):
    """Run session between server and client protocol instances over UNIX socket."""
    path = tempfile.mktemp()
    from twisted.internet import reactor
    f = protocol.Factory()
    f.buildProtocol = lambda addr, p=server: p
    serverPort = reactor.listenUNIX(path, f)
    reactor.iterate()
    clientF = LoopbackClientFactory(client)
    reactor.connectUNIX(path, clientF)
    
    while not clientF.disconnected:
        reactor.iterate(0.01)

    serverPort.stopListening()
    reactor.iterate()
