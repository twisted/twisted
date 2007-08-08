# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.words.protocols.jabber.client}
"""

import sha
from twisted.trial import unittest
from twisted.words.protocols.jabber import client, error, jid, xmlstream
from twisted.words.protocols.jabber.sasl import SASLInitiatingInitializer

class CheckVersionInitializerTest(unittest.TestCase):
    def setUp(self):
        a = xmlstream.Authenticator()
        xs = xmlstream.XmlStream(a)
        self.init = client.CheckVersionInitializer(xs)

    def testSupported(self):
        """
        Test supported version number 1.0
        """
        self.init.xmlstream.version = (1, 0)
        self.init.initialize()

    def testNotSupported(self):
        """
        Test unsupported version number 0.0, and check exception.
        """
        self.init.xmlstream.version = (0, 0)
        exc = self.assertRaises(error.StreamError, self.init.initialize)
        self.assertEquals('unsupported-version', exc.condition)


class InitiatingInitializerHarness(object):
    def setUp(self):
        self.output = []
        self.authenticator = xmlstream.ConnectAuthenticator('example.org')
        self.xmlstream = xmlstream.XmlStream(self.authenticator)
        self.xmlstream.send = self.output.append
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived("<stream:stream xmlns='jabber:client' "
                        "xmlns:stream='http://etherx.jabber.org/streams' "
                        "from='example.com' id='12345' version='1.0'>")


class IQAuthInitializerTest(InitiatingInitializerHarness, unittest.TestCase):
    def setUp(self):
        super(IQAuthInitializerTest, self).setUp()
        self.init = client.IQAuthInitializer(self.xmlstream)
        self.authenticator.jid = jid.JID('user@example.com/resource')
        self.authenticator.password = 'secret'

    def testBasic(self):
        """
        Test basic operations with plain text authentication.

        Set up a stream, and act as if authentication succeeds.
        """
        d = self.init.initialize()

        # The initializer should have sent query to find out auth methods.

        # Examine query.
        iq = self.output[-1]
        self.assertEquals('iq', iq.name)
        self.assertEquals('get', iq['type'])
        self.assertEquals(('jabber:iq:auth', 'query'),
                          (iq.children[0].uri, iq.children[0].name))

        # Send server response
        iq['type'] = 'result'
        iq.query.addElement('username')
        iq.query.addElement('password')
        iq.query.addElement('resource')
        self.xmlstream.dataReceived(iq.toXml())

        # Upon receiving the response, the initializer can start authentication

        iq = self.output[-1]
        self.assertEquals('iq', iq.name)
        self.assertEquals('set', iq['type'])
        self.assertEquals(('jabber:iq:auth', 'query'),
                          (iq.children[0].uri, iq.children[0].name))
        self.assertEquals('user', unicode(iq.query.username))
        self.assertEquals('secret', unicode(iq.query.password))
        self.assertEquals('resource', unicode(iq.query.resource))

        # Send server response
        self.xmlstream.dataReceived("<iq type='result' id='%s'/>" % iq['id'])
        return d

    def testDigest(self):
        """
        Test digest authentication.

        Set up a stream, and act as if authentication succeeds.
        """
        d = self.init.initialize()

        # The initializer should have sent query to find out auth methods.

        iq = self.output[-1]

        # Send server response
        iq['type'] = 'result'
        iq.query.addElement('username')
        iq.query.addElement('digest')
        iq.query.addElement('resource')
        self.xmlstream.dataReceived(iq.toXml())

        # Upon receiving the response, the initializer can start authentication

        iq = self.output[-1]
        self.assertEquals('iq', iq.name)
        self.assertEquals('set', iq['type'])
        self.assertEquals(('jabber:iq:auth', 'query'),
                          (iq.children[0].uri, iq.children[0].name))
        self.assertEquals('user', unicode(iq.query.username))
        self.assertEquals(sha.new('12345secret').hexdigest(),
                          unicode(iq.query.digest))
        self.assertEquals('resource', unicode(iq.query.resource))

        # Send server response
        self.xmlstream.dataReceived("<iq type='result' id='%s'/>" % iq['id'])
        return d

    def testFailRequestFields(self):
        """
        Test failure of request for fields.
        """
        d = self.init.initialize()
        iq = self.output[-1]
        response = error.StanzaError('not-authorized').toResponse(iq)
        self.xmlstream.dataReceived(response.toXml())
        self.assertFailure(d, error.StanzaError)
        return d

    def testFailAuth(self):
        """
        Test failure of request for fields.
        """
        d = self.init.initialize()
        iq = self.output[-1]
        iq['type'] = 'result'
        iq.query.addElement('username')
        iq.query.addElement('password')
        iq.query.addElement('resource')
        self.xmlstream.dataReceived(iq.toXml())
        iq = self.output[-1]
        response = error.StanzaError('not-authorized').toResponse(iq)
        self.xmlstream.dataReceived(response.toXml())
        self.assertFailure(d, error.StanzaError)
        return d


class BindInitializerTest(InitiatingInitializerHarness, unittest.TestCase):
    def setUp(self):
        super(BindInitializerTest, self).setUp()
        self.init = client.BindInitializer(self.xmlstream)
        self.authenticator.jid = jid.JID('user@example.com/resource')

    def testBasic(self):
        """
        Test basic operations.

        Set up a stream, and act as if resource binding succeeds.
        """
        def cb(result):
            self.assertEquals(jid.JID('user@example.com/other resource'),
                              self.authenticator.jid)

        d = self.init.start().addCallback(cb)
        iq = self.output[-1]
        self.assertEquals('iq', iq.name)
        self.assertEquals('set', iq['type'])
        self.assertEquals(('urn:ietf:params:xml:ns:xmpp-bind', 'bind'),
                          (iq.children[0].uri, iq.children[0].name))
        iq['type'] = 'result'
        iq.bind.children = []
        iq.bind.addElement('jid', content='user@example.com/other resource')
        self.xmlstream.dataReceived(iq.toXml())
        return d

    def testFailure(self):
        """
        Test basic operations.

        Set up a stream, and act as if resource binding fails.
        """
        def cb(result):
            self.assertEquals(jid.JID('user@example.com/resource'),
                              self.authenticator.jid)

        d = self.init.start()
        id = self.output[-1]['id']
        self.xmlstream.dataReceived("<iq type='error' id='%s'/>" % id)
        self.assertFailure(d, error.StanzaError)
        return d


class SessionInitializerTest(InitiatingInitializerHarness, unittest.TestCase):

    def setUp(self):
        super(SessionInitializerTest, self).setUp()
        self.init = client.SessionInitializer(self.xmlstream)

    def testSuccess(self):
        """
        Test basic operations.

        Set up a stream, and act as if resource binding succeeds.
        """
        d = self.init.start()
        iq = self.output[-1]
        self.assertEquals('iq', iq.name)
        self.assertEquals('set', iq['type'])
        self.assertEquals(('urn:ietf:params:xml:ns:xmpp-session', 'session'),
                          (iq.children[0].uri, iq.children[0].name))
        self.xmlstream.dataReceived("<iq type='result' id='%s'/>" % iq['id'])
        return d

    def testFailure(self):
        """
        Test basic operations.

        Set up a stream, and act as if session establishment succeeds.
        """
        d = self.init.start()
        id = self.output[-1]['id']
        self.xmlstream.dataReceived("<iq type='error' id='%s'/>" % id)
        self.assertFailure(d, error.StanzaError)
        return d


class XMPPAuthenticatorTest(unittest.TestCase):
    """
    Test for both XMPPAuthenticator and XMPPClientFactory.
    """
    def testBasic(self):
        """
        Test basic operations.

        Setup an XMPPClientFactory, which sets up an XMPPAuthenticator, and let
        it produce a protocol instance. Then inspect the instance variables of
        the authenticator and XML stream objects.
        """
        self.client_jid = jid.JID('user@example.com/resource')

        # Get an XmlStream instance. Note that it gets initialized with the
        # XMPPAuthenticator (that has its associateWithXmlStream called) that
        # is in turn initialized with the arguments to the factory.
        xs = client.XMPPClientFactory(self.client_jid,
                                      'secret').buildProtocol(None)

        # test authenticator's instance variables
        self.assertEqual('example.com', xs.authenticator.otherHost)
        self.assertEqual(self.client_jid, xs.authenticator.jid)
        self.assertEqual('secret', xs.authenticator.password)

        # test list of initializers
        version, tls, sasl, bind, session = xs.initializers

        self.assert_(isinstance(tls, xmlstream.TLSInitiatingInitializer))
        self.assert_(isinstance(sasl, SASLInitiatingInitializer))
        self.assert_(isinstance(bind, client.BindInitializer))
        self.assert_(isinstance(session, client.SessionInitializer))

        self.assertFalse(tls.required)
        self.assertTrue(sasl.required)
        self.assertFalse(bind.required)
        self.assertFalse(session.required)
