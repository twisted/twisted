# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.words.protocols.jabber.error}.
"""

from twisted.trial import unittest

from twisted.words.protocols.jabber import error
from twisted.words.xish import domish

NS_XML = 'http://www.w3.org/XML/1998/namespace'
NS_STREAMS = 'http://etherx.jabber.org/streams'
NS_XMPP_STREAMS = 'urn:ietf:params:xml:ns:xmpp-streams'
NS_XMPP_STANZAS = 'urn:ietf:params:xml:ns:xmpp-stanzas'

class BaseErrorTest(unittest.TestCase):

    def testGetElementPlain(self):
        e = error.BaseError('feature-not-implemented')
        element = e.getElement()
        self.assertIdentical(element.uri, None)
        self.assertEquals(len(element.children), 1)

    def testGetElementText(self):
        e = error.BaseError('feature-not-implemented', 'text')
        element = e.getElement()
        self.assertEquals(len(element.children), 2)
        self.assertEquals(unicode(element.text), 'text')
        self.assertEquals(element.text.getAttribute((NS_XML, 'lang')), None)

    def testGetElementTextLang(self):
        e = error.BaseError('feature-not-implemented', 'text', 'en_US')
        element = e.getElement()
        self.assertEquals(len(element.children), 2)
        self.assertEquals(unicode(element.text), 'text')
        self.assertEquals(element.text[(NS_XML, 'lang')], 'en_US')

    def testGetElementAppCondition(self):
        ac = domish.Element(('testns', 'myerror'))
        e = error.BaseError('feature-not-implemented', appCondition=ac)
        element = e.getElement()
        self.assertEquals(len(element.children), 2)
        self.assertEquals(element.myerror, ac)

class StreamErrorTest(unittest.TestCase):

    def testGetElementPlain(self):
        e = error.StreamError('feature-not-implemented')
        element = e.getElement()
        self.assertEquals(element.uri, NS_STREAMS)

    def test_getElementConditionNamespace(self):
        """
        Test that the error condition element has the correct namespace.
        """
        e = error.StreamError('feature-not-implemented')
        element = e.getElement()
        self.assertEquals(NS_XMPP_STREAMS, getattr(element, 'feature-not-implemented').uri)

    def test_getElementTextNamespace(self):
        """
        Test that the error text element has the correct namespace.
        """
        e = error.StreamError('feature-not-implemented', 'text')
        element = e.getElement()
        self.assertEquals(NS_XMPP_STREAMS, element.text.uri)

class StanzaErrorTest(unittest.TestCase):

    def test_getElementPlain(self):
        e = error.StanzaError('feature-not-implemented')
        element = e.getElement()
        self.assertEquals(element.uri, None)
        self.assertEquals(element['type'], 'cancel')
        self.assertEquals(element['code'], '501')

    def test_getElementType(self):
        e = error.StanzaError('feature-not-implemented', 'auth')
        element = e.getElement()
        self.assertEquals(element.uri, None)
        self.assertEquals(element['type'], 'auth')
        self.assertEquals(element['code'], '501')

    def test_getElementConditionNamespace(self):
        """
        Test that the error condition element has the correct namespace.
        """
        e = error.StanzaError('feature-not-implemented')
        element = e.getElement()
        self.assertEquals(NS_XMPP_STANZAS, getattr(element, 'feature-not-implemented').uri)

    def test_getElementTextNamespace(self):
        """
        Test that the error text element has the correct namespace.
        """
        e = error.StanzaError('feature-not-implemented', text='text')
        element = e.getElement()
        self.assertEquals(NS_XMPP_STANZAS, element.text.uri)

    def test_toResponse(self):
        """
        Test an error response is generated from a stanza.

        The addressing on the (new) response stanza should be reversed, an
        error child (with proper properties) added and the type set to
        C{'error'}.
        """
        stanza = domish.Element(('jabber:client', 'message'))
        stanza['type'] = 'chat'
        stanza['to'] = 'user1@example.com'
        stanza['from'] = 'user2@example.com/resource'
        e = error.StanzaError('service-unavailable')
        response = e.toResponse(stanza)
        self.assertNotIdentical(response, stanza)
        self.assertEqual(response['from'], 'user1@example.com')
        self.assertEqual(response['to'], 'user2@example.com/resource')
        self.assertEqual(response['type'], 'error')
        self.assertEqual(response.error.children[0].name,
                         'service-unavailable')
        self.assertEqual(response.error['type'], 'cancel')
        self.assertNotEqual(stanza.children, response.children)

class ParseErrorTest(unittest.TestCase):

    def setUp(self):
        self.error = domish.Element((None, 'error'))

    def testEmpty(self):
        result = error._parseError(self.error)
        self.assertEqual({'condition': None,
                          'text': None,
                          'textLang': None,
                          'appCondition': None}, result)

    def testCondition(self):
        self.error.addElement((NS_XMPP_STANZAS, 'bad-request'))
        result = error._parseError(self.error)
        self.assertEqual('bad-request', result['condition'])

    def testText(self):
        text = self.error.addElement((NS_XMPP_STANZAS, 'text'))
        text.addContent('test')
        result = error._parseError(self.error)
        self.assertEqual('test', result['text'])
        self.assertEqual(None, result['textLang'])

    def testTextLang(self):
        text = self.error.addElement((NS_XMPP_STANZAS, 'text'))
        text[NS_XML, 'lang'] = 'en_US'
        text.addContent('test')
        result = error._parseError(self.error)
        self.assertEqual('en_US', result['textLang'])

    def testTextLangInherited(self):
        text = self.error.addElement((NS_XMPP_STANZAS, 'text'))
        self.error[NS_XML, 'lang'] = 'en_US'
        text.addContent('test')
        result = error._parseError(self.error)
        self.assertEqual('en_US', result['textLang'])
    testTextLangInherited.todo = "xml:lang inheritance not implemented"

    def testAppCondition(self):
        condition = self.error.addElement(('testns', 'condition'))
        result = error._parseError(self.error)
        self.assertEqual(condition, result['appCondition'])

    def testMultipleAppConditions(self):
        condition = self.error.addElement(('testns', 'condition'))
        condition2 = self.error.addElement(('testns', 'condition2'))
        result = error._parseError(self.error)
        self.assertEqual(condition2, result['appCondition'])

class ExceptionFromStanzaTest(unittest.TestCase):

    def testBasic(self):
        """
        Test basic operations of exceptionFromStanza.

        Given a realistic stanza, check if a sane exception is returned.

        Using this stanza::

          <iq type='error'
              from='pubsub.shakespeare.lit'
              to='francisco@denmark.lit/barracks'
              id='subscriptions1'>
            <pubsub xmlns='http://jabber.org/protocol/pubsub'>
              <subscriptions/>
            </pubsub>
            <error type='cancel'>
              <feature-not-implemented
                xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>
              <unsupported xmlns='http://jabber.org/protocol/pubsub#errors'
                           feature='retrieve-subscriptions'/>
            </error>
          </iq>
        """

        stanza = domish.Element((None, 'stanza'))
        p = stanza.addElement(('http://jabber.org/protocol/pubsub', 'pubsub'))
        p.addElement('subscriptions')
        e = stanza.addElement('error')
        e['type'] = 'cancel'
        e.addElement((NS_XMPP_STANZAS, 'feature-not-implemented'))
        uc = e.addElement(('http://jabber.org/protocol/pubsub#errors',
                           'unsupported'))
        uc['feature'] = 'retrieve-subscriptions'

        result = error.exceptionFromStanza(stanza)
        self.assert_(isinstance(result, error.StanzaError))
        self.assertEquals('feature-not-implemented', result.condition)
        self.assertEquals('cancel', result.type)
        self.assertEquals(uc, result.appCondition)
        self.assertEquals([p], result.children)

    def testLegacy(self):
        """
        Test legacy operations of exceptionFromStanza.

        Given a realistic stanza with only legacy (pre-XMPP) error information,
        check if a sane exception is returned.

        Using this stanza::

          <message type='error'
                   to='piers@pipetree.com/Home'
                   from='qmacro@jaber.org'>
            <body>Are you there?</body>
            <error code='502'>Unable to resolve hostname.</error>
          </message>
        """
        stanza = domish.Element((None, 'stanza'))
        p = stanza.addElement('body', content='Are you there?')
        e = stanza.addElement('error', content='Unable to resolve hostname.')
        e['code'] = '502'

        result = error.exceptionFromStanza(stanza)
        self.assert_(isinstance(result, error.StanzaError))
        self.assertEquals('service-unavailable', result.condition)
        self.assertEquals('wait', result.type)
        self.assertEquals('Unable to resolve hostname.', result.text)
        self.assertEquals([p], result.children)
