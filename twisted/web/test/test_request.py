# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{twisted.web.iweb.IRequest}.
"""

from zope.interface.verify import verifyObject

from twisted.trial.unittest import TestCase
from twisted.web import iweb, server

from twisted.web.test.requesthelper import DummyChannel, DummyRequest


class RequestTestsMixin(object):
    def test_interface(self):
        """
        L{server.Request} instances provide L{iweb.IRequest}.
        """
        self.assertTrue(verifyObject(iweb.IRequest, self.makeRequest()))


    def test_prePathURLSimple(self):
        """
        L{IRequest.prePathURL} returns a L{bytes} instance giving the request
        location as a URL string.
        """
        request = self.makeRequest()
        request.gotLength(0)
        request.requestReceived(b'GET', b'/foo/bar', b'HTTP/1.0')
        request.setHost(b'example.com', 80)
        self.assertEqual(request.prePathURL(), b'http://example.com/foo/bar')


    def test_prePathURLNonDefault(self):
        """
        """
        d = DummyChannel()
        d.transport.port = 81
        request = server.Request(d, 1)
        request.setHost(b'example.com', 81)
        request.gotLength(0)
        request.requestReceived(b'GET', b'/foo/bar', b'HTTP/1.0')
        self.assertEqual(request.prePathURL(), b'http://example.com:81/foo/bar')

    def testPrePathURLSSLPort(self):
        d = DummyChannel()
        d.transport.port = 443
        request = server.Request(d, 1)
        request.setHost(b'example.com', 443)
        request.gotLength(0)
        request.requestReceived(b'GET', b'/foo/bar', b'HTTP/1.0')
        self.assertEqual(request.prePathURL(), b'http://example.com:443/foo/bar')

    def testPrePathURLSSLPortAndSSL(self):
        d = DummyChannel()
        d.transport = DummyChannel.SSL()
        d.transport.port = 443
        request = server.Request(d, 1)
        request.setHost(b'example.com', 443)
        request.gotLength(0)
        request.requestReceived(b'GET', b'/foo/bar', b'HTTP/1.0')
        self.assertEqual(request.prePathURL(), b'https://example.com/foo/bar')

    def testPrePathURLHTTPPortAndSSL(self):
        d = DummyChannel()
        d.transport = DummyChannel.SSL()
        d.transport.port = 80
        request = server.Request(d, 1)
        request.setHost(b'example.com', 80)
        request.gotLength(0)
        request.requestReceived(b'GET', b'/foo/bar', b'HTTP/1.0')
        self.assertEqual(request.prePathURL(), b'https://example.com:80/foo/bar')

    def testPrePathURLSSLNonDefault(self):
        d = DummyChannel()
        d.transport = DummyChannel.SSL()
        d.transport.port = 81
        request = server.Request(d, 1)
        request.setHost(b'example.com', 81)
        request.gotLength(0)
        request.requestReceived(b'GET', b'/foo/bar', b'HTTP/1.0')
        self.assertEqual(request.prePathURL(), b'https://example.com:81/foo/bar')

    def testPrePathURLSetSSLHost(self):
        d = DummyChannel()
        d.transport.port = 81
        request = server.Request(d, 1)
        request.setHost(b'foo.com', 81, 1)
        request.gotLength(0)
        request.requestReceived(b'GET', b'/foo/bar', b'HTTP/1.0')
        self.assertEqual(request.prePathURL(), b'https://foo.com:81/foo/bar')


    def test_prePathURLQuoting(self):
        """
        L{Request.prePathURL} quotes special characters in the URL segments to
        preserve the original meaning.
        """
        d = DummyChannel()
        request = server.Request(d, 1)
        request.setHost(b'example.com', 80)
        request.gotLength(0)
        request.requestReceived(b'GET', b'/foo%2Fbar', b'HTTP/1.0')
        self.assertEqual(request.prePathURL(), b'http://example.com/foo%2Fbar')



class MemoryRequestTests(TestCase, RequestTestsMixin):
    def makeRequest(self):
        return DummyRequest()



class RequestTests(TestCase, RequestTestsMixin):
    """
    Tests for the HTTP request class, L{server.Request}.
    """
    def makeRequest(self):
        return server.Request(DummyChannel(), True)


    def test_childLink(self):
        """
        L{twisted.web.server.Request.childLink} returns a link (relative to the
        request's current traversal location) to the given child..
        """
        request = server.Request(DummyChannel(), 1)
        request.gotLength(0)
        request.requestReceived(b'GET', b'/foo/bar', b'HTTP/1.0')
        self.assertEqual(request.childLink(b'baz'), b'bar/baz')
        request = server.Request(DummyChannel(), 1)
        request.gotLength(0)
        request.requestReceived(b'GET', b'/foo/bar/', b'HTTP/1.0')
        self.assertEqual(request.childLink(b'baz'), b'baz')

