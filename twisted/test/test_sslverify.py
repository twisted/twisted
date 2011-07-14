# Copyright 2005 Divmod, Inc.  See LICENSE file for details
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet._sslverify}.
"""

import itertools

try:
    from OpenSSL import SSL
    from OpenSSL.crypto import PKey, X509, X509Req
    from OpenSSL.crypto import TYPE_RSA
    from twisted.internet import _sslverify as sslverify
except ImportError:
    pass

from twisted.trial import unittest
from twisted.internet import protocol, defer, reactor
from twisted.python.reflect import objgrep, isSame
from twisted.python import log

from twisted.internet.error import CertificateError, ConnectionLost
from twisted.internet import interfaces


# A couple of static PEM-format certificates to be used by various tests.
A_HOST_CERTIFICATE_PEM = """
-----BEGIN CERTIFICATE-----
        MIIC2jCCAkMCAjA5MA0GCSqGSIb3DQEBBAUAMIG0MQswCQYDVQQGEwJVUzEiMCAG
        A1UEAxMZZXhhbXBsZS50d2lzdGVkbWF0cml4LmNvbTEPMA0GA1UEBxMGQm9zdG9u
        MRwwGgYDVQQKExNUd2lzdGVkIE1hdHJpeCBMYWJzMRYwFAYDVQQIEw1NYXNzYWNo
        dXNldHRzMScwJQYJKoZIhvcNAQkBFhhub2JvZHlAdHdpc3RlZG1hdHJpeC5jb20x
        ETAPBgNVBAsTCFNlY3VyaXR5MB4XDTA2MDgxNjAxMDEwOFoXDTA3MDgxNjAxMDEw
        OFowgbQxCzAJBgNVBAYTAlVTMSIwIAYDVQQDExlleGFtcGxlLnR3aXN0ZWRtYXRy
        aXguY29tMQ8wDQYDVQQHEwZCb3N0b24xHDAaBgNVBAoTE1R3aXN0ZWQgTWF0cml4
        IExhYnMxFjAUBgNVBAgTDU1hc3NhY2h1c2V0dHMxJzAlBgkqhkiG9w0BCQEWGG5v
        Ym9keUB0d2lzdGVkbWF0cml4LmNvbTERMA8GA1UECxMIU2VjdXJpdHkwgZ8wDQYJ
        KoZIhvcNAQEBBQADgY0AMIGJAoGBAMzH8CDF/U91y/bdbdbJKnLgnyvQ9Ig9ZNZp
        8hpsu4huil60zF03+Lexg2l1FIfURScjBuaJMR6HiMYTMjhzLuByRZ17KW4wYkGi
        KXstz03VIKy4Tjc+v4aXFI4XdRw10gGMGQlGGscXF/RSoN84VoDKBfOMWdXeConJ
        VyC4w3iJAgMBAAEwDQYJKoZIhvcNAQEEBQADgYEAviMT4lBoxOgQy32LIgZ4lVCj
        JNOiZYg8GMQ6y0ugp86X80UjOvkGtNf/R7YgED/giKRN/q/XJiLJDEhzknkocwmO
        S+4b2XpiaZYxRyKWwL221O7CGmtWYyZl2+92YYmmCiNzWQPfP6BOMlfax0AGLHls
        fXzCWdG0O/3Lk2SRM0I=
