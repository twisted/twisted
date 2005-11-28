# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from __future__ import nested_scopes
from twisted.trial import unittest
from twisted.internet import protocol, reactor, interfaces, defer
from twisted.protocols import basic
from twisted.python import util, components, log
from twisted.test import test_tcp

import os

try:
    from OpenSSL import SSL, crypto
    from twisted.internet import ssl
    from ssl_helpers import ClientTLSContext
except ImportError:
    SSL = ssl = None

certPath = util.sibpath(__file__, "server.pem")

class UnintelligentProtocol(basic.LineReceiver):
    pretext = [
        "first line",
        "last thing before tls starts",
        "STARTTLS"]

    posttext = [
        "first thing after tls started",
        "last thing ever"]

    def connectionMade(self):
        for l in self.pretext:
            self.sendLine(l)

    def lineReceived(self, line):
        if line == "READY":
            self.transport.startTLS(ClientTLSContext(), self.factory.client)
            for l in self.posttext:
                self.sendLine(l)
            self.transport.loseConnection()


class LineCollector(basic.LineReceiver):
    def __init__(self, doTLS, fillBuffer=0):
        self.doTLS = doTLS
        self.fillBuffer = fillBuffer

    def connectionMade(self):
        self.factory.rawdata = ''
        self.factory.lines = []

    def lineReceived(self, line):
        self.factory.lines.append(line)
        if line == 'STARTTLS':
            if self.fillBuffer:
                for x in range(500):
                    self.sendLine('X'*1000)
            self.sendLine('READY')
            if self.doTLS:
                ctx = ServerTLSContext(
                    privateKeyFileName=certPath,
                    certificateFileName=certPath,
                )
                self.transport.startTLS(ctx, self.factory.server)
            else:
                self.setRawMode()

    def rawDataReceived(self, data):
        self.factory.rawdata += data
        self.factory.done = 1

    def connectionLost(self, reason):
        self.factory.done = 1


class SingleLineServerProtocol(protocol.Protocol):
    def connectionMade(self):
        self.transport.identifier = 'SERVER'
        self.transport.write("+OK <some crap>\r\n")
        self.transport.getPeerCertificate()


class RecordingClientProtocol(protocol.Protocol):
    def connectionMade(self):
        self.transport.identifier = 'CLIENT'
        self.buffer = []
        self.transport.getPeerCertificate()

    def dataReceived(self, data):
        self.factory.buffer.append(data)


class ImmediatelyDisconnectingProtocol(protocol.Protocol):
    def connectionMade(self):
        self.transport.loseConnection()

    def connectionLost(self, reason):
        self.factory.connectionDisconnected.callback(None)


class AlmostImmediatelyDisconnectingProtocol(protocol.Protocol):
    def connectionMade(self):
        # Twisted's SSL support is terribly broken.
        reactor.callLater(0.1, self.transport.loseConnection)

    def connectionLost(self, reason):
        self.factory.connectionDisconnected.callback(reason)


def generateCertificateObjects(organization, organizationalUnit):
    pkey = crypto.PKey()
    pkey.generate_key(crypto.TYPE_RSA, 512)
    req = crypto.X509Req()
    subject = req.get_subject()
    subject.O = organization
    subject.OU = organizationalUnit
    req.set_pubkey(pkey)
    req.sign(pkey, "md5")

    # Here comes the actual certificate
    cert = crypto.X509()
    cert.set_serial_number(1)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(60) # Testing certificates need not be long lived
    cert.set_issuer(req.get_subject())
    cert.set_subject(req.get_subject())
    cert.set_pubkey(req.get_pubkey())
    cert.sign(pkey, "md5")

    return pkey, req, cert


def generateCertificateFiles(basename, organization, organizationalUnit):
    pkey, req, cert = generateCertificateObjects(organization, organizationalUnit)

    for ext, obj, dumpFunc in [
        ('key', pkey, crypto.dump_privatekey),
        ('req', req, crypto.dump_certificate_request),
        ('cert', cert, crypto.dump_certificate)]:
        fName = os.extsep.join((basename, ext))
        fObj = file(fName, 'w')
        fObj.write(dumpFunc(crypto.FILETYPE_PEM, obj))
        fObj.close()


class ContextGeneratingMixin:
    def makeContextFactory(self, org, orgUnit, *args, **kwArgs):
        base = self.mktemp()
        generateCertificateFiles(base, org, orgUnit)
        serverCtxFactory = ssl.DefaultOpenSSLContextFactory(
            os.extsep.join((base, 'key')),
            os.extsep.join((base, 'cert')),
            *args, **kwArgs)
        
        return base, serverCtxFactory
    
    def setupServerAndClient(self, clientArgs, clientKwArgs, serverArgs, serverKwArgs):
        self.clientBase, self.clientCtxFactory = self.makeContextFactory(
            *clientArgs, **clientKwArgs)
        self.serverBase, self.serverCtxFactory = self.makeContextFactory(
            *serverArgs, **serverKwArgs)


