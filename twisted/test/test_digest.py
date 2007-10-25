# Copyright (c) 2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for twisted.cred.digest
"""

import time

from twisted.internet import task
from twisted.trial import unittest
from twisted.cred import sasl, digest

# XXX see http://jakarta.apache.org/commons/httpclient/xref-test/org/apache/commons/httpclient/auth/TestDigestAuth.html
# for inspiration?


# From http://tools.ietf.org/html/rfc2617#section-3.5
quotedWWWChallenge = """realm="testrealm@host.com", \
qop="auth,auth-int", \
nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093", \
opaque="5ccc069c403ebaf9f0171e9517f40e41" """

mixquotedWWWChallenge = """realm="testrealm@host.com",\
nonce="00e2855b3f047bfd3297e720498e4571",opaque="00e04875776e15b",\
stale=true , algorithm=MD5 """

# an SASL challenge with qop=auth
chal1 = """realm="elwood.innosoft.com",nonce="OA6MG9tEQGm2hh",qop="auth",\
algorithm=md5-sess,charset=utf-8"""

resp1 = """charset=utf-8,username="chris",realm="elwood.innosoft.com",\
nonce="OA6MG9tEQGm2hh",nc=00000001,cnonce="OA6MHXh6VqTrRk",\
digest-uri="imap/elwood.innosoft.com",\
response=d388dad90d4bbd760a152321f2143af7,qop=auth"""

final1 = """rspauth=ea40f60335c427b5527b84dbabcdfffd"""

# an HTTP challenge with qop=auth
chal2 = """realm="testrealm@host.com",\
qop="auth,auth-int",
nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093",
opaque="5ccc069c403ebaf9f0171e9517f40e41"\
"""

resp2 = """username="Mufasa", \
realm="testrealm@host.com", \
nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093",\
uri="/dir/index.html", \
qop=auth,\
nc=00000001, \
cnonce="0a4f113b", \
response="6629fae49393a05397450978507c4ef1", \
opaque="5ccc069c403ebaf9f0171e9517f40e41"\
"""

# a SIP challenge without qop
chal3 = """realm="domain.tld",nonce="0115a73e3d7bbad83eb238c35e2756fa",\
opaque="00e04875776e15b" """

# an SASL challenge with qop=auth-int
# inspired from http://www.sendmail.org/~ca/email/authrealms.html
chal4 = """nonce="AJRUc5Jx0UQbv5SJ9FoyUnaZpqZIHDhLTU+Awn/K0Uw=",\
qop="auth-int,auth-conf",charset=utf-8,algorithm=md5-sess"""

resp4 = """username="test",realm="wiz.example.com",\
nonce="AJRUc5Jx0UQbv5SJ9FoyUnaZpqZIHDhLTU+Awn/K0Uw=",\
cnonce="AJRUc5Jx0UQbv5SJ9FoyUnaZpqZIHDhLTU+Awn/K0Uw=",\
nc=00000001,qop=auth-int,charset=utf-8,\
digest-uri="smtp/localhost.sendmail.com.",\
response=0e7cfcae717eeac972fc9d5606a1083d"""



class UtilitiesTestCase(unittest.TestCase):
    """
    Tests for utility functions of digest.
    """

    def test_calcHA1preHA1AndUser(self):
        """
        Check that L{digest.calcHA1} raises an exception when preHA1 is
        specified with other informations.
        """
        self.assertRaises(ValueError, digest.calcHA1, 'md5', 'user', 'realm',
                'password', 'nonce', 'cnonce', preHA1='preHA1')


    def test_calcHA1WithoutpreHA1(self):
        """
        If preHA1 is not specified in L{digest.calcHA1}, it should be
        calculated with other informations.
        """
        self.assertEquals(digest.calcHA1('md5', 'user', 'realm', 'password',
            'nonce', 'cnonce'), 'ebbc0ff9a121dbb6789bbe5f82174fa0')


