from twisted.trial import unittest

from twisted.words.protocols.jabber import sasl_mechanisms

class PlainTest(unittest.TestCase):
    def testGetInitialResponse(self):
        """
        Test the initial response.
        """
        m = sasl_mechanisms.Plain(None, 'test', 'secret')
        self.assertEquals(m.getInitialResponse(), '\x00test\x00secret')

class DigestMD5Test(unittest.TestCase):
    def setUp(self):
        self.mechanism = sasl_mechanisms.DigestMD5('xmpp', 'example.org', None,
                                                   'test', 'secret')


    def testGetInitialResponse(self):
        """
        Test that no initial response is generated.
        """
        self.assertIdentical(self.mechanism.getInitialResponse(), None)

    def testGetResponse(self):
        """
        Partially test challenge response.

        Does not actually test the response-value, yet.
        """

        challenge = 'realm="localhost",nonce="1234",qop="auth",charset=utf-8,algorithm=md5-sess'
        directives = self.mechanism._parse(self.mechanism.getResponse(challenge))
        self.assertEqual(directives['username'], 'test')
        self.assertEqual(directives['nonce'], '1234')
        self.assertEqual(directives['nc'], '00000001')
        self.assertEqual(directives['qop'], 'auth')
        self.assertEqual(directives['charset'], 'utf-8')
        self.assertEqual(directives['digest-uri'], 'xmpp/example.org')
        self.assertEqual(directives['realm'], 'localhost')

    def testGetResponseNoRealm(self):
        """
        Test that we accept challenges without realm.

        The realm should default to the host part of the JID.
        """

        challenge = 'nonce="1234",qop="auth",charset=utf-8,algorithm=md5-sess'
        directives = self.mechanism._parse(self.mechanism.getResponse(challenge))
        self.assertEqual(directives['realm'], 'example.org')
