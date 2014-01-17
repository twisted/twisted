# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.words.protocols.jabber.sasl_mechanisms}.
"""

from twisted.trial import unittest

from twisted.words.protocols.jabber import sasl_mechanisms

class PlainTest(unittest.TestCase):
    def test_getInitialResponse(self):
        """
        Test the initial response.
        """
        m = sasl_mechanisms.Plain(None, 'test', 'secret')
        self.assertEqual(m.getInitialResponse(), '\x00test\x00secret')



class AnonymousTest(unittest.TestCase):
    """
    Tests for L{twisted.words.protocols.jabber.sasl_mechanisms.Anonymous}.
    """
    def test_getInitialResponse(self):
        """
        Test the initial response to be empty.
        """
        m = sasl_mechanisms.Anonymous()
        self.assertEqual(m.getInitialResponse(), None)



class DigestMD5Test(unittest.TestCase):
    def setUp(self):
        self.mechanism = sasl_mechanisms.DigestMD5(
            u'xmpp', u'example.org', None, u'test', u'secret')


    def test_getInitialResponse(self):
        """
        Test that no initial response is generated.
        """
        self.assertIdentical(self.mechanism.getInitialResponse(), None)


    def test_getResponse(self):
        """
        The response to a Digest-MD5 challenge includes the parameters from the
        challenge.
        """
        challenge = (
            'realm="localhost",nonce="1234",qop="auth",charset=utf-8,'
            'algorithm=md5-sess')
        directives = self.mechanism._parse(
            self.mechanism.getResponse(challenge))
        del directives["cnonce"], directives["response"]
        self.assertEqual({
                'username': 'test', 'nonce': '1234', 'nc': '00000001',
                'qop': ['auth'], 'charset': 'utf-8', 'realm': 'localhost',
                'digest-uri': 'xmpp/example.org'
                }, directives)


    def test_getResponseNonAsciiRealm(self):
        """
        Bytes outside the ASCII range in the challenge are nevertheless
        included in the response.
        """
        challenge = ('realm="\xc3\xa9chec.example.org",nonce="1234",'
                     'qop="auth",charset=utf-8,algorithm=md5-sess')
        directives = self.mechanism._parse(
            self.mechanism.getResponse(challenge))
        del directives["cnonce"], directives["response"]
        self.assertEqual({
                'username': 'test', 'nonce': '1234', 'nc': '00000001',
                'qop': ['auth'], 'charset': 'utf-8',
                'realm': '\xc3\xa9chec.example.org',
                'digest-uri': 'xmpp/example.org'}, directives)


    def test_getResponseNoRealm(self):
        """
        The response to a challenge without a realm uses the host part of the
        JID as the realm.
        """
        challenge = 'nonce="1234",qop="auth",charset=utf-8,algorithm=md5-sess'
        directives = self.mechanism._parse(self.mechanism.getResponse(challenge))
        self.assertEqual(directives['realm'], 'example.org')


    def test_getResponseNoRealmIDN(self):
        """
        If the challenge does not include a realm and the host part of the JID
        includes bytes outside of the ASCII range, the response still includes
        the host part of the JID as the realm.
        """
        self.mechanism = sasl_mechanisms.DigestMD5(
            u'xmpp', u'\u00e9chec.example.org', None, u'test', u'secret')
        challenge = 'nonce="1234",qop="auth",charset=utf-8,algorithm=md5-sess'
        directives = self.mechanism._parse(
            self.mechanism.getResponse(challenge))
        self.assertEqual(directives['realm'], '\xc3\xa9chec.example.org')


    def test_calculateResponse(self):
        """
        The response to a Digest-MD5 challenge is computed according to RFC
        2831.
        """
        charset = 'utf-8'
        nonce = 'OA6MG9tEQGm2hh'
        nc = '%08x' % (1,)
        cnonce = 'OA6MHXh6VqTrRk'

        username = u'\u0418chris'
        password = u'\u0418secret'
        host = u'\u0418elwood.innosoft.com'
        digestURI = u'imap/\u0418elwood.innosoft.com'.encode(charset)

        mechanism = sasl_mechanisms.DigestMD5(
            'imap', host, None, username, password)
        response = mechanism._calculateResponse(
            cnonce, nc, nonce, username.encode(charset),
            password.encode(charset), host.encode(charset), digestURI)
        self.assertEqual(response, '7928f233258be88392424d094453c5e3')


    def test_parse(self):
        """
        A challenge can be parsed into a L{dict} with L{bytes} or L{list}
        values.
        """
        challenge = (
            'nonce="1234",qop="auth,auth-conf",charset=utf-8,'
            'algorithm=md5-sess,cipher="des,3des"')
        directives = self.mechanism._parse(challenge)
        self.assertEqual({
                "algorithm": "md5-sess", "nonce": "1234", "charset": "utf-8",
                "qop": ['auth', 'auth-conf'], "cipher": ['des', '3des']
                }, directives)