class ChallengeParseTestCase(unittest.TestCase):
    """
    Test cases for the parseChallenge function.
    """

    def _roundTrip(self, fields):
        """
        Do an unparse/parse roundtrip and check equality.
        """
        chal = digest.unparseChallenge(**fields)
        f = digest.parseChallenge(chal)
        self.assertEquals(f, fields)


    def test_parseWWWQuoted(self):
        """
        Various levels of quoting.
        """
        f = digest.parseChallenge(quotedWWWChallenge)
        self.assertEquals(f, {
            'realm': "testrealm@host.com",
            'qop': ["auth","auth-int"],
            'nonce': "dcd98b7102dd2f0e8b11d0f600bfb0c093",
            'opaque': "5ccc069c403ebaf9f0171e9517f40e41",
            'stale': False,
        })
        self._roundTrip(f)


    def test_parseWWWMixquoted(self):
        """
        Various levels of quoting (2).
        """
        f = digest.parseChallenge(mixquotedWWWChallenge)
        self.assertEquals(f, {
            'realm': "testrealm@host.com",
            'nonce': "00e2855b3f047bfd3297e720498e4571",
            'opaque': "00e04875776e15b",
            'algorithm': "MD5",
            'qop': [],
            'stale': True,
        })
        self._roundTrip(f)


    def test_parseStaleTrue(self):
        """
        Explicit stale=true.
        """
        f = digest.parseChallenge('realm="testrealm@host.com",stale=true')
        self.assertEquals(f['stale'], True)
        self._roundTrip(f)


    def test_parseStaleFalse(self):
        """
        Explicit stale=false.
        """
        f = digest.parseChallenge('realm="testrealm@host.com",stale=false')
        self.assertEquals(f['stale'], False)
        self._roundTrip(f)


    def test_parseStaleAbsent(self):
        """
        Implicit stale=false.
        """
        f = digest.parseChallenge('realm="testrealm@host.com"')
        self.assertEquals(f['stale'], False)
        self._roundTrip(f)


    def test_parseSASLChal(self):
        """
        A real SASL challenge.
        """
        f = digest.parseChallenge(chal1)
        self.assertEquals(f, {
            'realm': "elwood.innosoft.com",
            'nonce': "OA6MG9tEQGm2hh",
            'qop': ["auth"],
            'algorithm': "md5-sess",
            'charset': "utf-8",
            'stale': False,
        })
        self._roundTrip(f)


    def test_parseHTTPChal(self):
        """
        A real HTTP challenge.
        """
        f = digest.parseChallenge(chal2)
        self.assertEquals(f, {
            'realm': "testrealm@host.com",
            'qop': ["auth", "auth-int"],
            'nonce': "dcd98b7102dd2f0e8b11d0f600bfb0c093",
            'opaque': "5ccc069c403ebaf9f0171e9517f40e41",
            'stale': False,
        })
        self._roundTrip(f)


    def test_parseFinalChal(self):
        """
        A real final (rspauth) challenge.
        """
        f = digest.parseChallenge(final1)
        self.assertEquals(f, {
            'rspauth': "ea40f60335c427b5527b84dbabcdfffd",
            'qop': [],
            'stale': False,
        })



class ResponseParseTestCase(unittest.TestCase):
    """
    Test cases for the parseResponse function.
    """

    def _roundTrip(self, fields):
        """
        Do an unparse/parse roundtrip and check equality.
        """
        resp = digest.unparseResponse(**fields)
        f = digest.parseResponse(resp)
        self.assertEquals(f, fields)


    def test_parseSASLResp(self):
        """
        A real SASL response.
        """
        f = digest.parseResponse(resp1)
        self.assertEquals(f, {
            'charset': 'utf-8',
            'username': "chris",
            'realm': "elwood.innosoft.com",
            'nonce': "OA6MG9tEQGm2hh",
            'nc': '00000001',
            'cnonce': "OA6MHXh6VqTrRk",
            'digest-uri': "imap/elwood.innosoft.com",
            'response': "d388dad90d4bbd760a152321f2143af7",
            'qop': 'auth',
        })
        self._roundTrip(f)


    def test_parseWWWResp(self):
        """
        A real HTTP response.
        """
        f = digest.parseResponse(resp2)
        self.assertEquals(f, {
            'username': "Mufasa",
            'realm': "testrealm@host.com",
            'nonce': "dcd98b7102dd2f0e8b11d0f600bfb0c093",
            'uri': "/dir/index.html",
            'qop': "auth",
            'nc': "00000001",
            'cnonce': "0a4f113b",
            'response': "6629fae49393a05397450978507c4ef1",
            'opaque': "5ccc069c403ebaf9f0171e9517f40e41",
        })
        self._roundTrip(f)



class HTTPMechanismTestCase(unittest.TestCase):
    """
    Test cases for the HTTPDigestMechanism class.
    """

    def test_responseFromPassword(self):
        """
        Generate digest response from password.
        """
        fields = digest.parseChallenge(chal2)
        mech = digest.HTTPDigestMechanism("Mufasa", "/dir/index.html", fields)
        mech.setClientParams("0a4f113b", "00000001", "auth")
        r = mech.getResponseFromPassword("Circle Of Life", "GET")
        self.assertEquals(r, "6629fae49393a05397450978507c4ef1")



class SASLMechanismTestCase(unittest.TestCase):
    """
    Test cases for the SASLDigestMechanism class.
    """

    def test_responseFromPassword(self):
        """
        Generate digest response from password.
        """
        fields = digest.parseChallenge(chal1)
        mech = digest.SASLDigestMechanism(
            "chris", "imap/elwood.innosoft.com", fields)
        mech.setClientParams("OA6MHXh6VqTrRk", "00000001", "auth")
        r = mech.getResponseFromPassword("secret")
        self.assertEquals(r, "d388dad90d4bbd760a152321f2143af7")
        # rspauth
        r = mech.getResponseFromPassword("secret", method="")
        self.assertEquals(r, "ea40f60335c427b5527b84dbabcdfffd")


