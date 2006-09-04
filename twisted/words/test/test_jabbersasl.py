# Copyright (c) 2001-2006 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.internet import defer
from twisted.trial import unittest
from twisted.words.protocols.jabber import sasl, xmlstream
from twisted.words.xish import domish

class SASLInitiatingInitializerTest(unittest.TestCase):

    def testOnFailure(self):
        """
        Test that the SASL error condition is correctly extracted.
        """
        self.authenticator = xmlstream.Authenticator()
        self.xmlstream = xmlstream.XmlStream(self.authenticator)
        init = sasl.SASLInitiatingInitializer(self.xmlstream)
        failure = domish.Element(('urn:ietf:params:xml:ns:xmpp-sasl',
                                  'failure'))
        failure.addElement('not-authorized')
        init._deferred = defer.Deferred()
        init.onFailure(failure)
        self.assertFailure(init._deferred, sasl.SASLAuthError)
        init._deferred.addCallback(lambda e:
                                   self.assertEquals('not-authorized',
                                                     e.condition))
        return init._deferred
