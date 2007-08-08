# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for twisted.words.protocols.jabber.server
"""

from twisted.trial import unittest
from twisted.words.protocols.jabber import error, server, xmlstream

from twisted.test.proto_helpers import StringTransport


DIALBACK_NS = "jabber:server:dialback"

class GenerateKeyTest(unittest.TestCase):
    """
    Tests for generateKey.
    """

    def testBasic(self):
        secret = "s3cr3tf0rd14lb4ck"
        receiving = "example.net"
        originating = "example.com"
        id = "D60000229F"

        key = server.generateKey(secret, receiving, originating, id)

        self.assertEqual(key,
            '008c689ff366b50c63d69a3e2d2c0e0e1f8404b0118eb688a0102c87cb691bdc')

class DialbackListenTest(unittest.TestCase):
    """
    Tests for XMPPServerListenAuthenticator.
    """

    receiving = "example.org"
    originating = "example.net"
    id_ = "2093845023948"
    secret = "not-telling"

    def setUp(self):
        self.output = []
        self.authenticator = server.XMPPServerListenAuthenticator(
                        self.receiving, self.secret)
        self.xmlstream = xmlstream.XmlStream(self.authenticator)
        self.xmlstream.send = self.output.append
        self.xmlstream.transport = StringTransport()

    def test_attributes(self):
        """
        Test attributes of authenticator and stream objects.
        """
        self.assertEquals(self.secret, self.authenticator.secret)
        self.assertEquals(self.receiving, self.authenticator.domain)
        self.assertEquals(self.xmlstream.initiating, False)

    def test_streamRootElement(self):
        """
        Test stream error on wrong stream namespace.
        """
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived(
            "<stream:stream xmlns:stream='badns' "
                           "xmlns:db='jabber:server:dialback' "
                           "xmlns='jabber:server' "
                           "to='example.org'>")

        self.assertEquals(3, len(self.output))
        exc = error.exceptionFromStreamError(self.output[1])
        self.assertEquals('invalid-namespace', exc.condition)

    def test_streamDefaultNamespace(self):
        """
        Test stream error on missing dialback namespace.
        """
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived(
            "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
                           "xmlns:db='jabber:server:dialback' "
                           "xmlns='badns' "
                           "to='example.org'>")

        self.assertEquals(3, len(self.output))
        exc = error.exceptionFromStreamError(self.output[1])
        self.assertEquals('invalid-namespace', exc.condition)

    def test_streamNoDialbackNamespace(self):
        """
        Test stream error on missing dialback namespace.
        """
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived(
            "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
                           "xmlns='jabber:server' "
                           "to='example.org'>")

        self.assertEquals(3, len(self.output))
        exc = error.exceptionFromStreamError(self.output[1])
        self.assertEquals('invalid-namespace', exc.condition)

    def test_streamBadDialbackNamespace(self):
        """
        Test stream error on missing dialback namespace.
        """
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived(
            "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
                           "xmlns:db='badns' "
                           "xmlns='jabber:server' "
                           "to='example.org'>")

        self.assertEquals(3, len(self.output))
        exc = error.exceptionFromStreamError(self.output[1])
        self.assertEquals('invalid-namespace', exc.condition)

    def test_streamToUnknownHost(self):
        """
        Test stream error on stream's to attribute having unknown host.
        """
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived(
            "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
                           "xmlns:db='jabber:server:dialback' "
                           "xmlns='jabber:server' "
                           "to='badhost'>")

        self.assertEquals(3, len(self.output))
        exc = error.exceptionFromStreamError(self.output[1])
        self.assertEquals('host-unknown', exc.condition)
