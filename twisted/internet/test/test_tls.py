# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{ITLSTransport}.
"""

__metaclass__ = type

from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.internet.protocol import ServerFactory, ClientFactory, Protocol
from twisted.internet.interfaces import ITLSTransport
from twisted.internet.defer import Deferred, DeferredList
from twisted.internet.error import ConnectionClosed
from twisted.trial.unittest import SkipTest
from twisted.python.runtime import platform

try:
    from OpenSSL.crypto import FILETYPE_PEM
except ImportError:
    FILETYPE_PEM = None
else:
    from twisted.internet.ssl import PrivateCertificate, KeyPair
    from twisted.internet.ssl import ClientContextFactory



class SSLClientTestsMixin(ReactorBuilder):
    """
    Mixin defining tests relating to L{ITLSTransport}.
    """
    if FILETYPE_PEM is None:
        skip = "OpenSSL is unavailable"

    if platform.isWindows():
        msg = (
            "For some reason, these reactors don't deal with SSL "
            "disconnection correctly on Windows.  See #3371.")
        skippedReactors = {
            "twisted.internet.glib2reactor.Glib2Reactor": msg,
            "twisted.internet.gtk2reactor.Gtk2Reactor": msg}


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

        serverFactory = ServerFactory()
        serverFactory.finished = Deferred()
        serverFactory.protocol = ShortProtocol
        serverFactory.context = self.getServerContext()

        clientFactory = ClientFactory()
        clientFactory.finished = Deferred()
        clientFactory.protocol = ShortProtocol
        clientFactory.context = ClientContextFactory()
        clientFactory.context.method = serverFactory.context.method

        lostConnectionResults = []
        finished = DeferredList(
            [serverFactory.finished, clientFactory.finished],
            consumeErrors=True)
        def cbFinished(results):
            lostConnectionResults.extend([results[0][1], results[1][1]])
        finished.addCallback(cbFinished)

        reactor = self.buildReactor()

        port = reactor.listenTCP(0, serverFactory, interface='127.0.0.1')
        self.addCleanup(port.stopListening)

        connector = reactor.connectTCP(
            port.getHost().host, port.getHost().port, clientFactory)
        self.addCleanup(connector.disconnect)

        finished.addCallback(lambda ign: reactor.stop())
        self.runReactor(reactor)
        lostConnectionResults[0].trap(ConnectionClosed)
        lostConnectionResults[1].trap(ConnectionClosed)


globals().update(SSLClientTestsMixin.makeTestCaseClasses())