if SSL is not None:
    class ServerTLSContext(ssl.DefaultOpenSSLContextFactory):
        isClient = 0
        def __init__(self, *args, **kw):
            kw['sslmethod'] = SSL.TLSv1_METHOD
            ssl.DefaultOpenSSLContextFactory.__init__(self, *args, **kw)


class StolenTCPTestCase(test_tcp.ProperlyCloseFilesTestCase, test_tcp.WriteDataTestCase):
    def setUp(self):
        test_tcp.PortCleanerUpper.setUp(self)
        self.serverConns = []
        f = protocol.ServerFactory()
        f.protocol = protocol.Protocol
        self.listener = reactor.listenSSL(
            0, f, ssl.DefaultOpenSSLContextFactory(certPath, certPath), interface="127.0.0.1",
        )
        self.ports.append(self.listener)
        f = protocol.ClientFactory()
        f.protocol = test_tcp.ConnectionLosingProtocol

        f.protocol.master = self

        L = []
        def connector():
            p = self.listener.getHost().port
            ctx = ssl.ClientContextFactory()
            return reactor.connectSSL('127.0.0.1', p, f, ctx)
        self.connector = connector

        self.totalConnections = 0


class TLSTestCase(unittest.TestCase):
    fillBuffer = 0

    port = None
    clientProto = None
    serverProto = None

    def setUpClass(self):
        # This is really, really bad and really, really stupid.  If you are
        # reading this and Twisted has gained support for handling
        # SSL.Errors without automatically logging them (causing this test
        # to fail), please rewrite this test to *not* call ignoreErrors
        # here, and instead simply not log the exception that testUnTLS
        # induces:
        #
        # OpenSSL.SSL.Error: [('SSL routines', 'SSL3_READ_BYTES', 'ssl handshake failure')]
        #
        # This happens because only one side of the connection is speaking
        # SSL in that test method, the other end is just collecting bytes
        # and examining them.
        #
        # Until it is possible to avoid having this error logged, we have to
        # rely on the asserts in the tests making sure things are going
        # alright.
        log.ignoreErrors(SSL.Error)

    def tearDownClass(self):
        log.clearIgnores()

    def tearDown(self):
        if self.clientProto is not None and self.clientProto.transport is not None:
            self.clientProto.transport.loseConnection()
        if self.serverProto is not None and self.serverProto.transport is not None:
            self.serverProto.transport.loseConnection()

        if self.port is not None:
            return defer.maybeDeferred(self.port.stopListening)

    def _runTest(self, clientProto, serverProto, clientIsServer=False):
        self.clientProto = clientProto
        cf = self.clientFactory = protocol.ClientFactory()
        cf.protocol = lambda: clientProto
        if clientIsServer:
            cf.server = 0
        else:
            cf.client = 1

        self.serverProto = serverProto
        sf = self.serverFactory = protocol.ServerFactory()
        sf.protocol = lambda: serverProto
        if clientIsServer:
            sf.client = 0
        else:
            sf.server = 1

        if clientIsServer:
            inCharge = cf
        else:
            inCharge = sf
        inCharge.done = 0

        port = self.port = reactor.listenTCP(0, sf, interface="127.0.0.1")
        portNo = port.getHost().port

        reactor.connectTCP('127.0.0.1', portNo, cf)

        i = 0
        while i < 1000 and not inCharge.done:
            reactor.iterate(0.01)
            i += 1
        self.failUnless(
            inCharge.done,
            "Never finished reading all lines: %s" % (inCharge.lines,))


    def testTLS(self):
        self._runTest(UnintelligentProtocol(), LineCollector(1, self.fillBuffer))
        self.assertEquals(
            self.serverFactory.lines,
            UnintelligentProtocol.pretext + UnintelligentProtocol.posttext
        )


    def testUnTLS(self):
        self._runTest(UnintelligentProtocol(), LineCollector(0, self.fillBuffer))
        self.assertEquals(
            self.serverFactory.lines,
            UnintelligentProtocol.pretext
        )
        self.failUnless(self.serverFactory.rawdata, "No encrypted bytes received")


    def testBackwardsTLS(self):
        self._runTest(LineCollector(1, self.fillBuffer), UnintelligentProtocol(), True)
        self.assertEquals(
            self.clientFactory.lines,
            UnintelligentProtocol.pretext + UnintelligentProtocol.posttext
        )


