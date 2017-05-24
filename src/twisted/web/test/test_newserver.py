# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import zlib

from io import BytesIO

from twisted.logger import Logger, LogPublisher
from twisted.web import server, resource
from twisted.internet.task import Clock
from twisted.test import iosim, proto_helpers
from twisted.trial.unittest import SynchronousTestCase
from twisted.web.test.test_web import SimpleResource
from twisted.web.http import H2_ENABLED
from twisted.internet.address import IPv4Address


class ServerTests(SynchronousTestCase):
    """
    Tests for L{twisted.web.server.makeServer}.
    """

    def test_noAcceptEncoding(self):
        """
        L{server.makeServer}s with C{compressResponses=True} will not compress
        responses with no C{Accept-Encoding} header.
        """
        reactor = Clock()
        sre = SimpleResource()
        r = resource.Resource()
        r.putChild(b'', sre)
        site = server.makeServer(r, compressResponses=True, reactor=reactor)

        serverProtocol = site.buildProtocol(None)
        clientProtocol = proto_helpers.AccumulatingProtocol()

        c, s, pump = iosim.connectedServerAndClient(lambda: serverProtocol,
                                                    lambda: clientProtocol)

        c.transport.write(b"GET / HTTP/1.1\r\n\r\n")
        pump.flush()

        data = clientProtocol.data.split(b'\r\n')
        self.assertTrue(b'HTTP/1.1 200 OK' in data)
        self.assertFalse(b'Content-Encoding' in data)


    def test_logger(self):
        """
        L{server.makeServer} with C{logger} will set the logger.
        """
        reactor = Clock()
        msg = []
        logger = Logger(observer=msg.append)
        sre = SimpleResource()
        r = resource.Resource()
        r.putChild(b'', sre)
        site = server.makeServer(r, logger=logger, reactor=reactor)

        serverProtocol = site.buildProtocol(None)
        clientProtocol = proto_helpers.AccumulatingProtocol()

        c, s, pump = iosim.connectedServerAndClient(lambda: serverProtocol,
                                                    lambda: clientProtocol)

        c.transport.write(b"GET / HTTP/1.1\r\n\r\n")
        pump.flush()

        data = clientProtocol.data.split(b'\r\n')
        self.assertTrue(b'HTTP/1.1 200 OK' in data)
        self.assertFalse(b'Content-Encoding' in data)
        self.assertEqual(len(msg), 1)
        self.assertEqual(msg[0]["uri"], "/")


    def test_gzip(self):
        """
        L{server.makeServer} with C{compressResponses=True} will compress eligible
        responses.
        """
        reactor = Clock()
        sre = SimpleResource()
        r = resource.Resource()
        r.putChild(b'', sre)
        site = server.makeServer(r, compressResponses=True, reactor=reactor)

        serverProtocol = site.buildProtocol(None)
        clientProtocol = proto_helpers.AccumulatingProtocol()

        c, s, pump = iosim.connectedServerAndClient(lambda: serverProtocol,
                                                    lambda: clientProtocol)

        c.transport.write(b"GET / HTTP/1.0\r\n"
                          b"X-Forwarded-For: 4.3.2.1\r\n"
                          b"Accept-Encoding: gzip\r\n\r\n")
        pump.flush()

        data = clientProtocol.data.split(b'\r\n')
        self.assertTrue(b'HTTP/1.0 200 OK' in data)
        self.assertTrue(b'Content-Encoding: gzip' in data)
        body = clientProtocol.data.split(b'\r\n\r\n', 1)[1]
        self.assertEqual(b'correct',
                         zlib.decompress(body, 16 + zlib.MAX_WBITS))


    def test_compressResponsesFalse(self):
        """
        L{server.makeServer} with C{compressResponses=False} will not compress
        responses.
        """
        reactor = Clock()
        sre = SimpleResource()
        r = resource.Resource()
        r.putChild(b'', sre)
        site = server.makeServer(r, compressResponses=False, reactor=reactor)

        serverProtocol = site.buildProtocol(None)
        clientProtocol = proto_helpers.AccumulatingProtocol()

        c, s, pump = iosim.connectedServerAndClient(lambda: serverProtocol,
                                                    lambda: clientProtocol)

        c.transport.write(b"GET / HTTP/1.1\r\nAccept-Encoding: gzip\r\n\r\n")
        pump.flush()

        data = clientProtocol.data.split(b'\r\n')
        self.assertTrue(b'HTTP/1.1 200 OK' in data)
        self.assertFalse(b'Content-Encoding: gzip' in data)
        body = clientProtocol.data.split(b'\r\n\r\n', 1)[1]
        self.assertEqual(b'correct', body)

    def test_XForwardedFor(self):
        """
        The IP returned by C{Request.getClientIP} on a C{Request} made by a
        C{Server} that was made by L{makeServer} with
        C{getTrustedReverseProxyIPs()} containing an IP that is a trusted
        reverse proxy will be the contents of the C{X-Forwarded-For} header.
        """
        reactor = Clock()
        r = resource.Resource()

        class IPSayingResource(resource.Resource):
            def render(self, request):
                return str(request.getClientIP()).encode('utf8')

        r.putChild(b'', IPSayingResource())
        site = server.makeServer(r, reactor=reactor,
                                 trustedReverseProxyIPs=['1.2.3.4'])

        serverProtocol = site.buildProtocol(None)
        clientProtocol = proto_helpers.AccumulatingProtocol()

        c, s, pump = iosim.connectedServerAndClient(lambda: serverProtocol,
                                                    lambda: clientProtocol)
        s._channel.getPeer = lambda: IPv4Address('TCP', '1.2.3.4', 12345)

        c.transport.write(b"GET / HTTP/1.0\r\n"
                          b"X-Forwarded-For: 4.3.2.1\r\n\r\n")
        pump.flush()

        data = clientProtocol.data.split(b'\r\n')
        self.assertTrue(b'HTTP/1.0 200 OK' in data)
        body = clientProtocol.data.split(b'\r\n\r\n', 1)[1]
        self.assertEqual(body, b"4.3.2.1")


    def test_h2(self):
        """
        L{server.makeServer} with C{compressResponses=False} will not compress
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
        site = server.makeServer(r, compressResponses=False, reactor=reactor)

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
        reactor = Clock()
        site = server.makeServer(None, reactor=reactor)
        p = site.buildProtocol(None)
        session = p.site.makeSession()
        otherSession = p.site.getSession(session.uid)
        self.assertIs(session, otherSession)


class ServerLoggingTests(SynchronousTestCase):
    """
    Tests for L{twisted.web._newserver.makeCombinedLogFormatFileForServer}.
    """

    def test_globalPublisher(self):
        """
        Passing no explicit logger and no explicit C{logPublisher} will make it
        use the global log publisher.
        """
        reactor = Clock()
        reactor.advance(1234567890)
        r = resource.Resource()
        r.putChild(b'', SimpleResource())
        site = server.makeServer(r, reactor=reactor)

        logFile = BytesIO()
        logger = server.makeCombinedLogFormatFileForServer(site, logFile)

        serverProtocol = site.buildProtocol(None)
        clientProtocol = proto_helpers.AccumulatingProtocol()

        c, s, pump = iosim.connectedServerAndClient(lambda: serverProtocol,
                                                    lambda: clientProtocol)
        s._channel.getPeer = lambda: IPv4Address('TCP', '1.2.3.4', 12345)

        c.transport.write(b"GET / HTTP/1.1\r\n\r\n")
        pump.flush()

        data = clientProtocol.data.split(b'\r\n')
        self.assertTrue(b'HTTP/1.1 200 OK' in data)
        self.assertFalse(b'Content-Encoding' in data)

        # Log something else on the system, it shouldn't show up in the log
        myLogger = Logger()
        myLogger.info("hello!")

        # Reach in and log on the logger in the server, it shouldn't show up
        site._logger.info("hellllo!")

        logLines = logFile.getvalue().strip().split(b"\n")
        self.assertEqual(len(logLines), 1)
        self.assertEqual(
            logLines[0],
            # Client IP
            b'1.2.3.4 '
            # Some blanks we never fill in
            b'- - '
            # The current time (circa 1234567890)
            b'[13/Feb/2009:23:31:30 +0000] '
            # Method, URI, version
            b'"GET / HTTP/1.1" '
            # Response code
            b'200 '
            # Response length
            b'7 '
            # Value of the "Referer" header.  Probably incorrectly quoted.
            b'"-" '
            # Value pf the "User-Agent" header.  Probably incorrectly quoted.
            b'"-"')

        # Unsubscribe, we ought to not get anything else.
        logger()
        clientProtocol.data = b''

        c.transport.write(b"GET / HTTP/1.1\r\n\r\n")
        pump.flush()

        data = clientProtocol.data.split(b'\r\n')
        self.assertTrue(b'HTTP/1.1 200 OK' in data)
        self.assertFalse(b'Content-Encoding' in data)
        logLines = logFile.getvalue().strip().split(b"\n")
        self.assertEqual(len(logLines), 1)


    def test_explicitPublisher(self):
        """
        Passing an explicit logger and publisher to L{makeServer} and
        L{makeCombinedLogFormatFileForServer}.
        """
        observer = LogPublisher()
        logger = Logger(observer=observer)

        reactor = Clock()
        reactor.advance(1234567890)
        r = resource.Resource()
        r.putChild(b'', SimpleResource())
        site = server.makeServer(r, reactor=reactor, logger=logger)

        logFile = BytesIO()
        logger = server.makeCombinedLogFormatFileForServer(
            site, logFile, logPublisher=observer)

        serverProtocol = site.buildProtocol(None)
        clientProtocol = proto_helpers.AccumulatingProtocol()

        c, s, pump = iosim.connectedServerAndClient(lambda: serverProtocol,
                                                    lambda: clientProtocol)
        s._channel.getPeer = lambda: IPv4Address('TCP', '1.2.3.4', 12345)

        c.transport.write(b"GET / HTTP/1.1\r\n\r\n")
        pump.flush()

        data = clientProtocol.data.split(b'\r\n')
        self.assertTrue(b'HTTP/1.1 200 OK' in data)
        self.assertFalse(b'Content-Encoding' in data)

        # Log something else on the system, it shouldn't show up in the log
        myLogger = Logger()
        myLogger.info("hello!")

        # Reach in and log on the logger in the server, it shouldn't show up
        site._logger.info("hellllo!")

        logLines = logFile.getvalue().strip().split(b"\n")
        self.assertEqual(len(logLines), 1)
        self.assertEqual(
            logLines[0],
            # Client IP
            b'1.2.3.4 '
            # Some blanks we never fill in
            b'- - '
            # The current time (circa 1234567890)
            b'[13/Feb/2009:23:31:30 +0000] '
            # Method, URI, version
            b'"GET / HTTP/1.1" '
            # Response code
            b'200 '
            # Response length
            b'7 '
            # Value of the "Referer" header.  Probably incorrectly quoted.
            b'"-" '
            # Value pf the "User-Agent" header.  Probably incorrectly quoted.
            b'"-"')

        # Unsubscribe, we ought to not get anything else.
        logger()
        clientProtocol.data = b''

        c.transport.write(b"GET / HTTP/1.1\r\n\r\n")
        pump.flush()

        data = clientProtocol.data.split(b'\r\n')
        self.assertTrue(b'HTTP/1.1 200 OK' in data)
        self.assertFalse(b'Content-Encoding' in data)
        logLines = logFile.getvalue().strip().split(b"\n")
        self.assertEqual(len(logLines), 1)
