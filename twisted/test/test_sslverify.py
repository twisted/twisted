# Copyright 2005 Divmod, Inc.  See LICENSE file for details

import itertools

from OpenSSL import SSL
from OpenSSL.crypto import PKey, X509, X509Req
from OpenSSL.crypto import TYPE_RSA

from twisted.trial import unittest
from twisted.internet import protocol, defer, reactor
from twisted.python import log

from twisted.internet import _sslverify as sslverify

counter = itertools.count().next
def makeCertificate(**kw):
    keypair = PKey()
    keypair.generate_key(TYPE_RSA, 1024)

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

def otherMakeCertificate(**kw):
    keypair = PKey()
    keypair.generate_key(TYPE_RSA, 1024)

    req = X509Req()
    subj = req.get_subject()
    for (k, v) in kw.items():
        setattr(subj, k, v)

    req.set_pubkey(keypair)
    req.sign(keypair, "md5")

    cert = X509()
    cert.set_serial_number(counter())
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(60 * 60 * 24 * 365) # One year

    cert.set_issuer(req.get_subject())
    cert.set_subject(req.get_subject())
    cert.set_pubkey(req.get_pubkey())
    cert.sign(keypair, "md5")

    return keypair, cert


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

    def setUpClass(self):
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
        self.clientConn = reactor.connectSSL('127.0.0.1', self.serverPort.getHost().port,
                                             clientFactory, clientCertOpts)

    def testAbbreviatingDistinguishedNames(self):
        self.assertEquals(sslverify.DN(CN='a', OU='hello'),
                          sslverify.DistinguishedName(commonName='a', organizationalUnitName='hello'))
        self.assertNotEquals(sslverify.DN(CN='a', OU='hello'),
                             sslverify.DN(CN='a', OU='hello', emailAddress='xxx'))
        dn = sslverify.DN(CN='abcdefg')
        self.assertRaises(AttributeError, setattr, dn, 'Cn', 'x')
        self.assertEquals(dn.CN, dn.commonName)
        dn.CN = 'bcdefga'
        self.assertEquals(dn.CN, dn.commonName)

    
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


    def testAllowedAnonymousClientConnection(self):
        onData = defer.Deferred()
        self.loopback(sslverify.OpenSSLCertificateOptions(privateKey=self.sKey, certificate=self.sCert, requireCertificate=False),
                      sslverify.OpenSSLCertificateOptions(requireCertificate=False),
                      onData=onData)

        return onData.addCallback(
            lambda result: self.assertEquals(result, WritingProtocol.byte))

    def testRefusedAnonymousClientConnection(self):
        onServerLost = defer.Deferred()
        onClientLost = defer.Deferred()
        self.loopback(sslverify.OpenSSLCertificateOptions(privateKey=self.sKey, certificate=self.sCert, verify=True, caCerts=[self.sCert], requireCertificate=True),
                      sslverify.OpenSSLCertificateOptions(requireCertificate=False),
                      onServerLost=onServerLost,
                      onClientLost=onClientLost)

        d = defer.DeferredList([onClientLost, onServerLost], consumeErrors=True)


        def afterLost(((cSuccess, cResult), (sSuccess, sResult))):

            self.failIf(cSuccess)
            self.failIf(sSuccess)

            # XXX Twisted doesn't report SSL errors as SSL errors, but in the
            # future it will.

            # cResult.trap(SSL.Error)
            # sResult.trap(SSL.Error)

            # Twisted trunk will do the correct thing here, and not log any
            # errors.  Twisted 2.1 will do the wrong thing.  We're flushing
            # errors until the buildbot is updated to a reasonable facsimilie
            # of 2.2.
            log.flushErrors(SSL.Error)

        return d.addCallback(afterLost)

    def testFailedCertificateVerification(self):
        onServerLost = defer.Deferred()
        onClientLost = defer.Deferred()
        self.loopback(sslverify.OpenSSLCertificateOptions(privateKey=self.sKey, certificate=self.sCert, verify=False, requireCertificate=False),
                      sslverify.OpenSSLCertificateOptions(verify=True, requireCertificate=False, caCerts=[self.cCert]),
                      onServerLost=onServerLost,
                      onClientLost=onClientLost)

        d = defer.DeferredList([onClientLost, onServerLost], consumeErrors=True)
        def afterLost(((cSuccess, cResult), (sSuccess, sResult))):

            self.failIf(cSuccess)
            self.failIf(sSuccess)

            # Twisted trunk will do the correct thing here, and not log any
            # errors.  Twisted 2.1 will do the wrong thing.  We're flushing
            # errors until the buildbot is updated to a reasonable facsimilie
            # of 2.2.
            log.flushErrors(SSL.Error)

        return d.addCallback(afterLost)

    def testSuccessfulCertificateVerification(self):
        onData = defer.Deferred()
        self.loopback(sslverify.OpenSSLCertificateOptions(privateKey=self.sKey, certificate=self.sCert, verify=False, requireCertificate=False),
                      sslverify.OpenSSLCertificateOptions(verify=True, requireCertificate=True, caCerts=[self.sCert]),
                      onData=onData)

        return onData.addCallback(lambda result: self.assertEquals(result, WritingProtocol.byte))

    def testSuccessfulSymmetricSelfSignedCertificateVerification(self):
        onData = defer.Deferred()
        self.loopback(sslverify.OpenSSLCertificateOptions(privateKey=self.sKey, certificate=self.sCert, verify=True, requireCertificate=True, caCerts=[self.cCert]),
                      sslverify.OpenSSLCertificateOptions(privateKey=self.cKey, certificate=self.cCert, verify=True, requireCertificate=True, caCerts=[self.sCert]),
                      onData=onData)

        return onData.addCallback(lambda result: self.assertEquals(result, WritingProtocol.byte))

    def testVerification(self):
        clientDN = sslverify.DistinguishedName(commonName='client')
        clientKey = sslverify.KeyPair.generate()
        clientCertReq = clientKey.certificateRequest(clientDN)

        serverDN = sslverify.DistinguishedName(commonName='server')
        serverKey = sslverify.KeyPair.generate()
        serverCertReq = serverKey.certificateRequest(serverDN)

        ##
        clientSelfCertReq = clientKey.certificateRequest(clientDN)
        clientSelfCertData = clientKey.signCertificateRequest(clientDN, clientSelfCertReq,
                                                              lambda dn: True,
                                                              132)
        clientSelfCert = clientKey.newCertificate(clientSelfCertData)
        ##

        ##
        serverSelfCertReq = serverKey.certificateRequest(serverDN)
        serverSelfCertData = serverKey.signCertificateRequest(serverDN, serverSelfCertReq,
                                                              lambda dn: True,
                                                              516)
        serverSelfCert = serverKey.newCertificate(serverSelfCertData)
        ##

        ##
        clientCertData = serverKey.signCertificateRequest(serverDN, clientCertReq,
                                                          lambda dn: True,
                                                          7)
        clientCert = clientKey.newCertificate(clientCertData)
        ##

        ##
        serverCertData = clientKey.signCertificateRequest(clientDN, serverCertReq,
                                                          lambda dn: True,
                                                          42)
        serverCert = serverKey.newCertificate(serverCertData)
        ##

        onData = defer.Deferred()

        serverOpts = serverCert.options(serverSelfCert)
        clientOpts = clientCert.options(clientSelfCert)

        self.loopback(serverOpts,
                      clientOpts,
                      onData=onData)

        return onData.addCallback(lambda result: self.assertEquals(result, WritingProtocol.byte))