#
# Test responders
#

class _BaseResponderTestCase(object):
    """
    Base class for {SASL,HTTP}DigestResponder classes.
    """

    def _checkResponseToChallenge(self, resp, chal, checkDict):
        """
        Given a responder and a challenge, checks its response contains the
        expected field values.
        """
        f2 = digest.parseResponse(resp)
        f = digest.parseChallenge(chal)
        for s in 'nonce', 'realm', 'opaque':
            if s in f:
                self.assertEquals(f2[s], f[s])
        for k, v in checkDict.items():
            if v is not None:
                self.assertEquals(f2[k], v)
            else:
                self.assertTrue(k not in f2)
        return f2



class HTTPResponderTestCase(_BaseResponderTestCase, unittest.TestCase):
    """
    Test cases for the HTTPDigestResponder class.
    """

    def test_latinUsername(self):
        """
        Username with non-ASCII characters and no charset parameter.
        """
        checkDict = {
            'charset': None,
            'username': "andr\xe9",
        }
        # Unicode username
        responder = digest.HTTPDigestResponder(
            username=u"andr\u00e9", password="Circle Of Life")
        responder.cnonce = "1234"
        chalType, unparsed = responder.getResponse(chal2,
            uri="/dir/index.html", method="GET")
        f = self._checkResponseToChallenge(unparsed, chal2, checkDict)


    def test_respondMD5Auth(self):
        """
        Generate response for algorithm=MD5 and qop=auth.
        """
        checkDict = {
            'charset': None,
            'uri': "/dir/index.html",
            'nonce': "dcd98b7102dd2f0e8b11d0f600bfb0c093",
            'cnonce': "0a4f113b",
            'nc': "00000001",
            'qop': "auth",
            'username': "Mufasa",
            'response': "6629fae49393a05397450978507c4ef1",
        }
        responder = digest.HTTPDigestResponder(
            username="Mufasa", password="Circle Of Life")
        responder.cnonce = "0a4f113b"
        chalType, unparsed = responder.getResponse(chal2,
            uri="/dir/index.html", method="GET")
        self.assertIsInstance(chalType, sasl.InitialChallenge)
        self._checkResponseToChallenge(unparsed, chal2, checkDict)
        # Subsequent auth increments nc
        chalType, unparsed = responder.getResponse(chal2,
            uri="/dir/index.html", method="GET")
        self.assertIsInstance(chalType, sasl.InitialChallenge)
        checkDict['nc'] = "00000002"
        del checkDict['response']
        f = self._checkResponseToChallenge(unparsed, chal2, checkDict)
        self.assertNotEquals(f['response'], "6629fae49393a05397450978507c4ef1")


    def test_respondMD5WithoutQop(self):
        """
        Support for RFC 2069 servers (no qop).
        """
        checkDict = {
            'charset': None,
            'uri': "sip:domain.tld",
            'nonce': "0115a73e3d7bbad83eb238c35e2756fa",
            'cnonce': None,
            'nc': None,
            'qop': None,
            'username': "robobob5003",
            'response': "0883c5e1ce2ea2af5e44fc3e3ae1643b",
        }
        responder = digest.HTTPDigestResponder(
            username="robobob5003", password="spameggs")
        chalType, unparsed = responder.getResponse(chal3,
            uri="sip:domain.tld", method="REGISTER")
        self.assertIsInstance(chalType, sasl.InitialChallenge)
        self._checkResponseToChallenge(unparsed, chal3, checkDict)
        # Subsequent auth returns same response
        chalType, unparsed = responder.getResponse(chal3,
            uri="sip:domain.tld", method="REGISTER")
        self.assertIsInstance(chalType, sasl.InitialChallenge)
        self._checkResponseToChallenge(unparsed, chal3, checkDict)



