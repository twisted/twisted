# -*- test-case-name: twisted.test.test_loopback -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Testing support for protocols -- loopback between client and server.
"""

# system imports
import tempfile
from zope.interface import implements

# Twisted Imports
from twisted.protocols import policies
from twisted.internet import interfaces, protocol, main, defer
from twisted.python import failure
from twisted.internet.interfaces import IAddress


class _LoopbackQueue(object):
    """
    Trivial wrapper around a list to give it an interface like a queue, which
    the addition of also sending notifications by way of a Deferred whenever
    the list has something added to it.
    """

    _notificationDeferred = None
    disconnect = False

    def __init__(self):
        self._queue = []


    def put(self, v):
        self._queue.append(v)
        if self._notificationDeferred is not None:
            d, self._notificationDeferred = self._notificationDeferred, None
            d.callback(None)


    def __nonzero__(self):
        return bool(self._queue)


    def get(self):
        return self._queue.pop(0)



class _LoopbackAddress(object):
    implements(IAddress)


class _LoopbackTransport(object):
    implements(interfaces.ITransport, interfaces.IConsumer)

    disconnecting = False
    producer = None

    # ITransport
    def __init__(self, q):
        self.q = q

    def write(self, bytes):
        self.q.put(bytes)

    def writeSequence(self, iovec):
        self.q.put(''.join(iovec))

    def loseConnection(self):
        self.q.disconnect = True
        self.q.put('')

    def getPeer(self):
        return _LoopbackAddress()

    def getHost(self):
        return _LoopbackAddress()

    # IConsumer
    def registerProducer(self, producer, streaming):
        assert self.producer is None
        self.producer = producer
        self.streamingProducer = streaming
        self._pollProducer()

    def unregisterProducer(self):
        assert self.producer is not None
        self.producer = None

    def _pollProducer(self):
        if self.producer is not None and not self.streamingProducer:
            self.producer.resumeProducing()



def loopbackAsync(server, client):
    """
    Establish a connection between C{server} and C{client} then transfer data
    between them until the connection is closed. This is often useful for
    testing a protocol.

    @param server: The protocol instance representing the server-side of this
    connection.
    
    @param client: The protocol instance representing the client-side of this
    connection.

    @return: A L{Deferred} which fires when the connection has been closed and
    both sides have received notification of this.
    """
    serverToClient = _LoopbackQueue()
    clientToServer = _LoopbackQueue()

    server.makeConnection(_LoopbackTransport(serverToClient))
    client.makeConnection(_LoopbackTransport(clientToServer))

    return _loopbackAsyncBody(server, serverToClient, client, clientToServer)



def _loopbackAsyncBody(server, serverToClient, client, clientToServer):
    """
    Transfer bytes from the output queue of each protocol to the input of the other.

    @param server: The protocol instance representing the server-side of this
    connection.

    @param serverToClient: The L{_LoopbackQueue} holding the server's output.

    @param client: The protocol instance representing the client-side of this
    connection.

    @param clientToServer: The L{_LoopbackQueue} holding the client's output.

    @return: A L{Deferred} which fires when the connection has been closed and
    both sides have received notification of this.
    """
    def pump(source, q, target):
        sent = False
        while q:
            sent = True
            bytes = q.get()
            if bytes:
                target.dataReceived(bytes)

        # A write buffer has now been emptied.  Give any producer on that side
        # an opportunity to produce more data.
        source.transport._pollProducer()

        return sent

    while 1:
        disconnect = clientSent = serverSent = False

        # Deliver the data which has been written.
        serverSent = pump(server, serverToClient, client)
        clientSent = pump(client, clientToServer, server)

        if not clientSent and not serverSent:
            # Neither side wrote any data.  Wait for some new data to be added
            # before trying to do anything further.
            d = clientToServer._notificationDeferred = serverToClient._notificationDeferred = defer.Deferred()
            d.addCallback(_loopbackAsyncContinue, server, serverToClient, client, clientToServer)
            return d
        if serverToClient.disconnect:
            # The server wants to drop the connection.  Flush any remaining
            # data it has.
            disconnect = True
            pump(server, serverToClient, client)
        elif clientToServer.disconnect:
            # The client wants to drop the connection.  Flush any remaining
            # data it has.
            disconnect = True
            pump(client, clientToServer, server)
        if disconnect:
            # Someone wanted to disconnect, so okay, the connection is gone.
            server.connectionLost(failure.Failure(main.CONNECTION_DONE))
            client.connectionLost(failure.Failure(main.CONNECTION_DONE))
            return defer.succeed(None)



def _loopbackAsyncContinue(ignored, server, serverToClient, client, clientToServer):
    # Clear the Deferred from each message queue, since it has already fired
    # and cannot be used again.
    clientToServer._notificationDeferred = serverToClient._notificationDeferred = None

    # Push some more bytes around.
    return _loopbackAsyncBody(server, serverToClient, client, clientToServer)



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
    DEPRECATED in Twisted 2.5. Use loopbackAsync instead.
    """
    import warnings
    warnings.warn('loopback() is deprecated (since Twisted 2.5). '
                  'Use loopbackAsync() instead.',
                  stacklevel=2, category=DeprecationWarning)
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
            server.connectionLost(failure.Failure(main.CONNECTION_DONE))
            break
        elif clientToServer.shouldLose:
            client.connectionLost(failure.Failure(main.CONNECTION_DONE))
            break
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
