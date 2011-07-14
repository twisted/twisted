# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Various helpers for tests for connection-oriented transports.
"""

from twisted.python.reflect import fullyQualifiedName
from twisted.python.log import msg, err
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