class SpammyTLSTestCase(TLSTestCase):
    fillBuffer = 1
    def testTLS(self):
        TLSTestCase.testTLS(self)
    def testBackwardsTLS(self):
        TLSTestCase.testBackwardsTLS(self)

    testTLS.todo = "startTLS doesn't empty buffer before starting TLS. :("
    testBackwardsTLS.todo = "startTLS doesn't empty buffer before starting TLS. :("


class BufferingTestCase(unittest.TestCase):
    port = None
    connector = None
    serverProto = None
    clientProto = None

    def tearDown(self):
        if self.serverProto is not None and self.serverProto.transport is not None:
            self.serverProto.transport.loseConnection()
        if self.clientProto is not None and self.clientProto.transport is not None:
            self.clientProto.transport.loseConnection()
        if self.port is not None:
            return defer.maybeDeferred(self.port.stopListening)

    def testOpenSSLBuffering(self):
        serverProto = self.serverProto = SingleLineServerProtocol()
        clientProto = self.clientProto = RecordingClientProtocol()

        server = protocol.ServerFactory()
        client = self.client = protocol.ClientFactory()

        server.protocol = lambda: serverProto
        client.protocol = lambda: clientProto
        client.buffer = []

        sCTX = ssl.DefaultOpenSSLContextFactory(certPath, certPath)
        cCTX = ssl.ClientContextFactory()

        port = self.port = reactor.listenSSL(0, server, sCTX, interface='127.0.0.1')
        reactor.connectSSL('127.0.0.1', port.getHost().port, client, cCTX)

        i = 0
        while i < 5000 and not client.buffer:
            i += 1
            reactor.iterate()

        self.assertEquals(client.buffer, ["+OK <some crap>\r\n"])


class ConnectionLostTestCase(unittest.TestCase, ContextGeneratingMixin):

    def testImmediateDisconnect(self):
        org = "twisted.test.test_ssl"
        self.setupServerAndClient(
            (org, org + ", client"), {},
            (org, org + ", server"), {})
        
        # Set up a server, connect to it with a client, which should work since our verifiers
        # allow anything, then disconnect.
        serverProtocolFactory = protocol.ServerFactory()
        serverProtocolFactory.protocol = protocol.Protocol
        self.serverPort = serverPort = reactor.listenSSL(0, 
            serverProtocolFactory, self.serverCtxFactory)

        clientProtocolFactory = protocol.ClientFactory()
        clientProtocolFactory.protocol = ImmediatelyDisconnectingProtocol
        clientProtocolFactory.connectionDisconnected = defer.Deferred()
        clientConnector = reactor.connectSSL('127.0.0.1', 
            serverPort.getHost().port, clientProtocolFactory, self.clientCtxFactory)
        
        return clientProtocolFactory.connectionDisconnected.addCallback(
            lambda ignoredResult: self.serverPort.stopListening())

    def testFailedVerify(self):
        org = "twisted.test.test_ssl"
        self.setupServerAndClient(
            (org, org + ", client"), {},
            (org, org + ", server"), {})

        def verify(*a):
            return False
        self.clientCtxFactory.getContext().set_verify(SSL.VERIFY_PEER, verify)

        serverConnLost = defer.Deferred()
        serverProtocol = protocol.Protocol()
        serverProtocol.connectionLost = serverConnLost.callback
        serverProtocolFactory = protocol.ServerFactory()
        serverProtocolFactory.protocol = lambda: serverProtocol
        self.serverPort = serverPort = reactor.listenSSL(0,
            serverProtocolFactory, self.serverCtxFactory)

        clientConnLost = defer.Deferred()
        clientProtocol = protocol.Protocol()
        clientProtocol.connectionLost = clientConnLost.callback
        clientProtocolFactory = protocol.ClientFactory()
        clientProtocolFactory.protocol = lambda: clientProtocol
        clientConnector = reactor.connectSSL('127.0.0.1',
            serverPort.getHost().port, clientProtocolFactory, self.clientCtxFactory)

        dl = defer.DeferredList([serverConnLost, clientConnLost], consumeErrors=True)
        return dl.addCallback(self._cbLostConns)

    def _cbLostConns(self, results):
        (sSuccess, sResult), (cSuccess, cResult) = results

        self.failIf(sSuccess)
        self.failIf(cSuccess)

        sResult.trap(SSL.Error)
        cResult.trap(SSL.Error)

        return self.serverPort.stopListening()


if interfaces.IReactorSSL(reactor, None) is None:
    for tCase in [StolenTCPTestCase, TLSTestCase, SpammyTLSTestCase, 
                  BufferingTestCase, ConnectionLostTestCase]:
        tCase.skip = "Reactor does not support SSL, cannot run SSL tests"
