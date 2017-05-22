# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import zlib

from twisted.logger import Logger
from twisted.web import server, resource
from twisted.internet.task import Clock
from twisted.test import iosim, proto_helpers
from twisted.trial.unittest import SynchronousTestCase
from twisted.web.test.test_web import SimpleResource
from twisted.web.http import H2_ENABLED


class ServerTests(SynchronousTestCase):
    """
    Tests for L{twisted.web.server.server}.
    """

    def test_noAcceptEncoding(self):
        """
        L{server.server}s with C{compressResponses=True} will not compress
        responses with no C{Accept-Encoding} header.
        """
        sre = SimpleResource()
        r = resource.Resource()
        r.putChild(b'', sre)
        site = server.server(r, compressResponses=True)

        serverProtocol = site.buildProtocol(None)
        clientProtocol = proto_helpers.AccumulatingProtocol()

        c, s, pump = iosim.connectedServerAndClient(lambda: serverProtocol,
                                                    lambda: clientProtocol)

        c.transport.write(b"GET / HTTP/1.0\r\n\r\n")
        pump.flush()

        data = clientProtocol.data.split(b'\r\n')
        self.assertTrue(b'HTTP/1.0 200 OK' in data)
        self.assertFalse(b'Content-Encoding' in data)


    def test_logger(self):
        """
        L{server.server} with C{logger} will set the logger.
        """
        msg = []
        logger = Logger(observer=msg.append)
        sre = SimpleResource()
        r = resource.Resource()
        r.putChild(b'', sre)
        site = server.server(r, logger=logger)

        serverProtocol = site.buildProtocol(None)
        clientProtocol = proto_helpers.AccumulatingProtocol()

        c, s, pump = iosim.connectedServerAndClient(lambda: serverProtocol,
                                                    lambda: clientProtocol)

        c.transport.write(b"GET / HTTP/1.0\r\n\r\n")
        pump.flush()

        data = clientProtocol.data.split(b'\r\n')
        self.assertTrue(b'HTTP/1.0 200 OK' in data)
        self.assertFalse(b'Content-Encoding' in data)
        self.assertEqual(len(msg), 1)
        self.assertEqual(msg[0]["uri"], "/")


    def test_gzip(self):
        """
        L{server.server} with C{compressResponses=True} will compress eligible
        responses.
        """
        sre = SimpleResource()
        r = resource.Resource()
        r.putChild(b'', sre)
        site = server.server(r, compressResponses=True)

        serverProtocol = site.buildProtocol(None)
        clientProtocol = proto_helpers.AccumulatingProtocol()

        c, s, pump = iosim.connectedServerAndClient(lambda: serverProtocol,
                                                    lambda: clientProtocol)

        c.transport.write(b"GET / HTTP/1.0\r\nAccept-Encoding: gzip\r\n\r\n")
        pump.flush()

        data = clientProtocol.data.split(b'\r\n')
        self.assertTrue(b'HTTP/1.0 200 OK' in data)
        self.assertTrue(b'Content-Encoding: gzip' in data)
        body = clientProtocol.data.split(b'\r\n\r\n', 1)[1]
        self.assertEqual(b'correct',
                         zlib.decompress(body, 16 + zlib.MAX_WBITS))


    def test_compressResponsesFalse(self):
        """
        L{server.server} with C{compressResponses=False} will not compress
        responses.
        """
        sre = SimpleResource()
        r = resource.Resource()
        r.putChild(b'', sre)
        site = server.server(r, compressResponses=False)

        serverProtocol = site.buildProtocol(None)
        clientProtocol = proto_helpers.AccumulatingProtocol()

        c, s, pump = iosim.connectedServerAndClient(lambda: serverProtocol,
                                                    lambda: clientProtocol)

        c.transport.write(b"GET / HTTP/1.0\r\nAccept-Encoding: gzip\r\n\r\n")
        pump.flush()

        data = clientProtocol.data.split(b'\r\n')
        self.assertTrue(b'HTTP/1.0 200 OK' in data)
        self.assertFalse(b'Content-Encoding: gzip' in data)
        body = clientProtocol.data.split(b'\r\n\r\n', 1)[1]
        self.assertEqual(b'correct', body)

    def test_h2(self):
        """
        L{server.server} with C{compressResponses=False} will not compress
        responses.
        """
        from twisted.internet.ssl import optionsForClientTLS
        from twisted.protocols.tls import TLSMemoryBIOFactory
        from twisted.internet.protocol import ClientFactory
        from twisted.test.iosim import connectedServerAndClient
        from twisted.test.test_sslverify import (
            certificatesForAuthorityAndServer)
        from twisted.web.test.test_http2 import (
            framesFromBytes, buildRequestBytes, FrameFactory)

        reactor = Clock()
        sre = SimpleResource()
        r = resource.Resource()
        r.putChild(b'', sre)
        site = server.server(r, compressResponses=False, reactor=reactor)

        authCert, serverCert = certificatesForAuthorityAndServer()
        clientInnerF = ClientFactory.forProtocol(
            lambda: proto_helpers.AccumulatingProtocol())
        clientInnerF.protocolConnectionMade = None

        clientF = TLSMemoryBIOFactory(
            optionsForClientTLS(u"example.com", trustRoot=authCert,
                                acceptableProtocols=[b'h2']),
            isClient=True, wrappedFactory=clientInnerF
        )
        serverF = TLSMemoryBIOFactory(
            serverCert.options(), isClient=False,
            wrappedFactory=site
        )

        c, s, pump = connectedServerAndClient(
            lambda: serverF.buildProtocol(None),
            lambda: clientF.buildProtocol(None),
            greet=False,
        )
        c.transport.reactor = reactor
        s.transport.reactor = reactor
        pump.flush()

        frameFactory = FrameFactory()
        toWrite = frameFactory.clientConnectionPreface()
        toWrite += buildRequestBytes(
            [(b':method', b'GET'),
             (b':authority', b'localhost'),
             (b':path', b'/'),
             (b':scheme', b'https'),
             (b'user-agent', b'twisted-test-code')], [], frameFactory)

        c.wrappedProtocol.transport.write(toWrite)
        pump.flush()

        while reactor.calls:
            reactor.advance(1)
            pump.flush()

        dat = c.wrappedProtocol.data
        frames = framesFromBytes(dat)
        self.assertEqual(len(frames), 4)
        self.assertEqual(frames[2].data, b'correct')


    if not H2_ENABLED:
        test_h2.skip = "HTTP/2 is not enabled."


    def test_session(self):
        """
        Existing C{site.makeSession} and C{site.getSession} functions work.
        """
        site = server.server(None)
        p = site.buildProtocol(None)
        session = p.site.makeSession()
        otherSession = p.site.getSession(session.uid)
        self.assertIs(session, otherSession)