class SASLResponderTestCase(_BaseResponderTestCase, unittest.TestCase):
    """
    Test cases for the SASLDigestResponder class.
    """

    def test_noAuthzid(self):
        """
        No authzid in response by default.
        """
        responder = digest.SASLDigestResponder(
            username="chris", password="secret")
        chalType, unparsed = responder.getResponse(chal1, uri="/")
        f = digest.parseResponse(unparsed)
        self.assertIdentical(f.get('authzid'), None)


    def test_authzid(self):
        """
        Authzid in response if specified.
        """
        responder = digest.SASLDigestResponder(
            username="chris", password="secret", authzid="paul")
        chalType, unparsed = responder.getResponse(chal1, uri="/")
        f = digest.parseResponse(unparsed)
        self.assertEquals(f.get('authzid'), "paul")


    def test_latinUsernameAndPassword(self):
        """
        Username/password with iso-8859-1 characters and charset=utf-8 param.
        The username will be encoded in utf-8 in the response, but its hash
        will be taken in iso-8859-1 form. Weird :-)
        """
        checkDict = {
            'charset': 'utf-8',
            'username': "andr\xc3\xa9",
        }
        # Unicode username and password
        responder = digest.SASLDigestResponder(
            username=u"andr\u00e9", password=u"h\u00e9")
        responder.cnonce = "1234"
        chalType, unparsed = responder.getResponse(
            chal1, uri="/dir/index.html")
        f = self._checkResponseToChallenge(unparsed, chal1, checkDict)


    def test_unicodeUsernameAndPassword(self):
        """
        Username/password with non iso-8859-1 characters and charset=utf-8
        parameter.
        """
        checkDict = {
            'charset': 'utf-8',
            'username': "andr\xc3\xa9",
        }
        # Unicode username and password
        responder = digest.SASLDigestResponder(
            username=u"andr\u00e9", password=u"\u0101")
        responder.cnonce = "1234"
        chalType, unparsed = responder.getResponse(
            chal1, uri="/dir/index.html")
        f = self._checkResponseToChallenge(unparsed, chal1, checkDict)


    def test_respondMD5SessAuth(self):
        """
        Generate response for algorithm=md5-sess and qop=auth.
        """
        checkDict = {
            'charset': "utf-8",
            'digest-uri': "imap/elwood.innosoft.com",
            'nonce': "OA6MG9tEQGm2hh",
            'cnonce': "OA6MHXh6VqTrRk",
            'nc': "00000001",
            'qop': "auth",
            'username': "chris",
            'response': "d388dad90d4bbd760a152321f2143af7",
        }
        responder = digest.SASLDigestResponder(
            username="chris", password="secret")
        responder.cnonce = "OA6MHXh6VqTrRk"
        chalType, unparsed = responder.getResponse(chal1,
            uri="imap/elwood.innosoft.com")
        self.assertIsInstance(chalType, sasl.InitialChallenge)
        self._checkResponseToChallenge(unparsed, chal1, checkDict)
        # Subsequent auth increments nc
        chalType, unparsed = responder.getResponse(chal1,
            uri="imap/elwood.innosoft.com")
        self.assertIsInstance(chalType, sasl.InitialChallenge)
        checkDict['nc'] = "00000002"
        del checkDict['response']
        f = self._checkResponseToChallenge(unparsed, chal1, checkDict)
        self.assertNotEquals(f['response'], "d388dad90d4bbd760a152321f2143af7")


    def test_respondMD5SessAuthFinal(self):
        """
        Generate rspauth for algorithm=md5-sess and qop=auth.
        """
        responder = digest.SASLDigestResponder(username="chris",
            password="secret")
        responder.cnonce = "OA6MHXh6VqTrRk"
        responder.getResponse(chal1, uri="imap/elwood.innosoft.com")
        chalType, unparsed = responder.getResponse(final1,
            uri="imap/elwood.innosoft.com")
        self.assertIsInstance(chalType, sasl.FinalChallenge)
        self.assertIdentical(unparsed, None)
        # Bad rspauth
        self.assertRaises(sasl.FailedChallenge, responder.getResponse,
            "rspauth=0", uri="imap/elwood.innosoft.com")


    def test_unexpectedFinalChallenge(self):
        """
        A final challenge sent without a previous challenge should raise
        an exception.
        """
        responder = digest.SASLDigestResponder(username="chris",
            password="secret")
        self.assertRaises(sasl.UnexpectedFinalChallenge,
            responder.getResponse, final1, uri="imap/elwood.innosoft.com")


    def test_respondMD5SessAuthInt(self):
        """
        Generate response for algorithm=md5-sess, qop=auth-int, and
        without realm.
        """
        checkDict = {
            'charset': "utf-8",
            'digest-uri': "smtp/localhost.sendmail.com.",
            'nonce': "AJRUc5Jx0UQbv5SJ9FoyUnaZpqZIHDhLTU+Awn/K0Uw=",
            'cnonce': "AJRUc5Jx0UQbv5SJ9FoyUnaZpqZIHDhLTU+Awn/K0Uw=",
            'nc': "00000001",
            'qop': "auth-int",
            'username': "test",
            'response': "780c0451303666e1ea9a24de7b5eb08b",
        }
        responder = digest.SASLDigestResponder(username="test",
            password="tEst42", realm="wiz.example.com")
        responder.cnonce = "AJRUc5Jx0UQbv5SJ9FoyUnaZpqZIHDhLTU+Awn/K0Uw="
        chalType, unparsed = responder.getResponse(chal4,
            uri="smtp/localhost.sendmail.com.")
        self.assertIsInstance(chalType, sasl.InitialChallenge)
        self._checkResponseToChallenge(unparsed, chal4, checkDict)
        # Subsequent auth increments nc
        chalType, unparsed = responder.getResponse(chal4,
            uri="smtp/localhost.sendmail.com.")
        self.assertIsInstance(chalType, sasl.InitialChallenge)
        checkDict['nc'] = "00000002"
        del checkDict['response']
        f = self._checkResponseToChallenge(unparsed, chal4, checkDict)
        self.assertNotEquals(f['response'], "780c0451303666e1ea9a24de7b5eb08b")


    def test_overrideRealm(self):
        """
        Default responder realm overriden by realm in challenge.
        """
        responder = digest.SASLDigestResponder(username="chris",
            password="secret", realm="example.org")
        responder.cnonce = "OA6MHXh6VqTrRk"
        chalType, unparsed = responder.getResponse(chal1,
            uri="imap/elwood.innosoft.com")
        self._checkResponseToChallenge(unparsed, chal1, {})


    def test_noRealm(self):
        """
        No realm in challenge and no default realm in responder either.
        """
        responder = digest.SASLDigestResponder(username="test",
            password="tEst42")
        self.assertRaises(sasl.InvalidChallenge, responder.getResponse,
            chal4, uri="smtp/localhost.sendmail.com.")



