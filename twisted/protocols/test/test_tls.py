# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.protocols.tls}.
"""

try:
    from twisted.protocols.tls import TLSMemoryBIOProtocol, TLSMemoryBIOFactory
except ImportError:
    # Skip the whole test module if it can't be imported.
    skip = "pyOpenSSL 0.10 or newer required for twisted.protocol.tls"
else:
    # Otherwise, the pyOpenSSL dependency must be satisfied, so all these
    # imports will work.
    from OpenSSL.crypto import X509Type
    from OpenSSL.SSL import TLSv1_METHOD, Error, Context, ConnectionType
    from twisted.internet.ssl import ClientContextFactory, PrivateCertificate
    from twisted.internet.ssl import DefaultOpenSSLContextFactory

from twisted.python.filepath import FilePath
from twisted.internet.interfaces import ISystemHandle, ISSLTransport
from twisted.internet.error import ConnectionDone
from twisted.internet.defer import Deferred, gatherResults
from twisted.internet.protocol import Protocol, ClientFactory, ServerFactory
from twisted.protocols.loopback import loopbackAsync, collapsingPumpPolicy
from twisted.trial.unittest import TestCase
from twisted.test.test_tcp import ConnectionLostNotifyingProtocol
from twisted.test.test_ssl import certPath
from twisted.test.proto_helpers import StringTransport


class HandshakeCallbackContextFactory:
    """
    L{HandshakeCallbackContextFactory} is a factory for SSL contexts which
    allows applications to get notification when the SSL handshake completes.

    @ivar _finished: A L{Deferred} which will be called back when the handshake
        is done.
    """
    # pyOpenSSL needs to expose this.
    # https://bugs.launchpad.net/pyopenssl/+bug/372832
    SSL_CB_HANDSHAKE_DONE = 0x20

    def __init__(self):
        self._finished = Deferred()


    def factoryAndDeferred(cls):
        """
        Create a new L{HandshakeCallbackContextFactory} and return a two-tuple
        of it and a L{Deferred} which will fire when a connection created with
        it completes a TLS handshake.
        """
        contextFactory = cls()
        return contextFactory, contextFactory._finished
    factoryAndDeferred = classmethod(factoryAndDeferred)


    def _info(self, connection, where, ret):
        """
        This is the "info callback" on the context.  It will be called
        periodically by pyOpenSSL with information about the state of a
        connection.  When it indicates the handshake is complete, it will fire
        C{self._finished}.
        """
        if where & self.SSL_CB_HANDSHAKE_DONE:
            self._finished.callback(None)


    def getContext(self):
        """
        Create and return an SSL context configured to use L{self._info} as the
        info callback.
        """
        context = Context(TLSv1_METHOD)
        context.set_info_callback(self._info)
        return context



class AccumulatingProtocol(Protocol):
    """
    A protocol which collects the bytes it receives and closes its connection
    after receiving a certain minimum of data.

    @ivar howMany: The number of bytes of data to wait for before closing the connection.
    @ivar receiving: A C{list} of C{str} of the bytes received so far.
    """
    def __init__(self, howMany):
        self.howMany = howMany


    def connectionMade(self):
        self.received = []


    def dataReceived(self, bytes):
        self.received.append(bytes)
        if sum(map(len, self.received)) >= self.howMany:
            self.transport.loseConnection()



class TLSMemoryBIOTests(TestCase):
    """
    Tests for the implementation of L{ISSLTransport} which runs over another
    L{ITransport}.
    """
    def test_interfaces(self):
        """
        L{TLSMemoryBIOProtocol} instances provide L{ISSLTransport} and
        L{ISystemHandle}.
        """
        proto = TLSMemoryBIOProtocol(None, None)
        self.assertTrue(ISSLTransport.providedBy(proto))
        self.assertTrue(ISystemHandle.providedBy(proto))


    def test_getHandle(self):
        """
        L{TLSMemoryBIOProtocol.getHandle} returns the L{OpenSSL.SSL.Connection}
        instance it uses to actually implement TLS.

        This may seem odd.  In fact, it is.  The L{OpenSSL.SSL.Connection} is
        not actually the "system handle" here, nor even an object the reactor
        knows about directly.  However, L{twisted.internet.ssl.Certificate}'s
        C{peerFromTransport} and C{hostFromTransport} methods depend on being
        able to get an L{OpenSSL.SSL.Connection} object in order to work
        properly.  Implementing L{ISystemHandle.getHandle} like this is the
        easiest way for those APIs to be made to work.  If they are changed,
        then it may make sense to get rid of this implementation of
        L{ISystemHandle} and return the underlying socket instead.
        """
        factory = ClientFactory()
        contextFactory = ClientContextFactory()
        wrapperFactory = TLSMemoryBIOFactory(contextFactory, True, factory)
        proto = TLSMemoryBIOProtocol(wrapperFactory, Protocol())
        transport = StringTransport()
        proto.makeConnection(transport)
        self.assertIsInstance(proto.getHandle(), ConnectionType)


    def test_makeConnection(self):
        """
        When L{TLSMemoryBIOProtocol} is connected to a transport, it connects
        the protocol it wraps to a transport.
        """
        clientProtocol = Protocol()
        clientFactory = ClientFactory()
        clientFactory.protocol = lambda: clientProtocol

        contextFactory = ClientContextFactory()
        wrapperFactory = TLSMemoryBIOFactory(
            contextFactory, True, clientFactory)
        sslProtocol = wrapperFactory.buildProtocol(None)

        transport = StringTransport()
        sslProtocol.makeConnection(transport)

        self.assertNotIdentical(clientProtocol.transport, None)
        self.assertNotIdentical(clientProtocol.transport, transport)


    def test_handshake(self):
        """
        The TLS handshake is performed when L{TLSMemoryBIOProtocol} is
        connected to a transport.
        """
        clientFactory = ClientFactory()
        clientFactory.protocol = Protocol

        clientContextFactory, handshakeDeferred = (
            HandshakeCallbackContextFactory.factoryAndDeferred())
        wrapperFactory = TLSMemoryBIOFactory(
            clientContextFactory, True, clientFactory)
        sslClientProtocol = wrapperFactory.buildProtocol(None)

        serverFactory = ServerFactory()
        serverFactory.protocol = Protocol

        serverContextFactory = DefaultOpenSSLContextFactory(certPath, certPath)
        wrapperFactory = TLSMemoryBIOFactory(
            serverContextFactory, False, serverFactory)
        sslServerProtocol = wrapperFactory.buildProtocol(None)

        connectionDeferred = loopbackAsync(sslServerProtocol, sslClientProtocol)

        # Only wait for the handshake to complete.  Anything after that isn't
        # important here.
        return handshakeDeferred


    def test_handshakeFailure(self):
        """
        L{TLSMemoryBIOProtocol} reports errors in the handshake process to the
        application-level protocol object using its C{connectionLost} method
        and disconnects the underlying transport.
        """
        clientConnectionLost = Deferred()
        clientFactory = ClientFactory()
        clientFactory.protocol = (
            lambda: ConnectionLostNotifyingProtocol(
                clientConnectionLost))

        clientContextFactory = HandshakeCallbackContextFactory()
        wrapperFactory = TLSMemoryBIOFactory(
            clientContextFactory, True, clientFactory)
        sslClientProtocol = wrapperFactory.buildProtocol(None)

        serverConnectionLost = Deferred()
        serverFactory = ServerFactory()
        serverFactory.protocol = (
            lambda: ConnectionLostNotifyingProtocol(
                serverConnectionLost))

        # This context factory rejects any clients which do not present a
        # certificate.
        certificateData = FilePath(certPath).getContent()
        certificate = PrivateCertificate.loadPEM(certificateData)
        serverContextFactory = certificate.options(certificate)
        wrapperFactory = TLSMemoryBIOFactory(
            serverContextFactory, False, serverFactory)
        sslServerProtocol = wrapperFactory.buildProtocol(None)

        connectionDeferred = loopbackAsync(sslServerProtocol, sslClientProtocol)

        def cbConnectionLost(protocol):
            # The connection should close on its own in response to the error
            # induced by the client not supplying the required certificate.
            # After that, check to make sure the protocol's connectionLost was
            # called with the right thing.
            protocol.lostConnectionReason.trap(Error)
        clientConnectionLost.addCallback(cbConnectionLost)
        serverConnectionLost.addCallback(cbConnectionLost)

        # Additionally, the underlying transport should have been told to
        # go away.
        return gatherResults([
                clientConnectionLost, serverConnectionLost,
                connectionDeferred])


    def test_getPeerCertificate(self):
        """
        L{TLSMemoryBIOFactory.getPeerCertificate} returns the
        L{OpenSSL.crypto.X509Type} instance representing the peer's
        certificate.
        """
        # Set up a client and server so there's a certificate to grab.
        clientFactory = ClientFactory()
        clientFactory.protocol = Protocol

        clientContextFactory, handshakeDeferred = (
            HandshakeCallbackContextFactory.factoryAndDeferred())
        wrapperFactory = TLSMemoryBIOFactory(
            clientContextFactory, True, clientFactory)
        sslClientProtocol = wrapperFactory.buildProtocol(None)

        serverFactory = ServerFactory()
        serverFactory.protocol = Protocol

        serverContextFactory = DefaultOpenSSLContextFactory(certPath, certPath)
        wrapperFactory = TLSMemoryBIOFactory(
            serverContextFactory, False, serverFactory)
        sslServerProtocol = wrapperFactory.buildProtocol(None)

        connectionDeferred = loopbackAsync(
            sslServerProtocol, sslClientProtocol)

        # Wait for the handshake
        def cbHandshook(ignored):
            # Grab the server's certificate and check it out
            cert = sslClientProtocol.getPeerCertificate()
            self.assertIsInstance(cert, X509Type)
            self.assertEquals(
                cert.digest('md5'),
                '9B:A4:AB:43:10:BE:82:AE:94:3E:6B:91:F2:F3:40:E8')
        handshakeDeferred.addCallback(cbHandshook)
        return handshakeDeferred


    def test_writeAfterHandshake(self):
        """
        Bytes written to L{TLSMemoryBIOProtocol} before the handshake is
        complete are received by the protocol on the other side of the
        connection once the handshake succeeds.
        """
        bytes = "some bytes"

        clientProtocol = Protocol()
        clientFactory = ClientFactory()
        clientFactory.protocol = lambda: clientProtocol

        clientContextFactory, handshakeDeferred = (
            HandshakeCallbackContextFactory.factoryAndDeferred())
        wrapperFactory = TLSMemoryBIOFactory(
            clientContextFactory, True, clientFactory)
        sslClientProtocol = wrapperFactory.buildProtocol(None)

        serverProtocol = AccumulatingProtocol(len(bytes))
        serverFactory = ServerFactory()
        serverFactory.protocol = lambda: serverProtocol

        serverContextFactory = DefaultOpenSSLContextFactory(certPath, certPath)
        wrapperFactory = TLSMemoryBIOFactory(
            serverContextFactory, False, serverFactory)
        sslServerProtocol = wrapperFactory.buildProtocol(None)

        connectionDeferred = loopbackAsync(sslServerProtocol, sslClientProtocol)

        # Wait for the handshake to finish before writing anything.
        def cbHandshook(ignored):
            clientProtocol.transport.write(bytes)

            # The server will drop the connection once it gets the bytes.
            return connectionDeferred
        handshakeDeferred.addCallback(cbHandshook)

        # Once the connection is lost, make sure the server received the
        # expected bytes.
        def cbDisconnected(ignored):
            self.assertEquals("".join(serverProtocol.received), bytes)
        handshakeDeferred.addCallback(cbDisconnected)

        return handshakeDeferred


    def test_writeBeforeHandshake(self):
        """
        Bytes written to L{TLSMemoryBIOProtocol} before the handshake is
        complete are received by the protocol on the other side of the
        connection once the handshake succeeds.
        """
        bytes = "some bytes"

        class SimpleSendingProtocol(Protocol):
            def connectionMade(self):
                self.transport.write(bytes)

        clientFactory = ClientFactory()
        clientFactory.protocol = SimpleSendingProtocol

        clientContextFactory, handshakeDeferred = (
            HandshakeCallbackContextFactory.factoryAndDeferred())
        wrapperFactory = TLSMemoryBIOFactory(
            clientContextFactory, True, clientFactory)
        sslClientProtocol = wrapperFactory.buildProtocol(None)

        serverProtocol = AccumulatingProtocol(len(bytes))
        serverFactory = ServerFactory()
        serverFactory.protocol = lambda: serverProtocol

        serverContextFactory = DefaultOpenSSLContextFactory(certPath, certPath)
        wrapperFactory = TLSMemoryBIOFactory(
            serverContextFactory, False, serverFactory)
        sslServerProtocol = wrapperFactory.buildProtocol(None)

        connectionDeferred = loopbackAsync(sslServerProtocol, sslClientProtocol)

        # Wait for the connection to end, then make sure the server received
        # the bytes sent by the client.
        def cbConnectionDone(ignored):
            self.assertEquals("".join(serverProtocol.received), bytes)
        connectionDeferred.addCallback(cbConnectionDone)
        return connectionDeferred


    def test_writeSequence(self):
        """
        Bytes written to L{TLSMemoryBIOProtocol} with C{writeSequence} are
        received by the protocol on the other side of the connection.
        """
        bytes = "some bytes"
        class SimpleSendingProtocol(Protocol):
            def connectionMade(self):
                self.transport.writeSequence(list(bytes))

        clientFactory = ClientFactory()
        clientFactory.protocol = SimpleSendingProtocol

        clientContextFactory = HandshakeCallbackContextFactory()
        wrapperFactory = TLSMemoryBIOFactory(
            clientContextFactory, True, clientFactory)
        sslClientProtocol = wrapperFactory.buildProtocol(None)

        serverProtocol = AccumulatingProtocol(len(bytes))
        serverFactory = ServerFactory()
        serverFactory.protocol = lambda: serverProtocol

        serverContextFactory = DefaultOpenSSLContextFactory(certPath, certPath)
        wrapperFactory = TLSMemoryBIOFactory(
            serverContextFactory, False, serverFactory)
        sslServerProtocol = wrapperFactory.buildProtocol(None)

        connectionDeferred = loopbackAsync(sslServerProtocol, sslClientProtocol)

        # Wait for the connection to end, then make sure the server received
        # the bytes sent by the client.
        def cbConnectionDone(ignored):
            self.assertEquals("".join(serverProtocol.received), bytes)
        connectionDeferred.addCallback(cbConnectionDone)
        return connectionDeferred


    def test_multipleWrites(self):
        """
        If multiple separate TLS messages are received in a single chunk from
        the underlying transport, all of the application bytes from each
        message are delivered to the application-level protocol.
        """
        bytes = [str(i) for i in range(10)]
        class SimpleSendingProtocol(Protocol):
            def connectionMade(self):
                for b in bytes:
                    self.transport.write(b)

        clientFactory = ClientFactory()
        clientFactory.protocol = SimpleSendingProtocol

        clientContextFactory = HandshakeCallbackContextFactory()
        wrapperFactory = TLSMemoryBIOFactory(
            clientContextFactory, True, clientFactory)
        sslClientProtocol = wrapperFactory.buildProtocol(None)

        serverProtocol = AccumulatingProtocol(sum(map(len, bytes)))
        serverFactory = ServerFactory()
        serverFactory.protocol = lambda: serverProtocol

        serverContextFactory = DefaultOpenSSLContextFactory(certPath, certPath)
        wrapperFactory = TLSMemoryBIOFactory(
            serverContextFactory, False, serverFactory)
        sslServerProtocol = wrapperFactory.buildProtocol(None)

        connectionDeferred = loopbackAsync(sslServerProtocol, sslClientProtocol, collapsingPumpPolicy)

        # Wait for the connection to end, then make sure the server received
        # the bytes sent by the client.
        def cbConnectionDone(ignored):
            self.assertEquals("".join(serverProtocol.received), ''.join(bytes))
        connectionDeferred.addCallback(cbConnectionDone)
        return connectionDeferred


    def test_hugeWrite(self):
        """
        If a very long string is passed to L{TLSMemoryBIOProtocol.write}, any
        trailing part of it which cannot be send immediately is buffered and
        sent later.
        """
        bytes = "some bytes"
        factor = 8192
        class SimpleSendingProtocol(Protocol):
            def connectionMade(self):
                self.transport.write(bytes * factor)

        clientFactory = ClientFactory()
        clientFactory.protocol = SimpleSendingProtocol

        clientContextFactory = HandshakeCallbackContextFactory()
        wrapperFactory = TLSMemoryBIOFactory(
            clientContextFactory, True, clientFactory)
        sslClientProtocol = wrapperFactory.buildProtocol(None)

        serverProtocol = AccumulatingProtocol(len(bytes) * factor)
        serverFactory = ServerFactory()
        serverFactory.protocol = lambda: serverProtocol

        serverContextFactory = DefaultOpenSSLContextFactory(certPath, certPath)
        wrapperFactory = TLSMemoryBIOFactory(
            serverContextFactory, False, serverFactory)
        sslServerProtocol = wrapperFactory.buildProtocol(None)

        connectionDeferred = loopbackAsync(sslServerProtocol, sslClientProtocol)

        # Wait for the connection to end, then make sure the server received
        # the bytes sent by the client.
        def cbConnectionDone(ignored):
            self.assertEquals("".join(serverProtocol.received), bytes * factor)
        connectionDeferred.addCallback(cbConnectionDone)
        return connectionDeferred


    def test_disorderlyShutdown(self):
        """
        If a L{TLSMemoryBIOProtocol} loses its connection unexpectedly, this is
        reported to the application.
        """
        clientConnectionLost = Deferred()
        clientFactory = ClientFactory()
        clientFactory.protocol = (
            lambda: ConnectionLostNotifyingProtocol(
                clientConnectionLost))

        clientContextFactory = HandshakeCallbackContextFactory()
        wrapperFactory = TLSMemoryBIOFactory(
            clientContextFactory, True, clientFactory)
        sslClientProtocol = wrapperFactory.buildProtocol(None)

        # Client speaks first, so the server can be dumb.
        serverProtocol = Protocol()

        connectionDeferred = loopbackAsync(serverProtocol, sslClientProtocol)

        # Now destroy the connection.
        serverProtocol.transport.loseConnection()

        # And when the connection completely dies, check the reason.
        def cbDisconnected(clientProtocol):
            clientProtocol.lostConnectionReason.trap(Error)
        clientConnectionLost.addCallback(cbDisconnected)
        return clientConnectionLost


    def test_loseConnectionAfterHandshake(self):
        """
        L{TLSMemoryBIOProtocol.loseConnection} sends a TLS close alert and
        shuts down the underlying connection.
        """
        clientConnectionLost = Deferred()
        clientFactory = ClientFactory()
        clientFactory.protocol = (
            lambda: ConnectionLostNotifyingProtocol(
                clientConnectionLost))

        clientContextFactory, handshakeDeferred = (
            HandshakeCallbackContextFactory.factoryAndDeferred())
        wrapperFactory = TLSMemoryBIOFactory(
            clientContextFactory, True, clientFactory)
        sslClientProtocol = wrapperFactory.buildProtocol(None)

        serverProtocol = Protocol()
        serverFactory = ServerFactory()
        serverFactory.protocol = lambda: serverProtocol

        serverContextFactory = DefaultOpenSSLContextFactory(certPath, certPath)
        wrapperFactory = TLSMemoryBIOFactory(
            serverContextFactory, False, serverFactory)
        sslServerProtocol = wrapperFactory.buildProtocol(None)

        connectionDeferred = loopbackAsync(sslServerProtocol, sslClientProtocol)

        # Wait for the handshake before dropping the connection.
        def cbHandshake(ignored):
            serverProtocol.transport.loseConnection()

            # Now wait for the client to notice.
            return clientConnectionLost
        handshakeDeferred.addCallback(cbHandshake)

        # Wait for the connection to end, then make sure the client was
        # notified of a handshake failure.
        def cbConnectionDone(clientProtocol):
            clientProtocol.lostConnectionReason.trap(ConnectionDone)

            # The server should have closed its underlying transport, in
            # addition to whatever it did to shut down the TLS layer.
            self.assertTrue(serverProtocol.transport.q.disconnect)

            # The client should also have closed its underlying transport once
            # it saw the server shut down the TLS layer, so as to avoid relying
            # on the server to close the underlying connection.
            self.assertTrue(clientProtocol.transport.q.disconnect)
        handshakeDeferred.addCallback(cbConnectionDone)
        return handshakeDeferred