-----END CERTIFICATE-----
"""

A_PEER_CERTIFICATE_PEM = """
-----BEGIN CERTIFICATE-----
        MIIC3jCCAkcCAjA6MA0GCSqGSIb3DQEBBAUAMIG2MQswCQYDVQQGEwJVUzEiMCAG
        A1UEAxMZZXhhbXBsZS50d2lzdGVkbWF0cml4LmNvbTEPMA0GA1UEBxMGQm9zdG9u
        MRwwGgYDVQQKExNUd2lzdGVkIE1hdHJpeCBMYWJzMRYwFAYDVQQIEw1NYXNzYWNo
        dXNldHRzMSkwJwYJKoZIhvcNAQkBFhpzb21lYm9keUB0d2lzdGVkbWF0cml4LmNv
        bTERMA8GA1UECxMIU2VjdXJpdHkwHhcNMDYwODE2MDEwMTU2WhcNMDcwODE2MDEw
        MTU2WjCBtjELMAkGA1UEBhMCVVMxIjAgBgNVBAMTGWV4YW1wbGUudHdpc3RlZG1h
        dHJpeC5jb20xDzANBgNVBAcTBkJvc3RvbjEcMBoGA1UEChMTVHdpc3RlZCBNYXRy
        aXggTGFiczEWMBQGA1UECBMNTWFzc2FjaHVzZXR0czEpMCcGCSqGSIb3DQEJARYa
        c29tZWJvZHlAdHdpc3RlZG1hdHJpeC5jb20xETAPBgNVBAsTCFNlY3VyaXR5MIGf
        MA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCnm+WBlgFNbMlHehib9ePGGDXF+Nz4
        CjGuUmVBaXCRCiVjg3kSDecwqfb0fqTksBZ+oQ1UBjMcSh7OcvFXJZnUesBikGWE
        JE4V8Bjh+RmbJ1ZAlUPZ40bAkww0OpyIRAGMvKG+4yLFTO4WDxKmfDcrOb6ID8WJ
        e1u+i3XGkIf/5QIDAQABMA0GCSqGSIb3DQEBBAUAA4GBAD4Oukm3YYkhedUepBEA
        vvXIQhVDqL7mk6OqYdXmNj6R7ZMC8WWvGZxrzDI1bZuB+4aIxxd1FXC3UOHiR/xg
        i9cDl1y8P/qRp4aEBNF6rI0D4AxTbfnHQx4ERDAOShJdYZs/2zifPJ6va6YvrEyr
        yqDtGhklsWW3ZwBzEh5VEOUp
