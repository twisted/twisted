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
from twisted.protocols import policies
from twisted.internet import interfaces, protocol, main, defer
from twisted.python import failure, components

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
        self.deferred = defer.Deferred()
        self.protocol = protocol

    def buildProtocol(self, addr):
        return self.protocol

    def clientConnectionLost(self, connector, reason):
        self.disconnected = 1
        self.deferred.callback(None)


class _FireOnClose(policies.ProtocolWrapper):
    def __init__(self, protocol, factory):
        policies.ProtocolWrapper.__init__(self, protocol, factory)
        self.deferred = defer.Deferred()

    def connectionLost(self, reason):
        policies.ProtocolWrapper.connectionLost(self, reason)
        self.deferred.callback(None)


def loopbackTCP(server, client, port=0, noisy=True):
    """Run session between server and client protocol instances over TCP."""
    from twisted.internet import reactor
    f = policies.WrappingFactory(protocol.Factory())
    serverWrapper = _FireOnClose(f, server)
    f.noisy = noisy
    f.buildProtocol = lambda addr: serverWrapper
    serverPort = reactor.listenTCP(port, f, interface='127.0.0.1')
    clientF = LoopbackClientFactory(client)
    clientF.noisy = noisy
    reactor.connectTCP('127.0.0.1', serverPort.getHost().port, clientF)
    d = clientF.deferred
    d.addCallback(lambda x: serverWrapper.deferred)
    d.addCallback(lambda x: serverPort.stopListening())
    return d


def loopbackUNIX(server, client, noisy=True):
    """Run session between server and client protocol instances over UNIX socket."""
    path = tempfile.mktemp()
    from twisted.internet import reactor
    f = policies.WrappingFactory(protocol.Factory())
    serverWrapper = _FireOnClose(f, server)
    f.noisy = noisy
    f.buildProtocol = lambda addr: serverWrapper
    serverPort = reactor.listenUNIX(path, f)
    clientF = LoopbackClientFactory(client)
    clientF.noisy = noisy
    reactor.connectUNIX(path, clientF)
    d = clientF.deferred
    d.addCallback(lambda x: serverWrapper.deferred)
    d.addCallback(lambda x: serverPort.stopListening())
    return d