#
# Test challengers
#

class StaticTimeSASLChallenger(digest.SASLDigestChallenger):
    """
    An SASLDigestChallenger which is bound to a deterministic clock.
    """

    def __init__(self, *args, **kargs):
        digest.SASLDigestChallenger.__init__(self, *args, **kargs)
        self._clock = task.Clock()
        self._callLater = self._clock.callLater


    def _getTime(self):
        return self._clock.seconds()



class StaticTimeHTTPChallenger(digest.HTTPDigestChallenger):
    """
    An HTTPDigestChallenger which is bound to a deterministic clock.
    """

    def __init__(self, *args, **kargs):
        digest.HTTPDigestChallenger.__init__(self, *args, **kargs)
        self._clock = task.Clock()
        self._callLater = self._clock.callLater


    def _getTime(self):
        return self._clock.seconds()



class _BaseChallengerTestCase(object):
    """
    Base class for {HTTP,SASL}DigestChallenger test cases.
    """

    def test_freshNonce(self):
        """
        Accept a fresh nonce.
        """
        c = self.challengerClass("example.com")
        nonce = c.generateNonce()
        nonce2 = c.generateNonce()
        self.assertNotEquals(nonce, nonce2)
        self.assertEquals(c.acceptNonce(nonce, "00000001"), True)
        self.assertEquals(c.acceptNonce(nonce2, "00000001"), True)


    def test_expiredNonce(self):
        """
        Don't accept an expired nonce.
        """
        c = self.staticTimeChallengerClass("example.com")
        c._clock.advance(time.time())
        nonce = c.generateNonce()
        nonce2 = c.generateNonce()
        self.assertNotEquals(nonce, nonce2)
        c._clock.advance(c.CHALLENGE_LIFETIME_SECS * 0.5)
        self.assertEquals(c.acceptNonce(nonce, "00000001"), True)
        c._clock.advance(c.CHALLENGE_LIFETIME_SECS * 0.5 + 1)
        self.assertEquals(c.acceptNonce(nonce2, "00000001"), False)


    def test_nonceInFuture(self):
        """
        Don't accept a nonce generated in the future.
        """
        c = self.staticTimeChallengerClass("example.com")
        c._clock.advance(time.time())
        nonce = c.generateNonce()
        c._clock.advance(- c.CHALLENGE_LIFETIME_SECS * 0.5)
        self.assertRaises(sasl.InvalidResponse,
            c.acceptNonce, nonce, "00000001")


    def test_fakeNonce(self):
        """
        Don't accept a fake nonce (i.e. not generated by us).
        """
        c = self.challengerClass("example.com")
        nonce = c.generateNonce()
        self.assertRaises(sasl.InvalidResponse,
            c.acceptNonce, nonce + "1", "00000001")
        self.assertRaises(sasl.InvalidResponse,
            c.acceptNonce, "1" + nonce, "00000001")


    def test_nonceReplay(self):
        """
        Don't accept nonce replays.
        """
        c = self.challengerClass("example.com")
        nonce = c.generateNonce()
        nonce2 = c.generateNonce()
        self.assertNotEquals(nonce, nonce2)
        self.assertEquals(c.acceptNonce(nonce, "00000001"), True)
        self.assertEquals(c.acceptNonce(nonce, "00000002"), True)
        self.assertRaises(sasl.InvalidResponse,
            c.acceptNonce, nonce, "00000001")
        self.assertRaises(sasl.InvalidResponse,
            c.acceptNonce, nonce, "00000002")
        self.assertRaises(sasl.InvalidResponse,
            c.acceptNonce, nonce, "00000004")
        self.assertEquals(c.acceptNonce(nonce, "00000003"), True)


    def test_getChallenge(self):
        """
        Generate a challenge.
        """
        realm = "example.com"
        c = self.challengerClass(realm)
        unparsed = c.getChallenge()
        f = digest.parseChallenge(unparsed)
        self.assertEquals(f['realm'], realm)
        self.assertEquals(f['qop'], ["auth", "auth-int"])
        self.assertEquals(c.acceptNonce(f['nonce'], "00000001"), True)
        self.assertEquals(f['stale'], False)
        self._check_getChallenge(f)


    def test_getRenewedChallenge(self):
        """
        Generate a renewed challenge.
        """
        realm = "example.com"
        c = self.challengerClass(realm)
        # The response is currently ignored so give an empty one
        unparsed = c.getRenewedChallenge("")
        f = digest.parseChallenge(unparsed)
        self.assertEquals(f['realm'], realm)
        self.assertEquals(f['qop'], ["auth", "auth-int"])
        self.assertEquals(c.acceptNonce(f['nonce'], "00000001"), True)
        self.assertEquals(f['stale'], True)
        self._check_getRenewedChallenge(f)


    def _check_processResponseOk(self, realm, uri, username, password,
            method=None, body=None):
        """
        Given some challenge parameters and an username/password, check the
        challenger's response is accepted by the corresponding responder.
        """
        c = self.challengerClass(realm)
        r = self.responderClass(username, password)
        # Initial auth
        chal = c.getChallenge()
        if method is not None or body is not None:
            chalType, resp = r.getResponse(chal, uri, method, body)
        else:
            chalType, resp = r.getResponse(chal, uri)
        self.assertIsInstance(chalType, sasl.InitialChallenge)
        f = digest.parseResponse(resp)
        if body is not None:
            self.assertEquals(f['qop'], "auth-int")
        if method is not None or body is not None:
            credentials = c.processResponse(resp, method, body)
        else:
            credentials = c.processResponse(resp)
        self.assertTrue(credentials.checkPassword(password))
        self.assertFalse(credentials.checkPassword(password + "a"))


    def _check_multipleRoundTrip(self, realm, uri, username, password,
            method=None, body=None):
        """
        Check multiple roundtrips between single challenger and responder
        instances.
        """
        c = self.challengerClass(realm)
        r = self.responderClass(username, password)
        # Roundtrips with new challenge each time
        for i in range(3):
            chal = c.getChallenge()
            if method is not None or body is not None:
                chalType, resp = r.getResponse(chal, uri, method, body)
                credentials = c.processResponse(resp, method, body)
            else:
                chalType, resp = r.getResponse(chal, uri)
                credentials = c.processResponse(resp)
        self.assertTrue(credentials.checkPassword(password))
        self.assertFalse(credentials.checkPassword(password + "a"))
        # Roundtrips with the same original challenge
        chal = c.getChallenge()
        for i in range(3):
            if method is not None or body is not None:
                chalType, resp = r.getResponse(chal, uri, method, body)
                credentials = c.processResponse(resp, method, body)
            else:
                chalType, resp = r.getResponse(chal, uri)
                credentials = c.processResponse(resp)
        self.assertTrue(credentials.checkPassword(password))
        self.assertFalse(credentials.checkPassword(password + "a"))


    def _check_getSuccessfulChallenge(self, response, uri, password, rspauth):
        """
        Check the getSuccessfulChallenge method of the responder.
        """
        f = digest.parseResponse(response)
        c = self.challengerClass(f['realm'])
        mech = digest.SASLDigestMechanism(f['username'], uri, f)
        mech.setClientParams(f['cnonce'], f['nc'], f['qop'])
        cred = digest.DigestedCredentials(mech, f['response'])
        # Generate rspauth
        self.assertTrue(cred.checkPassword(password))
        unparsed = c.getSuccessfulChallenge(resp1, cred)
        f2 = digest.parseChallenge(unparsed)
        self.assertEquals(f2['rspauth'], rspauth)


    def _check_processResponseError(self, response, message):
        """
        Check that processing the given response raise a
        L{sasl.InvalidResponse}, with the specified message.
        """
        c = self.challengerClass("example.com")
        error = self.assertRaises(sasl.InvalidResponse,
                                  c.processResponse, response)
        self.assertEquals(str(error), message)



