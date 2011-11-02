# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Various helpers for tests for connection-oriented transports.
"""

from gc import collect
from weakref import ref

from twisted.python import context, log
from twisted.python.reflect import fullyQualifiedName
from twisted.python.log import ILogContext, msg, err
from twisted.internet.defer import Deferred, gatherResults
from twisted.internet.protocol import ServerFactory, Protocol

def serverFactoryFor(protocol):
    """
    Helper function which returns a L{ServerFactory} which will build instances
    of C{protocol}.

    @param protocol: A callable which returns an L{IProtocol} provider to be
        used to handle connections to the port the returned factory listens on.
    """
    factory = ServerFactory()
    factory.protocol = protocol
    return factory

# ServerFactory is good enough for client endpoints, too.
factoryFor = serverFactoryFor

class _AcceptOneClient(ServerFactory):
    """
    This factory fires a L{Deferred} with a protocol instance shortly after it
    is constructed (hopefully long enough afterwards so that it has been
    connected to a transport).

    @ivar reactor: The reactor used to schedule the I{shortly}.
    @ivar result: A L{Deferred} which will be fired with the protocol instance.
    """
    def __init__(self, reactor, result):
        self.reactor = reactor
        self.result = result


    def buildProtocol(self, addr):
        protocol = ServerFactory.buildProtocol(self, addr)
        self.reactor.callLater(0, self.result.callback, protocol)
        return protocol



class ClosingLaterProtocol(Protocol):
    """
    ClosingLaterProtocol exchanges one byte with its peer and then disconnects
    itself.  This is mostly a work-around for the fact that connectionMade is
    called before the SSL handshake has completed.
    """
    def __init__(self, onConnectionLost):
        self.lostConnectionReason = None
        self.onConnectionLost = onConnectionLost


    def connectionMade(self):
        msg("ClosingLaterProtocol.connectionMade")


    def dataReceived(self, bytes):
        msg("ClosingLaterProtocol.dataReceived %r" % (bytes,))
        self.transport.loseConnection()


    def connectionLost(self, reason):
        msg("ClosingLaterProtocol.connectionLost")
        self.lostConnectionReason = reason
        self.onConnectionLost.callback(self)



class ConnectionTestsMixin(object):
    """
    This mixin defines test methods which should apply to most L{ITransport}
    implementations.
    """
    def serverEndpoint(self, reactor):
        """
        Return an object providing L{IStreamServerEndpoint} for use in creating
        a server to use to establish the connection type to be tested.
        """
        raise NotImplementedError("%s.serverEndpoint() not implemented" % (
                fullyQualifiedName(self.__class__),))


    def clientEndpoint(self, reactor, serverAddress):
        """
        Return an object providing L{IStreamClientEndpoint} for use in creating
        a client to use to establish the connection type to be tested.
        """
        raise NotImplementedError("%s.clientEndpoint() not implemented" % (
                fullyQualifiedName(self.__class__),))


    def loopback(self, reactor, clientProtocol, serverProtocol):
        """
        Create a loopback connection of the type to be tested, using
        C{clientProtocol} and C{serverProtocol} to handle each end of the
        connection.

        @return: A L{Deferred} which fires when the connection is established.
            The result is a two-tuple of the client protocol instance and
            server protocol instance.
        """
        accepted = Deferred()
        factory = _AcceptOneClient(reactor, accepted)
        factory.protocol = serverProtocol
        server = self.serverEndpoint(reactor)
        listening = server.listen(factory)
        def startedListening(port):
            address = port.getHost()
            client = self.clientEndpoint(reactor, address)
            return gatherResults([
                    client.connect(factoryFor(clientProtocol)), accepted])
        listening.addCallback(startedListening)
        return listening


    def test_logPrefix(self):
        """
        Client and server transports implement L{ILoggingContext.logPrefix} to
        return a message reflecting the protocol they are running.
        """
        class CustomLogPrefixProtocol(Protocol):
            def __init__(self, prefix):
                self._prefix = prefix
                self.system = Deferred()

            def logPrefix(self):
                return self._prefix

            def dataReceived(self, bytes):
                self.system.callback(context.get(ILogContext)["system"])

        reactor = self.buildReactor()
        d = self.loopback(
            reactor,
            lambda: CustomLogPrefixProtocol("Custom Client"),
            lambda: CustomLogPrefixProtocol("Custom Server"))
        def connected((client, server)):
            client.transport.write("foo")
            server.transport.write("bar")
            return gatherResults([client.system, server.system])
        d.addCallback(connected)

        def gotSystem((client, server)):
            self.assertIn("Custom Client", client)
            self.assertIn("Custom Server", server)
        d.addCallback(gotSystem)
        d.addErrback(err)
        d.addCallback(lambda ignored: reactor.stop())
        self.runReactor(reactor)


    def test_writeAfterDisconnect(self):
        """
        After a connection is disconnected, L{ITransport.write} and
        L{ITransport.writeSequence} are no-ops.
        """
        reactor = self.buildReactor()

        finished = []

        serverConnectionLostDeferred = Deferred()
        protocol = lambda: ClosingLaterProtocol(serverConnectionLostDeferred)
        portDeferred = self.serverEndpoint(reactor).listen(
            serverFactoryFor(protocol))
        def listening(port):
            msg("Listening on %r" % (port.getHost(),))
            endpoint = self.clientEndpoint(reactor, port.getHost())

            lostConnectionDeferred = Deferred()
            protocol = lambda: ClosingLaterProtocol(
                lostConnectionDeferred)
            client = endpoint.connect(factoryFor(protocol))
            def write(proto):
                msg("About to write to %r" % (proto,))
                proto.transport.write('x')
            client.addCallbacks(
                write, lostConnectionDeferred.errback)

            def disconnected(proto):
                msg("%r disconnected" % (proto,))
                proto.transport.write("some bytes to get lost")
                proto.transport.writeSequence(["some", "more"])
                finished.append(True)

            lostConnectionDeferred.addCallback(disconnected)
            serverConnectionLostDeferred.addCallback(disconnected)
            return gatherResults([
                    lostConnectionDeferred,
                    serverConnectionLostDeferred])

        portDeferred.addCallback(listening)
        portDeferred.addErrback(err)
        portDeferred.addCallback(lambda ignored: reactor.stop())

        self.runReactor(reactor)
        self.assertEqual(finished, [True, True])


    def test_protocolGarbageAfterLostConnection(self):
        """
        After the connection a protocol is being used for is closed, the reactor
        discards all of its references to the protocol.
        """
        lostConnectionDeferred = Deferred()
        clientProtocol = ClosingLaterProtocol(lostConnectionDeferred)
        clientRef = ref(clientProtocol)

        reactor = self.buildReactor()
        portDeferred = self.serverEndpoint(reactor).listen(
            serverFactoryFor(Protocol))
        def listening(port):
            msg("Listening on %r" % (port.getHost(),))
            endpoint = self.clientEndpoint(reactor, port.getHost())

            client = endpoint.connect(factoryFor(lambda: clientProtocol))
            def disconnect(proto):
                msg("About to disconnect %r" % (proto,))
                proto.transport.loseConnection()
            client.addCallback(disconnect)
            client.addErrback(lostConnectionDeferred.errback)
            return lostConnectionDeferred

        portDeferred.addCallback(listening)
        portDeferred.addErrback(err)
        portDeferred.addCallback(lambda ignored: reactor.stop())

        self.runReactor(reactor)

        # Drop the reference and get the garbage collector to tell us if there
        # are no references to the protocol instance left in the reactor.
        clientProtocol = None
        collect()
        self.assertIdentical(None, clientRef())



class LogObserverMixin(object):
    """
    Mixin for L{TestCase} subclasses which want to observe log events.
    """
    def observe(self):
        loggedMessages = []
        log.addObserver(loggedMessages.append)
        self.addCleanup(log.removeObserver, loggedMessages.append)
        return loggedMessages
