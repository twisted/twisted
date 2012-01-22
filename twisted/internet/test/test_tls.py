# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{ITLSTransport}.
"""

__metaclass__ = type

from zope.interface import implements

from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.internet.protocol import ServerFactory, ClientFactory, Protocol
from twisted.internet.interfaces import (
    IReactorSSL, ITLSTransport, IStreamClientEndpoint)
from twisted.internet.defer import Deferred, DeferredList
from twisted.internet.endpoints import (
    SSL4ServerEndpoint, SSL4ClientEndpoint, TCP4ClientEndpoint)
from twisted.internet.error import ConnectionClosed
from twisted.internet.task import Cooperator
from twisted.trial.unittest import SkipTest
from twisted.python.runtime import platform

from twisted.internet.test.test_core import ObjectModelIntegrationMixin
from twisted.internet.test.test_tcp import StreamTransportTestsMixin
from twisted.internet.test.connectionmixins import ConnectionTestsMixin
from twisted.internet.test.test_tcp import (
    BrokenContextFactory, AbortConnectionMixin)

try:
    from OpenSSL.crypto import FILETYPE_PEM
except ImportError:
    FILETYPE_PEM = None
else:
    from twisted.internet.ssl import PrivateCertificate, KeyPair
    from twisted.internet.ssl import ClientContextFactory


class TLSMixin:
    requiredInterfaces = [IReactorSSL]

    if platform.isWindows():
        msg = (
            "For some reason, these reactors don't deal with SSL "
            "disconnection correctly on Windows.  See #3371.")
        skippedReactors = {
            "twisted.internet.glib2reactor.Glib2Reactor": msg,
            "twisted.internet.gtk2reactor.Gtk2Reactor": msg}


class ContextGeneratingMixin(object):
    _certificateText = (
        "-----BEGIN CERTIFICATE-----\n"
        "MIIDBjCCAm+gAwIBAgIBATANBgkqhkiG9w0BAQQFADB7MQswCQYDVQQGEwJTRzER\n"
        "MA8GA1UEChMITTJDcnlwdG8xFDASBgNVBAsTC00yQ3J5cHRvIENBMSQwIgYDVQQD\n"
        "ExtNMkNyeXB0byBDZXJ0aWZpY2F0ZSBNYXN0ZXIxHTAbBgkqhkiG9w0BCQEWDm5n\n"
        "cHNAcG9zdDEuY29tMB4XDTAwMDkxMDA5NTEzMFoXDTAyMDkxMDA5NTEzMFowUzEL\n"
        "MAkGA1UEBhMCU0cxETAPBgNVBAoTCE0yQ3J5cHRvMRIwEAYDVQQDEwlsb2NhbGhv\n"
        "c3QxHTAbBgkqhkiG9w0BCQEWDm5ncHNAcG9zdDEuY29tMFwwDQYJKoZIhvcNAQEB\n"
        "BQADSwAwSAJBAKy+e3dulvXzV7zoTZWc5TzgApr8DmeQHTYC8ydfzH7EECe4R1Xh\n"
        "5kwIzOuuFfn178FBiS84gngaNcrFi0Z5fAkCAwEAAaOCAQQwggEAMAkGA1UdEwQC\n"
        "MAAwLAYJYIZIAYb4QgENBB8WHU9wZW5TU0wgR2VuZXJhdGVkIENlcnRpZmljYXRl\n"
        "MB0GA1UdDgQWBBTPhIKSvnsmYsBVNWjj0m3M2z0qVTCBpQYDVR0jBIGdMIGagBT7\n"
        "hyNp65w6kxXlxb8pUU/+7Sg4AaF/pH0wezELMAkGA1UEBhMCU0cxETAPBgNVBAoT\n"
        "CE0yQ3J5cHRvMRQwEgYDVQQLEwtNMkNyeXB0byBDQTEkMCIGA1UEAxMbTTJDcnlw\n"
        "dG8gQ2VydGlmaWNhdGUgTWFzdGVyMR0wGwYJKoZIhvcNAQkBFg5uZ3BzQHBvc3Qx\n"
        "LmNvbYIBADANBgkqhkiG9w0BAQQFAAOBgQA7/CqT6PoHycTdhEStWNZde7M/2Yc6\n"
        "BoJuVwnW8YxGO8Sn6UJ4FeffZNcYZddSDKosw8LtPOeWoK3JINjAk5jiPQ2cww++\n"
        "7QGG/g5NDjxFZNDJP1dGiLAxPW6JXwov4v0FmdzfLOZ01jDcgQQZqEpYlgpuI5JE\n"
        "WUQ9Ho4EzbYCOQ==\n"
        "-----END CERTIFICATE-----\n")

    _privateKeyText = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIBPAIBAAJBAKy+e3dulvXzV7zoTZWc5TzgApr8DmeQHTYC8ydfzH7EECe4R1Xh\n"
        "5kwIzOuuFfn178FBiS84gngaNcrFi0Z5fAkCAwEAAQJBAIqm/bz4NA1H++Vx5Ewx\n"
        "OcKp3w19QSaZAwlGRtsUxrP7436QjnREM3Bm8ygU11BjkPVmtrKm6AayQfCHqJoT\n"
        "ZIECIQDW0BoMoL0HOYM/mrTLhaykYAVqgIeJsPjvkEhTFXWBuQIhAM3deFAvWNu4\n"
        "nklUQ37XsCT2c9tmNt1LAT+slG2JOTTRAiAuXDtC/m3NYVwyHfFm+zKHRzHkClk2\n"
        "HjubeEgjpj32AQIhAJqMGTaZVOwevTXvvHwNEH+vRWsAYU/gbx+OQB+7VOcBAiEA\n"
        "oolb6NMg/R3enNPvS1O4UU1H8wpaF77L4yiSWlE0p4w=\n"
        "-----END RSA PRIVATE KEY-----\n")


    def getServerContext(self):
        """
        Return a new SSL context suitable for use in a test server.
        """
        cert = PrivateCertificate.load(
            self._certificateText,
            KeyPair.load(self._privateKeyText, FILETYPE_PEM),
            FILETYPE_PEM)
        return cert.options()


    def getClientContext(self):
        return ClientContextFactory()



class StartTLSClientEndpoint(object):
    """
    An endpoint which wraps another one and adds a TLS layer immediately when
    connections are set up.

    @ivar wrapped: A L{IStreamClientEndpoint} provider which will be used to
        really set up connections.

    @ivar contextFactory: A L{ContextFactory} to use to do TLS.
    """
    implements(IStreamClientEndpoint)

    def __init__(self, wrapped, contextFactory):
        self.wrapped = wrapped
        self.contextFactory = contextFactory


    def connect(self, factory):
        """
        Establish a connection using a protocol build by C{factory} and
        immediately start TLS on it.  Return a L{Deferred} which fires with the
        protocol instance.
        """
        d = self.wrapped.connect(factory)
        def connected(protocol):
            protocol.transport.startTLS(self.contextFactory)
            return protocol
        d.addCallback(connected)
        return d



class StartTLSClientTestsMixin(TLSMixin, ReactorBuilder, ConnectionTestsMixin,
                               ContextGeneratingMixin):
    """
    Tests for TLS connections established using L{ITLSTransport.startTLS} (as
    opposed to L{IReactorSSL.connectSSL} or L{IReactorSSL.listenSSL}).
    """
    def serverEndpoint(self, reactor):
        """
        Construct an SSL server endpoint.  This should be be constructing a TCP
        server endpoint which immediately calls C{startTLS} instead, but that
        is hard.
        """
        return SSL4ServerEndpoint(reactor, 0, self.getServerContext())


    def clientEndpoint(self, reactor, serverAddress):
        """
        Construct a TCP client endpoint wrapped to immediately start TLS.
        """
        return StartTLSClientEndpoint(
            TCP4ClientEndpoint(
                reactor, '127.0.0.1', serverAddress.port),
            ClientContextFactory())



class BadContextTestsMixin(object):
    """
    Mixin for L{ReactorBuilder} subclasses which defines a helper for testing
    the handling of broken context factories.
    """
    def _testBadContext(self, useIt):
        """
        Assert that the exception raised by a broken context factory's
        C{getContext} method is raised by some reactor method.  If it is not, an
        exception will be raised to fail the test.

        @param useIt: A two-argument callable which will be called with a
            reactor and a broken context factory and which is expected to raise
            the same exception as the broken context factory's C{getContext}
            method.
        """
        reactor = self.buildReactor()
        exc = self.assertRaises(
            ValueError, useIt, reactor, BrokenContextFactory())
        self.assertEqual(BrokenContextFactory.message, str(exc))



class SSLClientTestsMixin(TLSMixin, ReactorBuilder, ContextGeneratingMixin,
                          ConnectionTestsMixin, BadContextTestsMixin):
    """
    Mixin defining tests relating to L{ITLSTransport}.
    """

    def serverEndpoint(self, reactor):
        """
        Create an SSL server endpoint on a TCP/IP-stack allocated port.
        """
        return SSL4ServerEndpoint(reactor, 0, self.getServerContext())


    def clientEndpoint(self, reactor, serverAddress):
        """
        Create an SSL client endpoint which will connect localhost on
        the port given by C{serverAddress}.

        @type serverAddress: L{IPv4Address}
        """
        return SSL4ClientEndpoint(
            reactor, '127.0.0.1', serverAddress.port,
            ClientContextFactory())


    def test_badContext(self):
        """
        If the context factory passed to L{IReactorSSL.connectSSL} raises an
        exception from its C{getContext} method, that exception is raised by
        L{IReactorSSL.connectSSL}.
        """
        def useIt(reactor, contextFactory):
            return reactor.connectSSL(
                "127.0.0.1", 1234, ClientFactory(), contextFactory)
        self._testBadContext(useIt)


    def test_disconnectAfterWriteAfterStartTLS(self):
        """
        L{ITCPTransport.loseConnection} ends a connection which was set up with
        L{ITLSTransport.startTLS} and which has recently been written to.  This
        is intended to verify that a socket send error masked by the TLS
        implementation doesn't prevent the connection from being reported as
        closed.
        """
        class ShortProtocol(Protocol):
            def connectionMade(self):
                if not ITLSTransport.providedBy(self.transport):
                    # Functionality isn't available to be tested.
                    finished = self.factory.finished
                    self.factory.finished = None
                    finished.errback(SkipTest("No ITLSTransport support"))
                    return

                # Switch the transport to TLS.
                self.transport.startTLS(self.factory.context)
                # Force TLS to really get negotiated.  If nobody talks, nothing
                # will happen.
                self.transport.write("x")

            def dataReceived(self, data):
                # Stuff some bytes into the socket.  This mostly has the effect
                # of causing the next write to fail with ENOTCONN or EPIPE.
                # With the pyOpenSSL implementation of ITLSTransport, the error
                # is swallowed outside of the control of Twisted.
                self.transport.write("y")
                # Now close the connection, which requires a TLS close alert to
                # be sent.
                self.transport.loseConnection()

            def connectionLost(self, reason):
                # This is the success case.  The client and the server want to
                # get here.
                finished = self.factory.finished
                if finished is not None:
                    self.factory.finished = None
                    finished.callback(reason)

        reactor = self.buildReactor()

        serverFactory = ServerFactory()
        serverFactory.finished = Deferred()
        serverFactory.protocol = ShortProtocol
        serverFactory.context = self.getServerContext()

        clientFactory = ClientFactory()
        clientFactory.finished = Deferred()
        clientFactory.protocol = ShortProtocol
        clientFactory.context = self.getClientContext()
        clientFactory.context.method = serverFactory.context.method

        lostConnectionResults = []
        finished = DeferredList(
            [serverFactory.finished, clientFactory.finished],
            consumeErrors=True)
        def cbFinished(results):
            lostConnectionResults.extend([results[0][1], results[1][1]])
        finished.addCallback(cbFinished)

        port = reactor.listenTCP(0, serverFactory, interface='127.0.0.1')
        self.addCleanup(port.stopListening)

        connector = reactor.connectTCP(
            port.getHost().host, port.getHost().port, clientFactory)
        self.addCleanup(connector.disconnect)

        finished.addCallback(lambda ign: reactor.stop())
        self.runReactor(reactor)
        lostConnectionResults[0].trap(ConnectionClosed)
        lostConnectionResults[1].trap(ConnectionClosed)



class TLSPortTestsBuilder(TLSMixin, ContextGeneratingMixin,
                          ObjectModelIntegrationMixin, BadContextTestsMixin,
                          StreamTransportTestsMixin, ReactorBuilder):
    """
    Tests for L{IReactorSSL.listenSSL}
    """
    def getListeningPort(self, reactor, factory):
        """
        Get a TLS port from a reactor.
        """
        return reactor.listenSSL(0, factory, self.getServerContext())


    def getExpectedStartListeningLogMessage(self, port, factory):
        """
        Get the message expected to be logged when a TLS port starts listening.
        """
        return "%s (TLS) starting on %d" % (factory, port.getHost().port)


    def getExpectedConnectionLostLogMsg(self, port):
        """
        Get the expected connection lost message for a TLS port.
        """
        return "(TLS Port %s Closed)" % (port.getHost().port,)


    def test_badContext(self):
        """
        If the context factory passed to L{IReactorSSL.listenSSL} raises an
        exception from its C{getContext} method, that exception is raised by
        L{IReactorSSL.listenSSL}.
        """
        def useIt(reactor, contextFactory):
            return reactor.listenSSL(0, ServerFactory(), contextFactory)
        self._testBadContext(useIt)



globals().update(SSLClientTestsMixin.makeTestCaseClasses())
globals().update(StartTLSClientTestsMixin.makeTestCaseClasses())
globals().update(TLSPortTestsBuilder().makeTestCaseClasses())



class AbortSSLConnectionTest(ReactorBuilder, AbortConnectionMixin, ContextGeneratingMixin):
    requiredInterfaces = (IReactorSSL,)

    def buildReactor(self):
        reactor = ReactorBuilder.buildReactor(self)
        try:
            from twisted.protocols import tls
        except ImportError:
            return reactor

        # Patch twisted.protocols.tls to use this reactor, until we get
        # around to fixing #5206, or the TLS code uses an explicit reactor:
        cooperator = Cooperator(
            scheduler=lambda x: reactor.callLater(0.00001, x))
        self.patch(tls, "cooperate", cooperator.cooperate)
        return reactor


    def setUp(self):
        if FILETYPE_PEM is None:
            raise SkipTest("OpenSSL not available.")
        self.serverContext = self.getServerContext()
        self.clientContext = self.getClientContext()
        self.clientContext.method = self.serverContext.method


    def listen(self, reactor, server):
        """
        Listen using SSL.
        """
        return reactor.listenSSL(
            0, server, self.serverContext, interface="127.0.0.1")


    def connect(self, clientcreator, serverport):
        """
        Connect using SSL.
        """
        return clientcreator.connectSSL(
            serverport.getHost().host, serverport.getHost().port,
            self.clientContext)

globals().update(AbortSSLConnectionTest.makeTestCaseClasses())