-----END CERTIFICATE-----
"""



counter = itertools.count().next
def makeCertificate(**kw):
    keypair = PKey()
    keypair.generate_key(TYPE_RSA, 512)

    certificate = X509()
    certificate.gmtime_adj_notBefore(0)
    certificate.gmtime_adj_notAfter(60 * 60 * 24 * 365) # One year
    for xname in certificate.get_issuer(), certificate.get_subject():
        for (k, v) in kw.items():
            setattr(xname, k, v)

    certificate.set_serial_number(counter())
    certificate.set_pubkey(keypair)
    certificate.sign(keypair, "md5")

    return keypair, certificate



class DataCallbackProtocol(protocol.Protocol):
    def dataReceived(self, data):
        d, self.factory.onData = self.factory.onData, None
        if d is not None:
            d.callback(data)

    def connectionLost(self, reason):
        d, self.factory.onLost = self.factory.onLost, None
        if d is not None:
            d.errback(reason)

class WritingProtocol(protocol.Protocol):
    byte = 'x'
    def connectionMade(self):
        self.transport.write(self.byte)

    def connectionLost(self, reason):
        self.factory.onLost.errback(reason)


class OpenSSLOptions(unittest.TestCase):
    serverPort = clientConn = None
    onServerLost = onClientLost = None

    sKey = None
    sCert = None
    cKey = None
    cCert = None

    def setUp(self):
        """
        Create class variables of client and server certificates.
        """
        self.sKey, self.sCert = makeCertificate(
            O="Server Test Certificate",
            CN="server")
        self.cKey, self.cCert = makeCertificate(
            O="Client Test Certificate",
            CN="client")

    def tearDown(self):
        if self.serverPort is not None:
            self.serverPort.stopListening()
        if self.clientConn is not None:
            self.clientConn.disconnect()

        L = []
        if self.onServerLost is not None:
            L.append(self.onServerLost)
        if self.onClientLost is not None:
            L.append(self.onClientLost)

        return defer.DeferredList(L, consumeErrors=True)

    def loopback(self, serverCertOpts, clientCertOpts,
                 onServerLost=None, onClientLost=None, onData=None):
        if onServerLost is None:
            self.onServerLost = onServerLost = defer.Deferred()
        if onClientLost is None:
            self.onClientLost = onClientLost = defer.Deferred()
        if onData is None:
            onData = defer.Deferred()

        serverFactory = protocol.ServerFactory()
        serverFactory.protocol = DataCallbackProtocol
        serverFactory.onLost = onServerLost
        serverFactory.onData = onData

        clientFactory = protocol.ClientFactory()
        clientFactory.protocol = WritingProtocol
        clientFactory.onLost = onClientLost

        self.serverPort = reactor.listenSSL(0, serverFactory, serverCertOpts)
        self.clientConn = reactor.connectSSL('127.0.0.1',
                self.serverPort.getHost().port, clientFactory, clientCertOpts)

    def test_abbreviatingDistinguishedNames(self):
        """
        Check that abbreviations used in certificates correctly map to
        complete names.
        """
        self.assertEqual(
                sslverify.DN(CN='a', OU='hello'),
                sslverify.DistinguishedName(commonName='a',
                                            organizationalUnitName='hello'))
        self.assertNotEquals(
                sslverify.DN(CN='a', OU='hello'),
                sslverify.DN(CN='a', OU='hello', emailAddress='xxx'))
        dn = sslverify.DN(CN='abcdefg')
        self.assertRaises(AttributeError, setattr, dn, 'Cn', 'x')
        self.assertEqual(dn.CN, dn.commonName)
        dn.CN = 'bcdefga'
        self.assertEqual(dn.CN, dn.commonName)


    def testInspectDistinguishedName(self):
        n = sslverify.DN(commonName='common name',
                         organizationName='organization name',
                         organizationalUnitName='organizational unit name',
                         localityName='locality name',
                         stateOrProvinceName='state or province name',
                         countryName='country name',
                         emailAddress='email address')
        s = n.inspect()
        for k in [
            'common name',
            'organization name',
            'organizational unit name',
            'locality name',
            'state or province name',
            'country name',
            'email address']:
            self.assertIn(k, s, "%r was not in inspect output." % (k,))
            self.assertIn(k.title(), s, "%r was not in inspect output." % (k,))


    def testInspectDistinguishedNameWithoutAllFields(self):
        n = sslverify.DN(localityName='locality name')
        s = n.inspect()
        for k in [
            'common name',
            'organization name',
            'organizational unit name',
            'state or province name',
            'country name',
            'email address']:
            self.assertNotIn(k, s, "%r was in inspect output." % (k,))
            self.assertNotIn(k.title(), s, "%r was in inspect output." % (k,))
        self.assertIn('locality name', s)
        self.assertIn('Locality Name', s)


    def test_inspectCertificate(self):
        """
        Test that the C{inspect} method of L{sslverify.Certificate} returns
        a human-readable string containing some basic information about the
        certificate.
        """
        c = sslverify.Certificate.loadPEM(A_HOST_CERTIFICATE_PEM)
        self.assertEqual(
            c.inspect().split('\n'),
            ["Certificate For Subject:",
             "  Organizational Unit Name: Security",
             "         Organization Name: Twisted Matrix Labs",
             "               Common Name: example.twistedmatrix.com",
             "    State Or Province Name: Massachusetts",
             "              Country Name: US",
             "             Email Address: nobody@twistedmatrix.com",
             "             Locality Name: Boston",
             "",
             "Issuer:",
             "  Organizational Unit Name: Security",
             "         Organization Name: Twisted Matrix Labs",
             "               Common Name: example.twistedmatrix.com",
             "    State Or Province Name: Massachusetts",
             "              Country Name: US",
             "             Email Address: nobody@twistedmatrix.com",
             "             Locality Name: Boston",
             "",
             "Serial Number: 12345",
             "Digest: C4:96:11:00:30:C3:EC:EE:A3:55:AA:ED:8C:84:85:18",
             "Public Key with Hash: ff33994c80812aa95a79cdb85362d054"])


    def test_certificateOptionsSerialization(self):
        """
        Test that __setstate__(__getstate__()) round-trips properly.
        """
        firstOpts = sslverify.OpenSSLCertificateOptions(
            privateKey=self.sKey,
            certificate=self.sCert,
            method=SSL.SSLv3_METHOD,
            verify=True,
            caCerts=[self.sCert],
            verifyDepth=2,
            requireCertificate=False,
            verifyOnce=False,
            enableSingleUseKeys=False,
            enableSessions=False,
            fixBrokenPeers=True,
            enableSessionTickets=True)
        context = firstOpts.getContext()
        state = firstOpts.__getstate__()

        # The context shouldn't be in the state to serialize
        self.failIf(objgrep(state, context, isSame),
                    objgrep(state, context, isSame))

        opts = sslverify.OpenSSLCertificateOptions()
        opts.__setstate__(state)
        self.assertEqual(opts.privateKey, self.sKey)
        self.assertEqual(opts.certificate, self.sCert)
        self.assertEqual(opts.method, SSL.SSLv3_METHOD)
        self.assertEqual(opts.verify, True)
        self.assertEqual(opts.caCerts, [self.sCert])
        self.assertEqual(opts.verifyDepth, 2)
        self.assertEqual(opts.requireCertificate, False)
        self.assertEqual(opts.verifyOnce, False)
        self.assertEqual(opts.enableSingleUseKeys, False)
        self.assertEqual(opts.enableSessions, False)
        self.assertEqual(opts.fixBrokenPeers, True)
        self.assertEqual(opts.enableSessionTickets, True)


    def test_certificateOptionsSessionTickets(self):
        """
        Enabling session tickets should not set the OP_NO_TICKET option.
        """
        opts = sslverify.OpenSSLCertificateOptions(enableSessionTickets=True)
        ctx = opts.getContext()
        self.assertEqual(0, ctx.set_options(0) & 0x00004000)


    def test_certificateOptionsSessionTicketsDisabled(self):
        """
        Enabling session tickets should set the OP_NO_TICKET option.
        """
        opts = sslverify.OpenSSLCertificateOptions(enableSessionTickets=False)
        ctx = opts.getContext()
        self.assertEqual(0x00004000, ctx.set_options(0) & 0x00004000)


    def test_allowedAnonymousClientConnection(self):
        """
        Check that anonymous connections are allowed when certificates aren't
        required on the server.
        """
        onData = defer.Deferred()
        self.loopback(sslverify.OpenSSLCertificateOptions(privateKey=self.sKey,
                            certificate=self.sCert, requireCertificate=False),
                      sslverify.OpenSSLCertificateOptions(
                          requireCertificate=False),
                      onData=onData)

        return onData.addCallback(
            lambda result: self.assertEqual(result, WritingProtocol.byte))

    def test_refusedAnonymousClientConnection(self):
        """
        Check that anonymous connections are refused when certificates are
        required on the server.
        """
        onServerLost = defer.Deferred()
        onClientLost = defer.Deferred()
        self.loopback(sslverify.OpenSSLCertificateOptions(privateKey=self.sKey,
                            certificate=self.sCert, verify=True,
                            caCerts=[self.sCert], requireCertificate=True),
                      sslverify.OpenSSLCertificateOptions(
                          requireCertificate=False),
                      onServerLost=onServerLost,
                      onClientLost=onClientLost)

        d = defer.DeferredList([onClientLost, onServerLost],
                               consumeErrors=True)


        def afterLost(((cSuccess, cResult), (sSuccess, sResult))):

            self.failIf(cSuccess)
            self.failIf(sSuccess)
            # Win32 fails to report the SSL Error, and report a connection lost
            # instead: there is a race condition so that's not totally
            # surprising (see ticket #2877 in the tracker)
            self.assertIsInstance(cResult.value, (SSL.Error, ConnectionLost))
            self.assertIsInstance(sResult.value, SSL.Error)

        return d.addCallback(afterLost)

    def test_failedCertificateVerification(self):
        """
        Check that connecting with a certificate not accepted by the server CA
        fails.
        """
        onServerLost = defer.Deferred()
        onClientLost = defer.Deferred()
        self.loopback(sslverify.OpenSSLCertificateOptions(privateKey=self.sKey,
                            certificate=self.sCert, verify=False,
                            requireCertificate=False),
                      sslverify.OpenSSLCertificateOptions(verify=True,
                            requireCertificate=False, caCerts=[self.cCert]),
                      onServerLost=onServerLost,
                      onClientLost=onClientLost)

        d = defer.DeferredList([onClientLost, onServerLost],
                               consumeErrors=True)
        def afterLost(((cSuccess, cResult), (sSuccess, sResult))):

            self.failIf(cSuccess)
            self.failIf(sSuccess)

        return d.addCallback(afterLost)

    def test_successfulCertificateVerification(self):
        """
        Test a successful connection with client certificate validation on
        server side.
        """
        onData = defer.Deferred()
        self.loopback(sslverify.OpenSSLCertificateOptions(privateKey=self.sKey,
                            certificate=self.sCert, verify=False,
                            requireCertificate=False),
                      sslverify.OpenSSLCertificateOptions(verify=True,
                            requireCertificate=True, caCerts=[self.sCert]),
                      onData=onData)

        return onData.addCallback(
                lambda result: self.assertEqual(result, WritingProtocol.byte))

    def test_successfulSymmetricSelfSignedCertificateVerification(self):
        """
        Test a successful connection with validation on both server and client
        sides.
        """
        onData = defer.Deferred()
        self.loopback(sslverify.OpenSSLCertificateOptions(privateKey=self.sKey,
                            certificate=self.sCert, verify=True,
                            requireCertificate=True, caCerts=[self.cCert]),
                      sslverify.OpenSSLCertificateOptions(privateKey=self.cKey,
                            certificate=self.cCert, verify=True,
                            requireCertificate=True, caCerts=[self.sCert]),
                      onData=onData)

        return onData.addCallback(
                lambda result: self.assertEqual(result, WritingProtocol.byte))

    def test_verification(self):
        """
        Check certificates verification building custom certificates data.
        """
        clientDN = sslverify.DistinguishedName(commonName='client')
        clientKey = sslverify.KeyPair.generate()
        clientCertReq = clientKey.certificateRequest(clientDN)

        serverDN = sslverify.DistinguishedName(commonName='server')
        serverKey = sslverify.KeyPair.generate()
        serverCertReq = serverKey.certificateRequest(serverDN)

        clientSelfCertReq = clientKey.certificateRequest(clientDN)
        clientSelfCertData = clientKey.signCertificateRequest(
                clientDN, clientSelfCertReq, lambda dn: True, 132)
        clientSelfCert = clientKey.newCertificate(clientSelfCertData)

        serverSelfCertReq = serverKey.certificateRequest(serverDN)
        serverSelfCertData = serverKey.signCertificateRequest(
                serverDN, serverSelfCertReq, lambda dn: True, 516)
        serverSelfCert = serverKey.newCertificate(serverSelfCertData)

        clientCertData = serverKey.signCertificateRequest(
                serverDN, clientCertReq, lambda dn: True, 7)
        clientCert = clientKey.newCertificate(clientCertData)

        serverCertData = clientKey.signCertificateRequest(
                clientDN, serverCertReq, lambda dn: True, 42)
        serverCert = serverKey.newCertificate(serverCertData)

        onData = defer.Deferred()

        serverOpts = serverCert.options(serverSelfCert)
        clientOpts = clientCert.options(clientSelfCert)

        self.loopback(serverOpts,
                      clientOpts,
                      onData=onData)

        return onData.addCallback(
                lambda result: self.assertEqual(result, WritingProtocol.byte))



if interfaces.IReactorSSL(reactor, None) is None:
    OpenSSLOptions.skip = "Reactor does not support SSL, cannot run SSL tests"



class _NotSSLTransport:
    def getHandle(self):
        return self

class _MaybeSSLTransport:
    def getHandle(self):
        return self

    def get_peer_certificate(self):
        return None

    def get_host_certificate(self):
        return None


class _ActualSSLTransport:
    def getHandle(self):
        return self

    def get_host_certificate(self):
        return sslverify.Certificate.loadPEM(A_HOST_CERTIFICATE_PEM).original

    def get_peer_certificate(self):
        return sslverify.Certificate.loadPEM(A_PEER_CERTIFICATE_PEM).original


class Constructors(unittest.TestCase):
    def test_peerFromNonSSLTransport(self):
        """
        Verify that peerFromTransport raises an exception if the transport
        passed is not actually an SSL transport.
        """
        x = self.assertRaises(CertificateError,
                              sslverify.Certificate.peerFromTransport,
                              _NotSSLTransport())
        self.failUnless(str(x).startswith("non-TLS"))

    def test_peerFromBlankSSLTransport(self):
        """
        Verify that peerFromTransport raises an exception if the transport
        passed is an SSL transport, but doesn't have a peer certificate.
        """
        x = self.assertRaises(CertificateError,
                              sslverify.Certificate.peerFromTransport,
                              _MaybeSSLTransport())
        self.failUnless(str(x).startswith("TLS"))

    def test_hostFromNonSSLTransport(self):
        """
        Verify that hostFromTransport raises an exception if the transport
        passed is not actually an SSL transport.
        """
        x = self.assertRaises(CertificateError,
                              sslverify.Certificate.hostFromTransport,
                              _NotSSLTransport())
        self.failUnless(str(x).startswith("non-TLS"))

    def test_hostFromBlankSSLTransport(self):
        """
        Verify that hostFromTransport raises an exception if the transport
        passed is an SSL transport, but doesn't have a host certificate.
        """
        x = self.assertRaises(CertificateError,
                              sslverify.Certificate.hostFromTransport,
                              _MaybeSSLTransport())
        self.failUnless(str(x).startswith("TLS"))


    def test_hostFromSSLTransport(self):
        """
        Verify that hostFromTransport successfully creates the correct
        certificate if passed a valid SSL transport.
        """
        self.assertEqual(
            sslverify.Certificate.hostFromTransport(
                _ActualSSLTransport()).serialNumber(),
            12345)

    def test_peerFromSSLTransport(self):
        """
        Verify that peerFromTransport successfully creates the correct
        certificate if passed a valid SSL transport.
        """
        self.assertEqual(
            sslverify.Certificate.peerFromTransport(
                _ActualSSLTransport()).serialNumber(),
            12346)



if interfaces.IReactorSSL(reactor, None) is None:
    Constructors.skip = "Reactor does not support SSL, cannot run SSL tests"