class SASLChallengerTestCase(unittest.TestCase, _BaseChallengerTestCase):
    """
    Test cases for the SASLDigestChallenger class.
    """

    challengerClass = digest.SASLDigestChallenger
    responderClass = digest.SASLDigestResponder
    staticTimeChallengerClass = StaticTimeSASLChallenger

    def _check_getChallenge(self, f):
        """
        Callback for basic checking of initial challenge fields.
        """
        self.assertTrue('opaque' not in f)
        self.assertEquals(f['charset'], "utf-8")
        self.assertEquals(f['algorithm'], "md5-sess")


    def _check_getRenewedChallenge(self, f):
        """
        Callback for basic checking of renewed challenge fields.
        """
        self.assertTrue('opaque' not in f)
        self.assertEquals(f['charset'], "utf-8")
        self.assertEquals(f['algorithm'], "md5-sess")


    def test_processResponseOk(self):
        """
        Full challenger -> responder -> challenger roundtrip,
        with credentials check.
        """
        self._check_processResponseOk("example.com", "/", "chris", "secret")


    def test_processResponseWithLatinUsername(self):
        """
        Full challenger -> responder -> challenger roundtrip,
        with credentials check on an ISO-8859-1 username.
        """
        self._check_processResponseOk(
            "example.com", "/", u"andr\u00e9", "secret")


    def test_processResponseWithUTF8Password(self):
        """
        Full challenger -> responder -> challenger roundtrip,
        with credentials check on an unicode (non ISO-8859-1) password.
        """
        self._check_processResponseOk(
            "example.com", "/", u"andr\u00e9", u"\u0101")


    def test_multipleRoundTrip(self):
        """
        Multiple roundtrip with same challenger and responder.
        """
        self._check_multipleRoundTrip("example.com", "/", "chris", "secret")


    def test_getSuccessfulChallenge(self):
        """
        Generate rspauth challenge.
        """
        self._check_getSuccessfulChallenge(resp1, "imap/elwood.innosoft.com",
            password="secret", rspauth="ea40f60335c427b5527b84dbabcdfffd")


    def test_processResponseWithoutNonce(self):
        """
        C{processResponse} should raise an exception when nonce is missing.
        """
        response = """username="chris", charset="utf-8", realm="example.com",
qop="auth", cnonce="27820981e17b5328ca57da861dc71436b8bce3b7", nc=00000001,
digest-uri="/", response=8721b91249d933caac86e455ac540921"""
        self._check_processResponseError(response, "Missing nonce.")


    def test_processResponseWithoutCnonce(self):
        """
        C{processResponse} should raise an exception when cnonce is missing.
        """
        response = """username="chris",
nonce="1193303803.810376196fa01ada2e23af4c66b9d4f2580ed8c8", charset="utf-8",
realm="example.com", qop="auth",
cnonce="a55d42daf1f13f5a16e6f1657054ec79bf674431", digest-uri="/",
response=bdf54ad80839a8c207020a4575d384e0"""
        self._check_processResponseError(response,
                "Missing nc and/or cnonce value.")


    def test_processResponseWithoutRealm(self):
        """
        C{processResponse} should raise an exception when realm is missing.
        """
        response = """username="chris",
nonce="1193304196.47466b8453c62a518449d607b68621146ac441f9", charset="utf-8",
qop="auth", cnonce="9401ee17a73b0843a89c987de83e6060c439ae03", nc=00000001,
digest-uri="/", response=430b342dfb56551f0955418a1e76ab70"""
        self._check_processResponseError(response, "Missing realm.")


    def test_processResponseWithInvalidRealm(self):
        """
        C{processResponse} should raise an exception when realm doesn't match
        the realm of the responder.
        """
        response = """username="chris",
nonce="1193304196.47466b8453c62a518449d607b68621146ac441f9", charset="utf-8",
realm="wrongexample.com", qop="auth",
cnonce="9401ee17a73b0843a89c987de83e6060c439ae03", nc=00000001, digest-uri="/",
response=430b342dfb56551f0955418a1e76ab70"""
        self._check_processResponseError(response,
                "Invalid realm 'wrongexample.com'.")


    def test_processWithoutUsername(self):
        """
        C{processResponse} should raise an exception when username is missing.
        """
        response = """
nonce="1193304464.bc495502323c4b96573491c822c1d1853c0d820d", charset="utf-8",
realm="example.com", qop="auth",
cnonce="ec08bcfcd068e2eb1d6be9da5ddc1fc0589e8bc0", nc=00000001, digest-uri="/",
response=1e03d87a358bdaad0334e3a40500e63b"""
        self._check_processResponseError(response, "Missing username.")


    def test_processWithoutResponse(self):
        """
        C{processResponse} should raise an exception when digest response is
        missing.
        """
        response = """username="chris",
nonce="1193304563.56182ed7a7561e8b67e74e3c501849e31ca0a103", charset="utf-8",
realm="example.com", qop="auth",
cnonce="6b71899e7045ee4ae55c8c8f0d307137edde354c", digest-uri="/",
nc=00000001"""
        self._check_processResponseError(response, "Missing digest response.")


    def test_processWithoutURI(self):
        """
        C{processResponse} should raise an exception when URI is missing.
        """
        response = """username="chris",
nonce="1193304697.5550bd0e3565b8c2ed1b4118b0f1724b72f1e6ed", charset="utf-8",
realm="example.com", qop="auth",
cnonce="d99048191cbe3427578aab7f52510e35d0378dca", nc=00000001,
response=9b134c5f20218f556ca91031c7342c37"""
        self._check_processResponseError(response, "Missing digest URI.")


    def test_processWithoutQOP(self):
        """
        C{processResponse} should raise an exception when QOP is missing.
        """
        response = """username="chris",
nonce="1193304949.15f1d7500f3f516eed44876b8d88144c5764ce12", charset="utf-8",
realm="example.com", cnonce="9032d855287cbe5f6041d355c136a12a6d3f642c",
nc=00000001, digest-uri="/", response=84352483446ab9f2f5d59465891ebcdd"""
        self._check_processResponseError(response, "Missing qop value.")


    def test_processInvalidQOP(self):
        """
        C{processResponse} should raise an exception when QOP has an invalid
        value.
        """
        response = """username="chris",
nonce="1193304949.15f1d7500f3f516eed44876b8d88144c5764ce12", charset="utf-8",
realm="example.com", qop="spam",
cnonce="9032d855287cbe5f6041d355c136a12a6d3f642c", nc=00000001, digest-uri="/",
response=84352483446ab9f2f5d59465891ebcdd"""
        self._check_processResponseError(response, "Invalid qop value 'spam'.")


    def test_processInvalidAlgorithm(self):
        """
        C{processResponse} should raise an exception when the algorithm is not
        handled.
        """
        response = """username="chris", algorithm="foobar",
nonce="1193304949.15f1d7500f3f516eed44876b8d88144c5764ce12", charset="utf-8",
realm="example.com", qop="auth",
cnonce="9032d855287cbe5f6041d355c136a12a6d3f642c", nc=00000001, digest-uri="/",
response=84352483446ab9f2f5d59465891ebcdd"""
        self._check_processResponseError(response,
                                         "Invalid algorithm 'foobar'.")


    def test_processInvalidNonce(self):
        """
        C{processResponse} should raise an exception when nonce has an invalid
        value.
        """
        response = """username="chris",
nonce="foo.15f1d7500f3f516eed44876b8d88144c5764ce12", charset="utf-8",
realm="example.com", qop="auth",
cnonce="9032d855287cbe5f6041d355c136a12a6d3f642c", nc=00000001, digest-uri="/",
response=84352483446ab9f2f5d59465891ebcdd"""
        self._check_processResponseError(response, "Invalid nonce value.")


    def test_processOldNonce(self):
        """
        C{processResponse} should not return any credentials if the nonce is
        too old.
        """
        response = """username="chris",
nonce="0193304949.15f1d7500f3f516eed44876b8d88144c5764ce12", charset="utf-8",
realm="example.com", qop="auth",
cnonce="9032d855287cbe5f6041d355c136a12a6d3f642c", nc=00000001, digest-uri="/",
response=84352483446ab9f2f5d59465891ebcdd"""
        c = self.challengerClass("example.com")
        self.assertIdentical(c.processResponse(response), None)



