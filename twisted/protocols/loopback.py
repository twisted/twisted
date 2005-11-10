# -*- test-case-name: twisted.test.test_loopback -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


# These class's names should have been based on Onanism, but were
# censored by the PSU

"""Testing support for protocols -- loopback between client and server."""

# system imports
import tempfile
from zope.interface import implements

# Twisted Imports
from twisted.internet import interfaces, protocol, main
from twisted.python import failure, components
from twisted.trial.util import spinUntil, spinWhile

class LoopbackRelay:

    implements(interfaces.ITransport, interfaces.IConsumer)

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
        if self.shouldLose == -1:
            return
        
        if self.producer:
            self.producer.resumeProducing()
        if self.buffer:
            if self.logFile:
                self.logFile.write("loopback receiving %s\n" % repr(self.buffer))
            buffer = self.buffer
            self.buffer = ''
            self.target.dataReceived(buffer)
        if self.shouldLose == 1:
            self.shouldLose = -1
            self.target.connectionLost(failure.Failure(main.CONNECTION_DONE))

    def loseConnection(self):
        if self.shouldLose != -1:
            self.shouldLose = 1

    def getHost(self):
        return 'loopback'

    def getPeer(self):
        return 'loopback'

    def registerProducer(self, producer, streaming):
        self.producer = producer

    def unregisterProducer(self):
        self.producer = None

    def logPrefix(self):
        return 'Loopback(%r)' % (self.target.__class__.__name__,)

components.backwardsCompatImplements(LoopbackRelay)

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


def loopbackTCP(server, client, port=0, noisy=True):
    """Run session between server and client protocol instances over TCP."""
    from twisted.internet import reactor
    f = protocol.Factory()
    f.noisy = noisy
    f.buildProtocol = lambda addr, p=server: p
    serverPort = reactor.listenTCP(port, f, interface='127.0.0.1')
    reactor.iterate()
    clientF = LoopbackClientFactory(client)
    clientF.noisy = noisy
    reactor.connectTCP('127.0.0.1', serverPort.getHost().port, clientF)

    # this needs to wait until:
    #  A: the client has disconnected
    #  B: the server has noticed, and its own socket has disconnected
    #  C: the listening socket has been shut down
    spinUntil(lambda :clientF.disconnected)        # A
    spinWhile(lambda :server.transport.connected)  # B
    serverPort.stopListening()
    spinWhile(lambda :serverPort.connected)        # C


def loopbackUNIX(server, client, noisy=True):
    """Run session between server and client protocol instances over UNIX socket."""
    path = tempfile.mktemp()
    from twisted.internet import reactor
    f = protocol.Factory()
    f.noisy = noisy
    f.buildProtocol = lambda addr, p=server: p
    serverPort = reactor.listenUNIX(path, f)
    reactor.iterate()
    clientF = LoopbackClientFactory(client)
    clientF.noisy = noisy
    reactor.connectUNIX(path, clientF)

    spinUntil(lambda :clientF.disconnected)        # A
    spinWhile(lambda :server.transport.connected)  # B
    serverPort.stopListening()
    spinWhile(lambda :serverPort.connected)        # C