class HTTPChallengerTestCase(unittest.TestCase, _BaseChallengerTestCase):
    """
    Test cases for the HTTPDigestChallenger class.
    """

    challengerClass = digest.HTTPDigestChallenger
    responderClass = digest.HTTPDigestResponder
    staticTimeChallengerClass = StaticTimeHTTPChallenger

    def _check_getChallenge(self, f):
        """
        Callback for basic checking of initial challenge fields.
        """
        self.assertTrue('opaque' in f)
        self.assertTrue('charset' not in f)
        self.assertEquals(f['algorithm'], "md5")


    def _check_getRenewedChallenge(self, f):
        """
        Callback for basic checking of renewed challenge fields.
        """
        self.assertTrue('opaque' in f)
        self.assertTrue('charset' not in f)
        self.assertEquals(f['algorithm'], "md5")


    def test_processResponseOk(self):
        """
        Full challenger -> responder -> challenger roundtrip,
        with credentials check.
        """
        self._check_processResponseOk("example.com", "/", "chris", "secret")
        self._check_processResponseOk("example.com", "/", "chris", "secret",
            "GET")
        self._check_processResponseOk("example.com", "/", "chris", "secret",
            "GET", "blah")


    def test_multipleRoundTrip(self):
        """
        Multiple roundtrip with same challenger and responder.
        """
        self._check_multipleRoundTrip("example.com", "/", "chris", "secret")
        self._check_multipleRoundTrip("example.com", "/", "chris", "secret",
            "GET")
        self._check_multipleRoundTrip("example.com", "/", "chris", "secret",
            "GET", "blah")


    def test_processResponseWithLatinUsername(self):
        """
        Full challenger -> responder -> challenger roundtrip,
        with credentials check on an ISO-8859-1 username.
        """
        self._check_processResponseOk(
            "example.com", "/", u"andr\u00e9", "secret")
        self._check_processResponseOk(
            "example.com", "/", u"andr\u00e9", "secret", "GET")
        self._check_processResponseOk(
            "example.com", "/", u"andr\u00e9", "secret", "GET", "blah")


    def test_weakDigest(self):
        """
        Support for RFC 2069 clients.
        """
        method, body = "GET", "blah"
        c = self.challengerClass("example.com")
        r = self.responderClass("chris", "secret")
        r._chooseQop = lambda *_: None
        chal = c.getChallenge()
        chalType, resp = r.getResponse(chal, "/", method, body)
        f = digest.parseResponse(resp)
        self.assertIdentical(f.get('qop'), None)
        credentials = c.processResponse(resp, method, body)
        self.assertTrue(credentials.checkPassword("secret"))
        self.assertFalse(credentials.checkPassword("secreta"))

