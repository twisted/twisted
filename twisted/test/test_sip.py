# -*- test-case-name: twisted.test.test_sip -*-
# Copyright (c) 2001-2009 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Session Initialization Protocol tests."""

from twisted.trial import unittest, util
from twisted.protocols import sip
from twisted.internet import defer, reactor
from twisted.python.versions import Version
from twisted.internet.task import Clock
from twisted.test.proto_helpers import FakeDatagramTransport

from twisted.test import proto_helpers

from twisted import cred
import twisted.cred.portal
import twisted.cred.checkers

from zope.interface import implements

#Warnings to suppress in tests for deprecated code.
suppress = [
    util.suppress(message="twisted.protocols.sip.DigestedCredentials "
                  "was deprecated in Twisted 9.0.0"),
    util.suppress(message="twisted.protocols.sip.DigestCalcResponse "
                  "was deprecated in Twisted 9.0.0"),
    util.suppress(message="twisted.protocols.sip.DigestCalcHA1 "
                  "was deprecated in Twisted 9.0.0"),
    util.suppress(message="twisted.protocols.sip.DigestAuthorizer "
                  "was deprecated in Twisted 9.0.0"),
    util.suppress(message="twisted.protocols.sip.BasicAuthorizer "
                  "was deprecated in Twisted 9.0.0"),
    ]

# request, prefixed by random CRLFs
request1 = "\n\r\n\n\r" + """\
INVITE sip:foo SIP/2.0
From: mo
To: joe
Content-Length: 4

abcd""".replace("\n", "\r\n")

# request, no content-length
request2 = """INVITE sip:foo SIP/2.0
From: mo
To: joe

1234""".replace("\n", "\r\n")

# request, with garbage after
request3 = """INVITE sip:foo SIP/2.0
From: mo
To: joe
Content-Length: 4

1234

lalalal""".replace("\n", "\r\n")

# three requests
request4 = """INVITE sip:foo SIP/2.0
From: mo
To: joe
Content-Length: 0

INVITE sip:loop SIP/2.0
From: foo
To: bar
Content-Length: 4

abcdINVITE sip:loop SIP/2.0
From: foo
To: bar
Content-Length: 4

1234""".replace("\n", "\r\n")

# response, no content
response1 = """SIP/2.0 200 OK
From:  foo
To:bar
Content-Length: 0

""".replace("\n", "\r\n")

# short header version
request_short = """\
INVITE sip:foo SIP/2.0
f: mo
t: joe
l: 4

abcd""".replace("\n", "\r\n")

request_natted = """\
INVITE sip:foo SIP/2.0
Via: SIP/2.0/UDP 10.0.0.1:5060;rport

""".replace("\n", "\r\n")

oldStyleInvite = """\
INVITE sip:bob@proxy2.org SIP/2.0\r
Via: SIP/2.0/UDP client.com:5060;branch=7\r
Max-Forwards: 70\r
Route: <sip:proxy1.org;lr>\r
From: Alice <sip:alice@proxy1.org>;tag=9fxced76sl\r
To: Bob <sip:bob@proxy2.org>\r
Call-ID: 3848276298220188511@client.com\r
CSeq: 1 INVITE\r
Contact: <sip:alice@client.com>\r
\r
 """


# INVITE Alice -> Proxy 1
aliceInvite = """\
INVITE sip:bob@proxy2.org SIP/2.0\r
Via: SIP/2.0/UDP client.com:5060;branch=z9hG4bK74bf9\r
Max-Forwards: 70\r
Route: <sip:proxy1.org;lr>\r
From: Alice <sip:alice@proxy1.org>;tag=9fxced76sl\r
To: Bob <sip:bob@proxy2.org>\r
Call-ID: 3848276298220188511@client.com\r
CSeq: 1 INVITE\r
Contact: <sip:alice@client.com>\r
\r
 """

#F19 487 Request Terminated Proxy 1 -> Alice
alice487 = """\
SIP/2.0 487 Request Terminated\r
Via: SIP/2.0/UDP client.com:5060;branch=z9hG4bK74bf9\r
From: Alice <sip:alice@proxy1.org>;tag=9fxced76sl\r
To: Bob <sip:bob@proxy2.org>;tag=314159\r
Call-ID: 3848276298220188511@client.com\r
CSeq: 1 INVITE\r
\r
"""

#F20 ACK Alice -> Proxy 1
alice487Ack = """\
ACK sip:bob@proxy2.org SIP/2.0\r
Via: SIP/2.0/UDP client.com:5060;branch=z9hG4bK74bf9\r
Max-Forwards: 70\r
From: Alice <sip:alice@proxy1.org>;tag=9fxced76sl\r
To: Bob <sip:bob@proxy2.org>;tag=314159\r
Call-ID: 3848276298220188511@client.com\r
CSeq: 1 ACK\r
\r
"""

oldStyleAck = """\
ACK sip:bob@proxy2.org SIP/2.0\r
Via: SIP/2.0/UDP client.com:5060;branch=7\r
Max-Forwards: 70\r
From: Alice <sip:alice@proxy1.org>;tag=9fxced76sl\r
To: Bob <sip:bob@proxy2.org>;tag=314159\r
Call-ID: 3848276298220188511@client.com\r
CSeq: 1 ACK\r
\r
"""

class TestRealm:
    def requestAvatar(self, avatarId, mind, *interfaces):
        return sip.IContact, None, lambda: None

class MessageParsingTestCase(unittest.TestCase):
    def setUp(self):
        self.l = []
        self.parser = sip.MessagesParser(self.l.append)

    def feedMessage(self, message):
        self.parser.dataReceived(message)
        self.parser.dataDone()

    def validateMessage(self, m, method, uri, headers, body):
        """Validate Requests."""
        self.assertEquals(m.method, method)
        self.assertEquals(m.uri.toString(), uri)
        self.assertEquals(m.headers, headers)
        self.assertEquals(m.body, body)
        self.assertEquals(m.finished, 1)

    def testSimple(self):
        l = self.l
        self.feedMessage(request1)
        self.assertEquals(len(l), 1)
        self.validateMessage(l[0], "INVITE", "sip:foo",
                             {"from": ["mo"], "to": ["joe"], "content-length": ["4"]},
                             "abcd")

    def testTwoMessages(self):
        l = self.l
        self.feedMessage(request1)
        self.feedMessage(request2)
        self.assertEquals(len(l), 2)
        self.validateMessage(l[0], "INVITE", "sip:foo",
                             {"from": ["mo"], "to": ["joe"], "content-length": ["4"]},
                             "abcd")
        self.validateMessage(l[1], "INVITE", "sip:foo",
                             {"from": ["mo"], "to": ["joe"]},
                             "1234")

    def testGarbage(self):
        l = self.l
        self.feedMessage(request3)
        self.assertEquals(len(l), 1)
        self.validateMessage(l[0], "INVITE", "sip:foo",
                             {"from": ["mo"], "to": ["joe"], "content-length": ["4"]},
                             "1234")

    def testThreeInOne(self):
        l = self.l
        self.feedMessage(request4)
        self.assertEquals(len(l), 3)
        self.validateMessage(l[0], "INVITE", "sip:foo",
                             {"from": ["mo"], "to": ["joe"], "content-length": ["0"]},
                             "")
        self.validateMessage(l[1], "INVITE", "sip:loop",
                             {"from": ["foo"], "to": ["bar"], "content-length": ["4"]},
                             "abcd")
        self.validateMessage(l[2], "INVITE", "sip:loop",
                             {"from": ["foo"], "to": ["bar"], "content-length": ["4"]},
                             "1234")

    def testShort(self):
        l = self.l
        self.feedMessage(request_short)
        self.assertEquals(len(l), 1)
        self.validateMessage(l[0], "INVITE", "sip:foo",
                             {"from": ["mo"], "to": ["joe"], "content-length": ["4"]},
                             "abcd")
        
    def testSimpleResponse(self):
        l = self.l
        self.feedMessage(response1)
        self.assertEquals(len(l), 1)
        m = l[0]
        self.assertEquals(m.code, 200)
        self.assertEquals(m.phrase, "OK")
        self.assertEquals(m.headers, {"from": ["foo"], "to": ["bar"], "content-length": ["0"]})
        self.assertEquals(m.body, "")
        self.assertEquals(m.finished, 1)


class MessageParsingTestCase2(MessageParsingTestCase):
    """Same as base class, but feed data char by char."""

    def feedMessage(self, message):
        for c in message:
            self.parser.dataReceived(c)
        self.parser.dataDone()


class MakeMessageTestCase(unittest.TestCase):

    def testRequest(self):
        r = sip.Request("INVITE", "sip:foo")
        r.addHeader("foo", "bar")
        self.assertEquals(r.toString(), "INVITE sip:foo SIP/2.0\r\nFoo: bar\r\n\r\n")


    def testResponse(self):
        """
        Test creation of L{Response} objects and their properties.
        """
        r = sip.Response(200, "OK")
        r.addHeader("foo", "bar")
        r.addHeader("Content-Length", "4")
        r.bodyDataReceived("1234")
        self.assertEquals(r.toString(),
                          "SIP/2.0 200 OK\r\nFoo: bar\r\nContent-Length: 4"
                          "\r\n\r\n1234")
        self.assertEquals(repr(r), "<SIP Response %d:200>" % (id(r),))


    def testStatusCode(self):
        r = sip.Response(200)
        self.assertEquals(r.toString(), "SIP/2.0 200 OK\r\n\r\n")


    def test_fromRequest(self):
        """
        L{sip.Response.fromRequest} creates a L{Response} to a L{Request},
        """
        cancelResponse = (
            "SIP/2.0 487 Request Terminated\r\n"
            "Via: SIP/2.0/UDP client.com:5060;branch=z9hG4bK74bf9\r\n"
            "From: Alice <sip:alice@proxy1.org>;tag=9fxced76sl\r\n"
            "To: Bob <sip:bob@proxy2.org>\r\n"
            "Call-ID: 3848276298220188511@client.com\r\n"
            "CSeq: 1 INVITE\r\n"
            "\r\n")
        request = parseMessage(aliceInvite)
        response1 = sip.Response.fromRequest(sip.REQUEST_TERMINATED, request)
        response2 = parseMessage(cancelResponse)
        self.assertEqual(response1.headers, response2.headers)
        self.assertEqual(response1.code, response2.code)



class ViaTestCase(unittest.TestCase):

    def checkRoundtrip(self, v):
        s = v.toString()
        self.assertEquals(s, sip.parseViaHeader(s).toString())

    def testExtraWhitespace(self):
        v1 = sip.parseViaHeader('SIP/2.0/UDP 192.168.1.1:5060')
        v2 = sip.parseViaHeader('SIP/2.0/UDP     192.168.1.1:5060')
        self.assertEquals(v1.transport, v2.transport)
        self.assertEquals(v1.host, v2.host)
        self.assertEquals(v1.port, v2.port)
    
    def test_complex(self):
        """
        Test parsing a Via header with one of everything.
        """
        s = ("SIP/2.0/UDP first.example.com:4000;ttl=16;maddr=224.2.0.1"
             " ;branch=a7c6a8dlze (Example)")
        v = sip.parseViaHeader(s)
        self.assertEquals(v.transport, "UDP")
        self.assertEquals(v.host, "first.example.com")
        self.assertEquals(v.port, 4000)
        self.assertEquals(v.rport, None)
        self.assertEquals(v.rportValue, None)
        self.assertEquals(v.rportRequested, False)
        self.assertEquals(v.ttl, 16)
        self.assertEquals(v.maddr, "224.2.0.1")
        self.assertEquals(v.branch, "a7c6a8dlze")
        self.assertEquals(v.hidden, 0)
        self.assertEquals(v.toString(),
                          "SIP/2.0/UDP first.example.com:4000"
                          ";ttl=16;branch=a7c6a8dlze;maddr=224.2.0.1")
        self.checkRoundtrip(v)
    
    def test_simple(self):
        """
        Test parsing a simple Via header.
        """
        s = "SIP/2.0/UDP example.com;hidden"
        v = sip.parseViaHeader(s)
        self.assertEquals(v.transport, "UDP")
        self.assertEquals(v.host, "example.com")
        self.assertEquals(v.port, 5060)
        self.assertEquals(v.rport, None)
        self.assertEquals(v.rportValue, None)
        self.assertEquals(v.rportRequested, False)
        self.assertEquals(v.ttl, None)
        self.assertEquals(v.maddr, None)
        self.assertEquals(v.branch, None)
        self.assertEquals(v.hidden, True)
        self.assertEquals(v.toString(),
                          "SIP/2.0/UDP example.com:5060;hidden")
        self.checkRoundtrip(v)
    
    def testSimpler(self):
        v = sip.Via("example.com")
        self.checkRoundtrip(v)


    def test_deprecatedRPort(self):
        """
        Setting rport to True is deprecated, but still produces a Via header
        with the expected properties.
        """
        v = sip.Via("foo.bar", rport=True)

        warnings = self.flushWarnings(
            offendingFunctions=[self.test_deprecatedRPort])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(
            warnings[0]['message'],
            'rport=True is deprecated since Twisted 9.0.')
        self.assertEqual(
            warnings[0]['category'],
            DeprecationWarning)

        self.assertEqual(v.toString(), "SIP/2.0/UDP foo.bar:5060;rport")
        self.assertEqual(v.rport, True)
        self.assertEqual(v.rportRequested, True)
        self.assertEqual(v.rportValue, None)


    def test_rport(self):
        """
        An rport setting of None should insert the parameter with no value.
        """
        v = sip.Via("foo.bar", rport=None)
        self.assertEqual(v.toString(), "SIP/2.0/UDP foo.bar:5060;rport")
        self.assertEqual(v.rportRequested, True)
        self.assertEqual(v.rportValue, None)


    def test_rportValue(self):
        """
        An rport numeric setting should insert the parameter with the number
        value given.
        """
        v = sip.Via("foo.bar", rport=1)
        self.assertEqual(v.toString(), "SIP/2.0/UDP foo.bar:5060;rport=1")
        self.assertEqual(v.rportRequested, False)
        self.assertEqual(v.rportValue, 1)
        self.assertEqual(v.rport, 1)


    def testNAT(self):
        s = "SIP/2.0/UDP 10.0.0.1:5060;received=22.13.1.5;rport=12345"
        v = sip.parseViaHeader(s)
        self.assertEquals(v.transport, "UDP")
        self.assertEquals(v.host, "10.0.0.1")
        self.assertEquals(v.port, 5060)
        self.assertEquals(v.received, "22.13.1.5")
        self.assertEquals(v.rport, 12345)
        
        self.assertNotEquals(v.toString().find("rport=12345"), -1)


    def test_unknownParams(self):
       """
       Parsing and serializing Via headers with unknown parameters should work.
       """
       s = "SIP/2.0/UDP example.com:5060;branch=a12345b;bogus;pie=delicious"
       v = sip.parseViaHeader(s)
       self.assertEqual(v.toString(), s)



class URLTestCase(unittest.TestCase):

    def testRoundtrip(self):
        for url in [
            "sip:j.doe@big.com",
            "sip:j.doe:secret@big.com;transport=tcp",
            "sip:j.doe@big.com?subject=project",
            "sip:example.com",
            ]:
            self.assertEquals(sip.parseURL(url).toString(), url)

    def testComplex(self):
        s = ("sip:user:pass@hosta:123;transport=udp;user=phone;method=foo;"
             "ttl=12;maddr=1.2.3.4;blah;goo=bar?a=b&c=d")
        url = sip.parseURL(s)
        for k, v in [("username", "user"), ("password", "pass"),
                     ("host", "hosta"), ("port", 123),
                     ("transport", "udp"), ("usertype", "phone"),
                     ("method", "foo"), ("ttl", 12),
                     ("maddr", "1.2.3.4"), ("other", ["blah", "goo=bar"]),
                     ("headers", {"a": "b", "c": "d"})]:
            self.assertEquals(getattr(url, k), v)


class ParseTestCase(unittest.TestCase):

    def testParseAddress(self):
        for address, name, urls, params in [
            ('"A. G. Bell" <sip:foo@example.com>', "A. G. Bell", "sip:foo@example.com", {}),
            ("Anon <sip:foo@example.com>", "Anon", "sip:foo@example.com", {}),
            ("sip:foo@example.com", "", "sip:foo@example.com", {}),
            ("<sip:foo@example.com>", "", "sip:foo@example.com", {}),
            ("foo <sip:foo@example.com>;tag=bar;foo=baz", "foo", "sip:foo@example.com", {"tag": "bar", "foo": "baz"}),
            ]:
            gname, gurl, gparams = sip.parseAddress(address)
            self.assertEquals(name, gname)
            self.assertEquals(gurl.toString(), urls)
            self.assertEquals(gparams, params)


class DummyLocator:
    implements(sip.ILocator)
    def getAddress(self, logicalURL):
        return defer.succeed(sip.URL("server.com", port=5060))

class FailingLocator:
    implements(sip.ILocator)
    def getAddress(self, logicalURL):
        return defer.fail(LookupError())



def parseMessage(msg):
    """
    Parse a single SIP message.
    """
    ms = []
    p = sip.MessagesParser(ms.append)
    p.dataReceived(msg)
    p.dataDone()
    return ms[0]


alice500response = """\
SIP/2.0 500 Internal Server Error\r
Via: SIP/2.0/UDP client.com:5060;branch=z9hG4bK74bf9\r
From: Alice <sip:alice@proxy1.org>;tag=9fxced76sl\r
To: Bob <sip:bob@proxy2.org>\r
Call-ID: 3848276298220188511@client.com\r
CSeq: 1 INVITE\r
\r
"""

class TransportTestCase(unittest.TestCase):
    """
    Tests for the SIP transport layer.
    """
    testAddr = ('169.254.0.1', 5060)


    def test_newRequestReceived(self):
        """
        When the transport receives a request for which there is no existing
        transaction, it should call C{requestReceived} on the transaction user.
        """
        clock = Clock()
        requestsReceived = []
        class TU(object):
            def requestReceived(tu, m, addr):
                requestsReceived.append((m, addr))

        t = sip.SIPTransport(TU(), ['example.org'], 5060, clock)
        t.datagramReceived(registerRequest2, self.testAddr)
        self.assertTrue(len(requestsReceived), 1)
        (m, addr) = requestsReceived[0]
        self.assertEqual(addr, self.testAddr)
        self.assertIsInstance(m, sip.Request)
        via = sip.parseViaHeader(m.headers['via'][0])
        self.assertEqual(via.received, self.testAddr[0])
        self.assertEqual(via.rport, self.testAddr[1])


    def test_oldStyleRequestRetransmissionReceived(self):
        """
        When the transport receives a non-INVITE request with no 'branch'
        parameter in its Via header for which a server transaction has been
        created by the transaction user, it should call C{messageReceived} on
        the correct server transaction.
        """
        clock = Clock()
        messageReceivedCalled = []
        class StubServerTransaction(object):
            def messageReceived(st, msg):
                messageReceivedCalled.append(st)
                self.assertIsInstance(msg, sip.Request)
            def messageReceivedFromTU(st, msg):
                pass

        class TU(object):
            def requestReceived(tu, m, addr):
                return StubServerTransaction()

        t = sip.SIPTransport(TU(), ['example.org'], 5060, clock)
        t.datagramReceived(registerRequest, self.testAddr)
        self.assertEqual(len(messageReceivedCalled), 0)
        t.datagramReceived(registerRequest, self.testAddr)
        self.assertEqual(len(messageReceivedCalled), 1)
        t.datagramReceived(oldStyleInvite, self.testAddr)
        self.assertEqual(len(messageReceivedCalled), 1)
        self.assertEqual(len(t._oldStyleServerTransactions), 2)

    def test_oldStyleInviteRequestRetransmissionReceived(self):
        """
        When the transport receives an INVITE request without an RFC
        3261-complient 'branch' parameter in its Via header for which a server
        transaction has been created by the transaction user, it should call
        C{messageReceived} on the server transaction.
        """
        clock = Clock()
        messageReceivedCalled = [False]
        class StubServerTransaction(object):
            def messageReceived(st, msg):
                messageReceivedCalled[0] = True
                self.assertIsInstance(msg, sip.Request)
            def messageReceivedFromTU(st, msg):
                pass

        class TU(object):
            def requestReceived(tu, m, addr):
                return StubServerTransaction()

        t = sip.SIPTransport(TU(), ['example.org'], 5060, clock)
        t.datagramReceived(oldStyleInvite, self.testAddr)
        self.assertFalse(messageReceivedCalled[0])
        t.datagramReceived(oldStyleInvite, self.testAddr)
        self.assertTrue(messageReceivedCalled[0])
        t.datagramReceived(registerRequest, self.testAddr)
        self.assertEqual(len(t._oldStyleServerTransactions), 2)


    def test_oldStyleAckRequestRetransmissionReceived(self):
        """
        When the transport receives an ACK for a response to an INVITE request
        without an RFC 3261-compliant 'branch' parameter in its Via header for
        which a server transaction has been created by the transaction user, it
        should call C{messageReceived} on the server transaction.
        """
        clock = Clock()
        messageReceivedCalled = [False]
        class StubServerTransaction(object):
            _lastResponse = None
            def messageReceived(st, msg):
                messageReceivedCalled[0] = True
                self.assertIsInstance(msg, sip.Request)
            def messageReceivedFromTU(st, msg):
                st._lastResponse = msg

        class TU(object):
            def requestReceived(tu, m, addr):
                return StubServerTransaction()

        t = sip.SIPTransport(TU(), ['example.org'], 5060, clock)
        t.datagramReceived(oldStyleInvite, self.testAddr)
        self.assertFalse(messageReceivedCalled[0])
        response = parseMessage(alice487)
        t._oldStyleServerTransactions[0][0].messageReceivedFromTU(response)
        t.datagramReceived(oldStyleAck, self.testAddr)
        self.assertTrue(messageReceivedCalled[0])


    def test_requestRetransmissionReceived(self):
        """
        When the transport receives a request for which a server transaction
        has been created by the transaction user, it should call
        C{messageReceived} on the server transaction.
        """
        clock = Clock()
        messageReceivedCalled = [False]
        class StubServerTransaction(object):
            def messageReceived(st, msg):
                messageReceivedCalled[0] = True
                self.assertIsInstance(msg, sip.Request)
        class TU(object):
            def requestReceived(tu, m, addr):
                return StubServerTransaction()

        t = sip.SIPTransport(TU(), ['example.org'], 5060, clock)
        t.datagramReceived(registerRequest2, self.testAddr)
        self.assertFalse(messageReceivedCalled[0])
        t.datagramReceived(registerRequest2, self.testAddr)
        self.assertTrue(messageReceivedCalled[0])


    def test_uniqueBranchCreation(self):
        """
        Branch values computed for requests are unique.
        """
        req = parseMessage(registerRequest)
        self.assertNotEqual(req.computeBranch(),
                            req.computeBranch())


    def test_ackMatching(self):
        """
        ACK requests match server transactions started with INVITE requests.
        """
        clock = Clock()
        methods = []
        class StubServerTransaction(object):
            def messageReceived(st, msg):
                methods.append(msg.method)
            def messageReceivedFromTU(st, msg):
                pass
        class TU(object):
            def requestReceived(tu, msg, addr):
                methods.append(msg.method)
                return StubServerTransaction()
        t = sip.SIPTransport(TU(), ['example.org'], 5060, clock)
        t.sendResponse = lambda r: None
        t.datagramReceived(aliceInvite, self.testAddr)
        t.datagramReceived(alice487Ack, self.testAddr)
        self.assertEqual(methods, ['INVITE', 'ACK'])


    def test_handlerFailure(self):
        """
        If the transaction user raises anything other than a L{sip.SIPError} in
        its L{requestReceived} method, the transport should create a server
        transaction with a 500 error code.
        """
        clock = Clock()
        responses = []
        class TU(object):
            def requestReceived(tu, msg, addr):
                raise RuntimeError("some bad stuff")

        t = sip.SIPTransport(TU(), ['example.org'], 5060, clock)
        t.sendResponse = lambda r: responses.append(r)
        t.datagramReceived(aliceInvite, self.testAddr)
        self.assertEqual(responses[0].code, sip.INTERNAL_ERROR)



    def test_errorCode(self):
        """
        If the transaction user raises an L{sip.SIPError} in its
        C{requestReceived} method, the error code from the raised error is used
        in the response.
        """
        clock = Clock()
        responses = []
        class TU(object):
            def requestReceived(tu, msg, addr):
                raise sip.SIPError(sip.NOT_FOUND)

        t = sip.SIPTransport(TU(), ['example.org'], 5060, clock)
        t.sendResponse = lambda r: responses.append(r)
        t.datagramReceived(aliceInvite, self.testAddr)
        self.assertEqual(responses[0].code, sip.NOT_FOUND)


    def test_responseFromRequest(self):
        """
        L{sip.Response.fromRequest} creates a L{sip.Response} that's a valid
        response to a L{sip.Request}.
        """
        r = sip.Response.fromRequest(sip.INTERNAL_ERROR,
                                    parseMessage(aliceInvite))
        self.assertEqual(r.headers, parseMessage(alice500response).headers)



    def test_initialTrying(self):
        """
        When the TU creates a L{ServerInviteTransaction}, the transport sends a
        "100 Trying" response.
        """
        clock = Clock()
        sent = []
        class TU(object):
            def requestReceived(tu, msg, addr):
                return sip.ServerInviteTransaction(self.siptransport,
                                                   tu, clock)
        self.siptransport = sip.SIPTransport(TU(), ['example.org'], 5060, clock)
        self.siptransport.sendResponse = lambda r: sent.append(r)
        self.siptransport.datagramReceived(aliceInvite, self.testAddr)
        self.assertEqual(sent[0].code, 100)


    def test_sendRequest(self):
        """
        Requests sent by client transactions have the transport address added
        to their Via header and are sent to the correct address.
        """
        fdt = FakeDatagramTransport()
        clock = Clock()
        request = parseMessage(registerRequest)
        tu = StubTransactionUser()
        destAddr = ('169.254.0.1', 5060)
        siptransport = sip.SIPTransport(tu, ['example.org'], 5065, clock)
        siptransport.transport = fdt
        ct = sip.ClientTransaction(siptransport, tu, request,
                                   destAddr, clock)
        self.assertEqual(len(fdt.written), 1)
        self.assertEqual(fdt.written[0][1], destAddr)
        sentRequest = parseMessage(fdt.written[0][0])
        self.assertEqual(len(sentRequest.headers['via']), 2)
        via = sip.parseViaHeader(sentRequest.headers['via'][0])
        self.assertEqual(via.host, 'example.org')
        self.assertEqual(via.port, 5065)
        self.assertEqual(via.branch, ct.branch)


    def test_responseReceived(self):
        """
        Responses received from the network are delivered to the client
        transactions that sent the requests they respond to.
        """
        received = []
        clock = Clock()
        tu = StubTransactionUser()
        transport = sip.SIPTransport(tu, ['192.168.1.100'], 50609, clock)
        class StubClientTransaction:
            request = parseMessage(registerRequest2)
            def messageReceived(ct, msg):
                received.append(msg)

        transport._clientTransactions["z9hG4bK74bf9"] = StubClientTransaction()
        transport.datagramReceived(challengeResponse2, ("127.0.0.2", 5060))
        self.assertEqual(len(received), 1)


    def test_dropMisdirectedResponses(self):
        """
        Responses whose top Via header sent-by info does not match the
        transport's host/port are silently dropped.
        """
        received = []
        clock = Clock()
        tu = StubTransactionUser()
        transport = sip.SIPTransport(tu, ['example.org'], 5065, clock)
        class StubClientTransaction:
            request = parseMessage(registerRequest2)
            def messageReceived(ct, msg):
                received.append(msg)

        transport._clientTransactions["z9hG4bK74bf9"] = StubClientTransaction()
        transport.datagramReceived(challengeResponse2, ("127.0.0.2", 5060))
        self.assertEqual(len(received), 0)


    def test_noTransactionResponses(self):
        """
        Responses that do not match any client transaction are delivered to the
        TU.
        """
        received = []
        clock = Clock()
        tu = StubTransactionUser()
        tu.responseReceived = lambda msg, ct: received.append(msg)
        transport = sip.SIPTransport(tu, ['192.168.1.100'], 50609, clock)
        transport.datagramReceived(challengeResponse2, ("127.0.0.2", 5060))
        self.assertEqual(len(received), 1)


    def test_sendResponse(self):
        """
        Responses sent via the transport are delivered to the 'received'
        address in their Via headers, if one exists.
        """
        fdt = FakeDatagramTransport()
        clock = Clock()
        request = parseMessage(registerRequest)
        tu = StubTransactionUser()
        siptransport = sip.SIPTransport(tu, ['example.org'], 5065, clock)
        siptransport.transport = fdt
        siptransport.sendResponse(parseMessage(challengeResponse2))
        siptransport.sendResponse(parseMessage(alice487))
        self.assertEqual(len(fdt.written), 2)
        self.assertEqual(fdt.written[0][1], ('127.0.0.1', 5632))
        self.assertEqual(fdt.written[1][1], ('client.com', 5060))


    def test_messageTooBig(self):
        """
        Until TCP support is added, sending a message larger than 1300 bytes
        raises C{NotImplementedError}.
        """
        siptransport = sip.SIPTransport(None, ['example.org'], 5065, None)
        request = parseMessage(registerRequest2)
        request.body = "x" * 1300
        response = parseMessage(challengeResponse2)
        response.body = "x" * 1300
        self.assertRaises(NotImplementedError,
                          siptransport.sendResponse, response)
        self.assertRaises(NotImplementedError,
                          siptransport.sendRequest, request, self.testAddr)


class StubTransport(object):
    """
    Stub for L{sip.SIPTransport}.
    """
    reliable = False
    def __init__(self, sent):
        """
        @param sent: A list to append written L{sip.Response}s to.
        """
        self.sent = sent
        self._clientTransactions = {}

    def sendResponse(self, msg):
        """
        @see L{sip.SIPTransport.sendResponse}
        """
        self.sent.append(msg)


    def sendRequest(self, msg, target):
        """
        @see L{sip.SIPTransport.sendRequest}
        """
        self.sent.append(msg)


    def isReliable(self):
        """
        @see L{sip.SIPTransport.isReliable}
        """
        return self.reliable

    def serverTransactionTerminated(self, st):
        """
        @see L{sip.SIPTransport.serverTransactionTerminated}
        """
        pass



class ServerTransactionTestCase(unittest.TestCase):
    """
    Tests for L{sip.ServerTransaction}.
    """

    def test_ignoreRetransmissions(self):
        """
        When in the initial "trying" state, retransmissions are ignored.
        """
        msg = parseMessage(registerRequest2)
        tu = StubTransactionUser()
        st = sip.ServerTransaction(None, tu, None)
        self.assertEqual(st._mode, 'trying')
        st.messageReceived(msg)
        self.assertEqual(st._mode, 'trying')


    def test_enterProceeding(self):
        """
        When a provisional response is received from the TU, switch to the
        "proceeding" state and send the response to the transport. Send any
        further provisional responses received to the transport as well.
        """
        sent = []
        req = parseMessage(registerRequest2)
        response = sip.Response.fromRequest(sip.TRYING, req)
        st = sip.ServerTransaction(StubTransport(sent), None, None)
        st.messageReceivedFromTU(response)
        self.assertEqual(st._mode, 'proceeding')
        st.messageReceivedFromTU(response)
        self.assertEqual(st._mode, 'proceeding')
        self.assertEqual(sent, [response, response])


    def test_retransmissionProceeding(self):
        """
        If a retransmission of the request is received while in the
        "proceeding" state, the most recently sent provisional response is
        passed to the transport layer for retransmission.
        """
        sent = []
        req = parseMessage(registerRequest2)
        response = sip.Response.fromRequest(sip.TRYING, req)

        st = sip.ServerTransaction(StubTransport(sent), None, None)
        st.messageReceivedFromTU(response)
        st.messageReceived(req)
        self.assertEqual(sent, [response, response])


    def test_finalProceeding(self):
        """
        If the TU passes a final response to the server transaction while in
        the "proceeding" state, the transaction enters the "completed" state,
        and the response is passed to the transport layer for transmission.
        """
        clock = Clock()
        sent = []
        req = parseMessage(registerRequest2)
        response1 = sip.Response.fromRequest(sip.TRYING, req)
        response2 = sip.Response.fromRequest(sip.UNAUTHORIZED, req)
        st = sip.ServerTransaction(StubTransport(sent), None, clock)
        st.messageReceivedFromTU(response1)
        st.messageReceivedFromTU(response2)
        self.assertEqual(st._mode, 'completed')
        self.assertEqual(sent, [response1, response2])


    def test_finalTrying(self):
        """
        If the TU passes a final response to the server transaction while in
        the "trying" state, the transaction enters the "completed" state, and
        the response is passed to the transport layer for transmission.
        """
        clock = Clock()
        sent = []
        req = parseMessage(registerRequest2)
        response = sip.Response.fromRequest(sip.UNAUTHORIZED, req)
        st = sip.ServerTransaction(StubTransport(sent), None, clock)
        st.messageReceivedFromTU(response)
        self.assertEqual(st._mode, 'completed')
        self.assertEqual(sent, [response])


    def test_timerJ(self):
        """
        When the server transaction enters the "completed" state, it
        transitions to "terminated" after 64*_T1 seconds for unreliable
        transports, and immediately for reliable transports.
        """
        clock = Clock()
        reliableTransport = StubTransport([])
        reliableTransport.reliable = True
        unreliableTransport = StubTransport([])
        unreliableTransport.reliable = False
        tu = StubTransactionUser()
        st = sip.ServerTransaction(unreliableTransport, tu, clock)
        st._complete()
        self.assertEqual(st._mode, 'completed')
        clock.advance(64*sip._T1)
        self.assertEqual(st._mode, 'terminated')
        st2 = sip.ServerTransaction(reliableTransport, StubTransactionUser(),
                                    clock)
        st2._complete()
        self.assertEqual(st2._mode, 'terminated')


    def test_completedRetransmission(self):
        """
        While in the "completed" state, the server transaction must pass the
        final response to the transport layer for retransmission whenever a
        retransmission of the request is received.
        """
        clock = Clock()
        sent = []
        req = parseMessage(registerRequest2)
        response = sip.Response.fromRequest(sip.UNAUTHORIZED, req)
        st = sip.ServerTransaction(StubTransport(sent), None, clock)
        st.messageReceivedFromTU(response)
        st.messageReceived(req)
        self.assertEqual(sent, [response, response])


    def test_completedIgnoreMoreResponses(self):
        """
        Any other final responses passed by the TU to the server transaction
        are discarded when in the "completed" state.
        """
        clock = Clock()
        sent = []
        req = parseMessage(registerRequest2)
        response = sip.Response.fromRequest(sip.UNAUTHORIZED, req)
        response2 = sip.Response.fromRequest(sip.INTERNAL_ERROR, req)
        st = sip.ServerTransaction(StubTransport(sent), None, clock)
        st.messageReceivedFromTU(response)
        st.messageReceivedFromTU(response2)
        self.assertEqual(sent, [response])


    def test_terminated(self):
        """
        A terminated transaction raises an error when it receives any kind of
        message.
        """
        terminated = []
        req = parseMessage(registerRequest)
        response = sip.Response.fromRequest(sip.UNAUTHORIZED, req)
        t = StubTransport([])
        t.serverTransactionTerminated = lambda st: terminated.append(st)
        st = sip.ServerTransaction(t, None, None)
        st._terminate()
        self.assertRaises(RuntimeError, st.messageReceived, req)
        self.assertRaises(RuntimeError, st.messageReceivedFromTU, response)
        self.assertEqual(terminated, [st])


class ServerInviteTransactionTestCase(unittest.TestCase):
    """
    Tests for L{sip.ServerInviteTransaction}.
    """
    def test_initialTrying(self):
        """
        The initial state is "proceeding".
        """
        st = sip.ServerInviteTransaction(None, None, None)
        self.assertEqual(st._mode, 'proceeding')


    def test_provisionalProceeding(self):
        """
        When in the "proceeding" state, any provisional responses from the TU
        are passed to the transport.
        """
        sent = []
        req = parseMessage(aliceInvite)
        st = sip.ServerInviteTransaction(StubTransport(sent), None, None)
        response = sip.Response.fromRequest(sip.RINGING, req)
        st.messageReceivedFromTU(response)
        self.assertIdentical(sent[0], response)


    def test_retransmissionProceeding(self):
        """
        When in the "proceeding" state, request retransmissions are responded
        to with the most recent provisional response.
        """
        sent = []
        req = parseMessage(aliceInvite)
        st = sip.ServerInviteTransaction(StubTransport(sent), None, None)
        trying = sip.Response.fromRequest(sip.TRYING, req)
        st.messageReceivedFromTU(trying)
        st.messageReceived(req)
        ringing = sip.Response.fromRequest(sip.RINGING, req)
        st.messageReceivedFromTU(ringing)
        st.messageReceived(req)
        self.assertEquals(sent, [trying, trying, ringing, ringing])


    def test_2xxProceeding(self):
        """
        When in the "proceeding" state, 2xx responses from the TU are passed to
        the transport and immediately terminate the transaction.
        """
        sent = []
        req = parseMessage(aliceInvite)
        tu = StubTransactionUser()
        st = sip.ServerInviteTransaction(StubTransport(sent), tu, None)
        ok = sip.Response.fromRequest(sip.OK, req)
        st.messageReceivedFromTU(ok)
        self.assertIdentical(sent[0], ok)
        self.assertEquals(st._mode, 'terminated')


    def test_finalProceeding(self):
        """
        When in the "proceeding" state, any other final response (3xx-6xx) from
        the TU is passed to the transport and puts the transaction in the
        "completed" state.
        """
        sent = []
        req = parseMessage(aliceInvite)
        st = sip.ServerInviteTransaction(StubTransport(sent), None, Clock())
        ok = sip.Response.fromRequest(sip.UNAUTHORIZED, req)
        st.messageReceivedFromTU(ok)
        self.assertIdentical(sent[0], ok)
        self.assertEquals(st._mode, 'completed')


    def test_timerG(self):
        """
        When in the "proceeding" state, a non-success final response sent over
        an unreliable transport is repeatedly retransmitted after
        C{min((2**n)*_T1, _T2)} seconds, where C{n} is the number of previous
        retransmissions.
        """
        clock = Clock()
        unreliableTransport = StubTransport([])
        unreliableTransport.reliable = False
        sent = []
        req = parseMessage(aliceInvite)
        st = sip.ServerInviteTransaction(StubTransport(sent), None, clock)
        ok = sip.Response.fromRequest(sip.UNAUTHORIZED, req)
        st.messageReceivedFromTU(ok)
        clock.advance(sip._T1)
        self.assertEquals(sent, 2 * [ok])
        clock.advance(3 * sip._T1)
        self.assertEquals(sent, 2 * [ok])
        clock.advance(sip._T1)
        self.assertEquals(sent, 3 * [ok])
        clock.advance(7 * sip._T1)
        self.assertEquals(sent, 3 * [ok])
        clock.advance(sip._T1)
        self.assertEquals(sent, 4 * [ok])
        clock.advance(sip._T2)
        self.assertEquals(sent, 5 * [ok])
        clock.advance(sip._T2)
        self.assertEquals(sent, 6 * [ok])
        clock.advance(sip._T2)
        self.assertEquals(sent, 7 * [ok])


    def test_noReliableTimerG(self):
        """
        Timer G is not set to fire on reliable transports.
        """
        clock = Clock()
        sent = []
        reliableTransport = StubTransport(sent)
        reliableTransport.reliable = True
        req = parseMessage(aliceInvite)
        tu = StubTransactionUser()
        st = sip.ServerInviteTransaction(reliableTransport, tu, clock)
        st.messageReceivedFromTU(sip.Response.fromRequest(sip.UNAUTHORIZED,
                                                          req))
        clock.advance(64*sip._T1)
        self.assertEqual(len(sent), 1)


    def test_timerH(self):
        """
        When the 'completed' state is entered, a timer is set for transitioning
        to the 'terminated' state if the state is still 'completed' after 64*_T1
        seconds.
        """
        clock = Clock()
        sent = []
        req = parseMessage(aliceInvite)
        tu = StubTransactionUser()
        st = sip.ServerInviteTransaction(StubTransport(sent), tu, clock)
        ok = sip.Response.fromRequest(sip.UNAUTHORIZED, req)
        st.messageReceivedFromTU(ok)
        clock.advance(64*sip._T1)
        self.assertEqual(st._mode, 'terminated')


    def test_retransmissionCompleted(self):
        """
        When in the "completed" state, request retransmissions are responded
        to with the final response.
        """
        clock = Clock()
        sent = []
        req = parseMessage(aliceInvite)
        st = sip.ServerInviteTransaction(StubTransport(sent), None, clock)
        unauthorized = sip.Response.fromRequest(sip.UNAUTHORIZED, req)
        st.messageReceivedFromTU(unauthorized)
        st.messageReceived(req)
        self.assertEquals(st._mode, 'completed')
        self.assertEquals(sent, 2 * [unauthorized])


    def test_ackReceipt(self):
        """
        Receipt of an ACK changes the state to 'confirmed' and ends
        retransmissions of the response. Further ACKs do not result in any
        activity.
        """
        clock = Clock()
        sent = []
        req = parseMessage(aliceInvite)
        tu = StubTransactionUser()
        st = sip.ServerInviteTransaction(StubTransport(sent), tu, clock)
        err = sip.Response.fromRequest(sip.REQUEST_TERMINATED, req)
        st.messageReceivedFromTU(err)
        ack = parseMessage(alice487Ack)
        st.messageReceived(ack)
        self.assertEquals(st._mode, 'confirmed')
        st.messageReceived(ack)
        st.messageReceived(ack)
        st.clock.advance(64*sip._T1)
        self.assertEquals(len(sent), 1)


    def test_timerI(self):
        """
        Upon entering the 'confirmed' state, the transaction transitions to the
        'terminated' state after C{_T4} seconds for unreliable transports.
        """
        clock = Clock()
        sent = []
        req = parseMessage(aliceInvite)
        tu = StubTransactionUser()
        st = sip.ServerInviteTransaction(StubTransport(sent), tu, clock)
        err = sip.Response.fromRequest(sip.REQUEST_TERMINATED, req)
        st.messageReceivedFromTU(err)
        ack = parseMessage(alice487Ack)
        st.messageReceived(ack)
        st.clock.advance(sip._T4)
        self.assertEquals(st._mode, 'terminated')


    def test_noReliableTimerI(self):
        """
        Upon entering the 'confirmed' state, the transaction immediately
        transitions to 'terminated'.
        """
        clock = Clock()
        sent = []
        req = parseMessage(aliceInvite)
        t = StubTransport(sent)
        t.reliable = True
        tu = StubTransactionUser()
        st = sip.ServerInviteTransaction(t, tu, clock)
        err = sip.Response.fromRequest(sip.REQUEST_TERMINATED, req)
        st.messageReceivedFromTU(err)
        ack = parseMessage(alice487Ack)
        st.messageReceived(ack)
        st.clock.advance(sip._T4)
        self.assertEquals(st._mode, 'terminated')


    def test_terminated(self):
        """
        A terminated transaction raises an error when it receives any kind of
        message.
        """
        terminated = []
        req = parseMessage(aliceInvite)
        response = sip.Response.fromRequest(sip.UNAUTHORIZED, req)
        t = StubTransport([])
        t.serverTransactionTerminated = lambda st: terminated.append(st)
        st = sip.ServerInviteTransaction(t, None, None)
        st._terminate()
        self.assertRaises(RuntimeError, st.messageReceived, req)
        self.assertRaises(RuntimeError, st.messageReceivedFromTU, response)
        self.assertEqual(terminated, [st])



class StubTransactionUser(object):
    def clientTransactionTerminated(self, ct):
        pass

    def responseReceived(self, response, ct):
        pass


class ClientTransactionTestCase(unittest.TestCase):
    """
    Tests for L{sip.ClientTransaction}.
    """

    testAddr = ('169.254.0.1', 5060)

    def setUp(self):
        """
        Create a L{sip.ClientTransaction} from an INVITE message.
        """
        self.clock = Clock()
        self.sent = []
        self.transport = StubTransport(self.sent)
        self.request = parseMessage(registerRequest)
        self.tu = StubTransactionUser()
        self.ct = sip.ClientTransaction(self.transport, self.tu,
                                        self.request,
                                        self.testAddr,
                                        self.clock)

    def test_initialState(self):
        """
        The initial state is 'trying', and the request is passed to the
        transport layer when the transaction is created.
        """
        self.assertEquals(self.ct._mode, 'trying')
        self.assertEquals(self.sent, [self.request])


    def test_addedViaHeader(self):
        """
        A C{Via} header is added to the request before it's sent to the
        transport, with the branch parameter generated by this transaction.
        """
        self.assertEquals(len(self.request.headers['via']), 2)
        self.assertEquals(sip.parseViaHeader(
                self.request.headers['via'][0]).branch,
                          self.ct.branch)


    def test_timerETrying(self):
        """
        While in the 'trying' state, on unreliable transports, the request
        should be retransmitted after C{min((2**n)*_T1, _T2)} seconds, where
        C{n} is the number of previous retransmissions.
        """
        self.clock.advance(sip._T1)
        self.assertEquals(self.sent, 2 * [self.request])
        self.clock.advance(3 * sip._T1)
        self.assertEquals(self.sent, 2 * [self.request])
        self.clock.advance(sip._T1)
        self.assertEquals(self.sent, 3 * [self.request])
        self.clock.advance(7 * sip._T1)
        self.assertEquals(self.sent, 3 * [self.request])
        self.clock.advance(sip._T1)
        self.assertEquals(self.sent, 4 * [self.request])
        self.clock.advance(sip._T2)
        self.assertEquals(self.sent, 5 * [self.request])
        self.clock.advance(sip._T2)
        self.assertEquals(self.sent, 6 * [self.request])
        self.clock.advance(sip._T2)
        self.assertEquals(self.sent, 7 * [self.request])


    def test_timerEProceeding(self):
        """
        While in the 'proceeding' state, on unreliable transports, the request
        should be retransmitted after _T2 seconds. (The first retransmission is
        after _T1 seconds, since it is scheduled while the transaction is in the
        'trying' state.)
        """
        response = sip.Response.fromRequest(sip.TRYING, self.request)
        self.tu.responseReceived = lambda msg, ct: None
        self.ct.messageReceived(response)
        self.clock.advance(sip._T1)
        numResponses = 2
        self.clock.advance(sip._T2 - sip._T1)
        while self.clock.seconds() < 64*sip._T1:
            self.assertEquals(self.sent, numResponses * [self.request])
            numResponses += 1
            self.clock.advance(sip._T1)
            self.assertEquals(self.sent, numResponses * [self.request])
            self.clock.advance(sip._T2 - sip._T1)


    def test_noReliableTimerE(self):
        """
        For reliable transports, no request retransmission should be done.
        """
        sent = []
        rcvd = []
        def responseReceived(msg, ct):
            self.assertEqual(msg.code, sip.TIMEOUT)
            rcvd.append(msg)
        self.tu.responseReceived = responseReceived
        transport = StubTransport(sent)
        transport.reliable = True
        self.ct = sip.ClientTransaction(transport, self.tu,
                                        self.request,
                                        self.testAddr,
                                        self.clock)
        self.clock.advance(64 * sip._T1)
        self.assertEquals(sent, [self.request])


    def test_timerF(self):
        """
        If still in the 'trying' state after 64*_T1 seconds, the TU should be
        informed of a timeout, the transaction should terminate, and no ACK
        should be sent.
        """
        rcvd = []
        def responseReceived(msg, ct):
            self.assertEqual(msg.code, sip.TIMEOUT)
            self.assertEqual(ct, self.ct)
            rcvd.append(msg)
        self.tu.responseReceived = responseReceived
        self.clock.advance(64 * sip._T1)
        self.assertEqual(len(rcvd), 1)
        self.assertEqual(self.ct._mode, 'terminated')


    def test_provisionalTrying(self):
        """
        When in the 'trying' state, change to 'proceeding' when a provisional
        response is received. The response is passed to the TU.
        """
        rcvd = []
        def responseReceived(msg, ct):
            self.assertEqual(msg.code, sip.TRYING)
            self.assertEqual(ct, self.ct)
            rcvd.append(msg)
        self.tu.responseReceived = responseReceived
        response = sip.Response.fromRequest(sip.TRYING, self.request)
        self.ct.messageReceived(response)
        self.assertEqual(self.ct._mode, 'proceeding')
        self.assertNotEqual(self.ct._timerE, None)
        self.assertNotEqual(self.ct._timerF, None)
        self.assertEqual(rcvd, [response])


    def test_provisionalProceeding(self):
        """
        When in the 'proceeding' state, all provisional response received are
        passed to the TU.
        """
        rcvd = []
        def responseReceived(msg, ct):
            rcvd.append(msg)
        self.tu.responseReceived = responseReceived
        response1 = sip.Response.fromRequest(sip.TRYING, self.request)
        response2 = sip.Response.fromRequest(sip.RINGING, self.request)
        self.ct.messageReceived(response1)
        self.ct.messageReceived(response2)
        self.ct.messageReceived(response2)
        self.assertEqual(self.ct._mode, 'proceeding')
        self.assertNotEqual(self.ct._timerE, None)
        self.assertNotEqual(self.ct._timerF, None)
        self.assertEqual(rcvd, [response1, response2, response2])


    def test_finalTrying(self):
        """
        When in the 'trying' state, receipt of a final response changes the
        state to 'completed', stops timers E and F, and notifies the TU.
        """
        rcvd = []
        def responseReceived(msg, ct):
            rcvd.append(msg)
        self.tu.responseReceived = responseReceived
        response = parseMessage(challengeResponse)
        self.ct.messageReceived(response)
        self.assertEqual(self.ct._mode, 'completed')
        self.assertEqual(self.ct._timerE, None)
        self.assertEqual(self.ct._timerF, None)
        self.assertEqual(rcvd, [response])


    def test_finalProceeding(self):
        """
        When in the 'proceeding' state, receipt of a final response changes the
        state to 'completed', stops timers E and F, and notifies the TU.
        """
        rcvd = []
        def responseReceived(msg, ct):
            rcvd.append(msg)
        self.tu.responseReceived = responseReceived
        response = parseMessage(challengeResponse)
        self.ct.messageReceived(response)
        self.assertEqual(self.ct._mode, 'completed')
        self.assertEqual(self.ct._timerE, None)
        self.assertEqual(self.ct._timerF, None)
        self.assertEqual(rcvd, [response])


    def test_completedIgnoreMoreResponses(self):
        """
        Retransmissions of the response are discarded when in the "completed"
        state.
        """
        rcvd = []
        def responseReceived(msg, ct):
            rcvd.append(msg)
        self.tu.responseReceived = responseReceived
        response = parseMessage(challengeResponse)
        self.ct.messageReceived(response)
        self.ct.messageReceived(response)
        self.ct.messageReceived(response)
        self.assertEqual(len(rcvd), 1)


    def test_timerK(self):
        """
        After entering the 'completed' state, the state should change to
        'terminated' after _T4 seconds.  The TU should also be notified of the
        termination.
        """
        terminated = []
        def clientTransactionTerminated(ct):
            terminated.append(ct)
        self.tu.responseReceived = lambda msg, ct: None
        self.tu.clientTransactionTerminated = clientTransactionTerminated
        self.assertEquals(len(self.transport._clientTransactions), 1)
        response = parseMessage(challengeResponse)
        response = parseMessage(challengeResponse)
        self.ct.messageReceived(response)
        self.clock.advance(sip._T4)
        self.assertEqual(self.ct._mode, 'terminated')
        self.assertEquals(terminated, [self.ct])
        self.assertEquals(len(self.transport._clientTransactions), 0)

    def test_noReliableTimerK(self):
        """
        For reliable transports, receipt of final responses results in
        immediate termination of the transaction.
        """
        sent = []
        self.tu.responseReceived = lambda msg, ct: None
        response = parseMessage(challengeResponse)
        transport = StubTransport(sent)
        transport.reliable = True
        self.ct = sip.ClientTransaction(transport, self.tu,
                                        self.request,
                                        self.testAddr,
                                        self.clock)
        self.ct.messageReceived(response)
        self.assertEqual(self.ct._mode, 'terminated')


    def test_terminated(self):
        """
        When in the 'terminated' state, receipt of any response should raise an
        error.
        """
        self.ct._mode = 'terminated'
        self.tu.responseReceived = lambda msg, ct: None
        response = sip.Response.fromRequest(200, self.request)
        self.assertRaises(RuntimeError, self.ct.messageReceived, response)



class ClientInviteTransactionTestCase(unittest.TestCase):
    """
    Tests for L{sip.ClientInviteTransaction}.
    """
    testAddr = ('169.254.0.1', 5060)

    def setUp(self):
        """
        Create a L{sip.ClientInviteTransaction} from an INVITE message.
        """
        self.clock = Clock()
        self.sent = []
        self.transport = StubTransport(self.sent)
        self.request = parseMessage(aliceInvite)
        self.tu = StubTransactionUser()
        self.ct = sip.ClientInviteTransaction(self.transport, self.tu,
                                              self.request,
                                              self.testAddr,
                                              self.clock)


    def test_initialState(self):
        """
        The initial state is 'calling', and the request is passed to the
        transport layer when the transaction is created.
        """
        self.assertEquals(self.ct._mode, 'calling')
        self.assertEquals(self.sent, [self.request])


    def test_addedViaHeader(self):
        """
        A C{Via} header is added to the request before it's sent to the
        transport, with the branch parameter generated by this transaction.
        """
        self.assertEquals(len(self.request.headers['via']), 2)
        self.assertEquals(self.request.headers['via'][0].branch,
                          self.ct.branch)

    def test_timerA(self):
        """
        While in the 'calling' state, on unreliable transports, the request
        should be retransmitted after _T1 seconds, and after an interval that
        doubles for every subsequent retransmission.
        """
        self.clock.advance(sip._T1)
        self.assertEquals(self.sent, 2 * [self.request])
        self.clock.advance(sip._T1)
        self.assertEquals(self.sent, 2 * [self.request])
        self.clock.advance(sip._T1)
        self.assertEquals(self.sent, 3 * [self.request])
        self.clock.advance(3 * sip._T1)
        self.assertEquals(self.sent, 3 * [self.request])
        self.clock.advance(sip._T1)
        self.assertEquals(self.sent, 4 * [self.request])
        self.clock.advance(7 * sip._T1)
        self.assertEquals(self.sent, 4 * [self.request])
        self.clock.advance(sip._T1)
        self.assertEquals(self.sent, 5 * [self.request])
        self.clock.advance(15 * sip._T1)
        self.assertEquals(self.sent, 5 * [self.request])
        self.clock.advance(sip._T1)
        self.assertEquals(self.sent, 6 * [self.request])
        self.clock.advance(31 * sip._T1)
        self.assertEquals(self.sent, 6 * [self.request])
        self.clock.advance(sip._T1)
        self.assertEquals(self.sent, 7 * [self.request])


    def test_noReliableTimerA(self):
        """
        For reliable transports, no request retransmission should be done.
        """
        sent = []
        rcvd = []
        def responseReceived(msg, ct):
            self.assertEqual(msg.code, sip.TIMEOUT)
            rcvd.append(msg)
        self.tu.responseReceived = responseReceived
        transport = StubTransport(sent)
        transport.reliable = True
        self.ct = sip.ClientInviteTransaction(transport, self.tu,
                                              self.request,
                                              self.testAddr,
                                              self.clock)
        self.clock.advance(64 * sip._T1)
        self.assertEquals(sent, [self.request])


    def test_timerB(self):
        """
        If still in the 'calling' state after 64*_T1 seconds, the TU should be
        informed of a timeout, the transaction should terminate, and no ACK
        should be sent.
        """
        rcvd = []
        def responseReceived(msg, ct):
            self.assertEqual(msg.code, sip.TIMEOUT)
            self.assertEqual(ct, self.ct)
            rcvd.append(msg)
        self.tu.responseReceived = responseReceived
        self.clock.advance(64 * sip._T1)
        self.assertEqual(len(rcvd), 1)
        self.assertEqual(self.ct._mode, 'terminated')


    def test_provisionalCalling(self):
        """
        When in the 'calling' state, change to 'proceeding' when a provisional
        response is received, stopping timers A and B. The response is passed
        to the TU.
        """
        rcvd = []
        def responseReceived(msg, ct):
            self.assertEqual(msg.code, sip.TRYING)
            self.assertEqual(ct, self.ct)
            rcvd.append(msg)
        self.tu.responseReceived = responseReceived
        response = sip.Response.fromRequest(sip.TRYING, self.request)
        self.ct.messageReceived(response)
        self.assertEqual(self.ct._mode, 'proceeding')
        self.assertEqual(self.ct._timerA, None)
        self.assertEqual(self.ct._timerB, None)
        self.assertEqual(rcvd, [response])


    def test_provisionalProceeding(self):
        """
        When in the 'proceeding' state, all provisional response received are
        passed to the TU.
        """
        rcvd = []
        def responseReceived(msg, ct):
            rcvd.append(msg)
        self.tu.responseReceived = responseReceived
        response1 = sip.Response.fromRequest(sip.TRYING, self.request)
        response2 = sip.Response.fromRequest(sip.RINGING, self.request)
        self.ct.messageReceived(response1)
        self.ct.messageReceived(response2)
        self.ct.messageReceived(response2)
        self.assertEqual(rcvd, [response1, response2, response2])


    def _finalResponseAsserts(self, response):
        """
        Assertions for C{test_callingError} and C{test_proceedingError}.
        """
        self.assertEqual(self.ct._mode, 'completed')
        self.assertEqual(self.ct._timerA, None)
        self.assertEqual(self.ct._timerB, None)
        self.assertEqual(self.sent[-1].method, 'ACK')
        ack = self.sent[-1]
        self.assertEquals(ack.headers['from'], self.request.headers['from'])
        self.assertEquals(ack.headers['call-id'],
                          self.request.headers['call-id'])
        self.assertEquals(ack.uri, self.request.uri)
        self.assertEquals(ack.headers['to'], response.headers['to'])
        self.assertEquals(len(ack.headers['via']), 1)
        self.assertEquals(ack.headers['via'][0], self.request.headers['via'][0])
        cseq, cseqMethod = ack.headers['cseq'][0].split(' ')
        self.assertTrue(self.request.headers['cseq'][0].startswith(cseq + ' '))
        self.assertEquals(cseqMethod, 'ACK')
        self.assertEquals(ack.headers['route'], self.request.headers['route'])
        self.clock.advance(32)
        self.assertEquals(self.ct._mode, 'terminated')


    def test_callingError(self):
        """
        When in the 'calling' state, receipt of a non-success final response
        changes the state to 'completed', stops timers A and B, passes the
        response to the TU, starts timer D, and sends an ACK.
        """
        rcvd = []
        def responseReceived(msg, ct):
            rcvd.append(msg)
        self.tu.responseReceived = responseReceived
        response = parseMessage(alice487)
        self.ct.messageReceived(response)
        self._finalResponseAsserts(response)


    def test_proceedingError(self):
        """
        When in the 'proceeding' state, receipt of a non-success final response
        changes the state to 'completed', stops timers A and B, passes the
        response to the TU, starts timer D, and sends an ACK.
        """
        rcvd = []
        def responseReceived(msg, ct):
            rcvd.append(msg)
        self.tu.responseReceived = responseReceived
        response = parseMessage(alice487)
        self.ct.messageReceived(sip.Response.fromRequest(sip.TRYING,
                                                        self.request))
        self.ct.messageReceived(response)
        self._finalResponseAsserts(response)


    def test_reliableNoTimerD(self):
        """
        On reliable transports, timer D fires immediately rather than after 32
        seconds.
        """
        sent = []
        transport = StubTransport(sent)
        transport.reliable = True
        self.ct = sip.ClientInviteTransaction(transport, self.tu,
                                              self.request,
                                              self.testAddr,
                                              self.clock)
        rcvd = []
        def responseReceived(msg, ct):
            rcvd.append(msg)
        self.tu.responseReceived = responseReceived
        response = parseMessage(alice487)
        self.ct.messageReceived(response)
        self.assertEqual(self.ct._mode, 'terminated')


    def test_completedRetransmission(self):
        """
        When in the 'completed' state, retransmissions of the final response
        are responded to with retransmissions of the ACK. The TU is not
        notified.
        """
        rcvd = []
        def responseReceived(msg, ct):
            rcvd.append(msg)
        self.tu.responseReceived = responseReceived
        response = parseMessage(alice487)
        self.ct.messageReceived(response)
        self.ct.messageReceived(response)
        self.ct.messageReceived(response)
        self.assertEqual(len(rcvd), 1)


    def test_callingOK(self):
        """
        When in the 'calling' state, receipt of a success response changes the
        state to 'terminated' and pass the response to the TU. The TU
        should also be notified of the termination.
        """
        terminated = []
        rcvd = []
        def responseReceived(msg, ct):
            rcvd.append(msg)
        def clientTransactionTerminated(ct):
            terminated.append(ct)
        self.tu.clientTransactionTerminated = clientTransactionTerminated
        self.tu.responseReceived = responseReceived
        response = sip.Response.fromRequest(200, self.request)
        self.assertEquals(len(self.transport._clientTransactions), 1)
        self.ct.messageReceived(response)
        self.assertEquals(self.ct._mode, 'terminated')
        self.assertEquals(len(self.transport._clientTransactions), 0)
        self.assertEquals(terminated, [self.ct])
        self.assertEquals(rcvd, [response])


    def test_proceedingOK(self):
        """
        When in the 'proceeding' state, receipt of a success response changes
        the state to 'terminated' and pass the response to the TU. The TU
        should also be notified of the termination.
        """
        terminated = []
        rcvd = []
        def responseReceived(msg, ct):
            rcvd.append(msg)
        def clientTransactionTerminated(ct):
            terminated.append(ct)
        self.tu.responseReceived = responseReceived
        self.tu.clientTransactionTerminated = clientTransactionTerminated
        response = sip.Response.fromRequest(200, self.request)
        self.assertEquals(len(self.transport._clientTransactions), 1)
        self.ct.messageReceived(response)
        self.assertEquals(self.ct._mode, 'terminated')
        self.assertEquals(terminated, [self.ct])
        self.assertEquals(len(self.transport._clientTransactions), 0)
        self.assertEquals(rcvd, [response])


    def test_terminated(self):
        """
        When in the 'terminated' state, receipt of any response should raise an
        error.
        """
        self.ct._mode = 'terminated'
        response = sip.Response.fromRequest(200, self.request)
        self.assertRaises(RuntimeError, self.ct.messageReceived, response)


    def test_cancel(self):
        """
        Calling C{cancel} sends an appropriately constructed CANCEL message to
        the transport in its own transaction.
        """
        ringing = sip.Response.fromRequest(sip.RINGING, self.request)
        self.transport.host = 'client.com'
        self.transport.port = 5060
        self.ct.messageReceived(ringing)
        d = self.ct.cancel()

        def checkCancelMessage(newCT):
            self.assertIsInstance(newCT, sip.ClientTransaction)
            cancelMsg = newCT.request
            self.assertEqual(len(cancelMsg.headers['via']), 1)
            for name in ('to', 'from', 'call-id'):
                self.assertEqual(self.request.headers[name][0],
                                 cancelMsg.headers[name][0])

            cseq, cseqMethod = cancelMsg.headers['cseq'][0].split(' ')
            self.assertEqual(cseq,
                             self.request.headers['cseq'][0].split(' ')[0])
            self.assertEqual(cseqMethod, 'CANCEL')

        d.addCallback(checkCancelMessage)
        return d


class ProxyTestCase(unittest.TestCase):

    def setUp(self):
        self.proxy = sip.Proxy("127.0.0.1")
        self.proxy.locator = DummyLocator()
        self.sent = []
        self.proxy.sendMessage = lambda dest, msg: self.sent.append((dest, msg))
    
    def testRequestForward(self):
        r = sip.Request("INVITE", "sip:foo")
        r.addHeader("via", sip.Via("1.2.3.4").toString())
        r.addHeader("via", sip.Via("1.2.3.5").toString())
        r.addHeader("foo", "bar")
        r.addHeader("to", "<sip:joe@server.com>")
        r.addHeader("contact", "<sip:joe@1.2.3.5>")
        self.proxy.datagramReceived(r.toString(), ("1.2.3.4", 5060))
        self.assertEquals(len(self.sent), 1)
        dest, m = self.sent[0]
        self.assertEquals(dest.port, 5060)
        self.assertEquals(dest.host, "server.com")
        self.assertEquals(m.uri.toString(), "sip:foo")
        self.assertEquals(m.method, "INVITE")
        self.assertEquals(m.headers["via"],
                          ["SIP/2.0/UDP 127.0.0.1:5060",
                           "SIP/2.0/UDP 1.2.3.4:5060",
                           "SIP/2.0/UDP 1.2.3.5:5060"])

    
    def testReceivedRequestForward(self):
        r = sip.Request("INVITE", "sip:foo")
        r.addHeader("via", sip.Via("1.2.3.4").toString())
        r.addHeader("foo", "bar")
        r.addHeader("to", "<sip:joe@server.com>")
        r.addHeader("contact", "<sip:joe@1.2.3.4>")
        self.proxy.datagramReceived(r.toString(), ("1.1.1.1", 5060))
        dest, m = self.sent[0]
        self.assertEquals(m.headers["via"],
                          ["SIP/2.0/UDP 127.0.0.1:5060",
                           "SIP/2.0/UDP 1.2.3.4:5060;received=1.1.1.1"])
        

    def testResponseWrongVia(self):
        # first via must match proxy's address
        r = sip.Response(200)
        r.addHeader("via", sip.Via("foo.com").toString())
        self.proxy.datagramReceived(r.toString(), ("1.1.1.1", 5060))
        self.assertEquals(len(self.sent), 0)
    
    def testResponseForward(self):
        r = sip.Response(200)
        r.addHeader("via", sip.Via("127.0.0.1").toString())
        r.addHeader("via", sip.Via("client.com", port=1234).toString())
        self.proxy.datagramReceived(r.toString(), ("1.1.1.1", 5060))
        self.assertEquals(len(self.sent), 1)
        dest, m = self.sent[0]
        self.assertEquals((dest.host, dest.port), ("client.com", 1234))
        self.assertEquals(m.code, 200)
        self.assertEquals(m.headers["via"], ["SIP/2.0/UDP client.com:1234"])
        
    def testReceivedResponseForward(self):
        r = sip.Response(200)
        r.addHeader("via", sip.Via("127.0.0.1").toString())
        r.addHeader("via", sip.Via("10.0.0.1", received="client.com").toString())
        self.proxy.datagramReceived(r.toString(), ("1.1.1.1", 5060))
        self.assertEquals(len(self.sent), 1)
        dest, m = self.sent[0]
        self.assertEquals((dest.host, dest.port), ("client.com", 5060))
        
    def testResponseToUs(self):
        r = sip.Response(200)
        r.addHeader("via", sip.Via("127.0.0.1").toString())
        l = []
        self.proxy.gotResponse = lambda *a: l.append(a)
        self.proxy.datagramReceived(r.toString(), ("1.1.1.1", 5060))
        self.assertEquals(len(l), 1)
        m, addr = l[0]
        self.assertEquals(len(m.headers.get("via", [])), 0)
        self.assertEquals(m.code, 200)
    
    def testLoop(self):
        r = sip.Request("INVITE", "sip:foo")
        r.addHeader("via", sip.Via("1.2.3.4").toString()) 
        r.addHeader("via", sip.Via("127.0.0.1").toString())
        self.proxy.datagramReceived(r.toString(), ("client.com", 5060))
        self.assertEquals(self.sent, [])

    def testCantForwardRequest(self):
        r = sip.Request("INVITE", "sip:foo")
        r.addHeader("via", sip.Via("1.2.3.4").toString())
        r.addHeader("to", "<sip:joe@server.com>")
        self.proxy.locator = FailingLocator()
        self.proxy.datagramReceived(r.toString(), ("1.2.3.4", 5060))
        self.assertEquals(len(self.sent), 1)
        dest, m = self.sent[0]
        self.assertEquals((dest.host, dest.port), ("1.2.3.4", 5060))
        self.assertEquals(m.code, 404)
        self.assertEquals(m.headers["via"], ["SIP/2.0/UDP 1.2.3.4:5060"])

    def testCantForwardResponse(self):
        pass

    #testCantForwardResponse.skip = "not implemented yet"


class RegistrationTestCase(unittest.TestCase):

    def setUp(self):
        self.proxy = sip.RegisterProxy(host="127.0.0.1")
        self.registry = sip.InMemoryRegistry("bell.example.com")
        self.proxy.registry = self.proxy.locator = self.registry
        self.sent = []
        self.proxy.sendMessage = lambda dest, msg: self.sent.append((dest, msg))

    def tearDown(self):
        for d, uri in self.registry.users.values():
            d.cancel()
        del self.proxy

    def register(self):
        r = sip.Request("REGISTER", "sip:bell.example.com")
        r.addHeader("to", "sip:joe@bell.example.com")
        r.addHeader("contact", "sip:joe@client.com:1234")
        r.addHeader("via", sip.Via("client.com").toString())
        self.proxy.datagramReceived(r.toString(), ("client.com", 5060))
    
    def unregister(self):
        r = sip.Request("REGISTER", "sip:bell.example.com")
        r.addHeader("to", "sip:joe@bell.example.com")
        r.addHeader("contact", "*")
        r.addHeader("via", sip.Via("client.com").toString())
        r.addHeader("expires", "0")
        self.proxy.datagramReceived(r.toString(), ("client.com", 5060))
    
    def testRegister(self):
        self.register()
        dest, m = self.sent[0]
        self.assertEquals((dest.host, dest.port), ("client.com", 5060))
        self.assertEquals(m.code, 200)
        self.assertEquals(m.headers["via"], ["SIP/2.0/UDP client.com:5060"])
        self.assertEquals(m.headers["to"], ["sip:joe@bell.example.com"])
        self.assertEquals(m.headers["contact"], ["sip:joe@client.com:5060"])
        self.failUnless(int(m.headers["expires"][0]) in (3600, 3601, 3599, 3598))
        self.assertEquals(len(self.registry.users), 1)
        dc, uri = self.registry.users["joe"]
        self.assertEquals(uri.toString(), "sip:joe@client.com:5060")
        d = self.proxy.locator.getAddress(sip.URL(username="joe",
                                                  host="bell.example.com"))
        d.addCallback(lambda desturl : (desturl.host, desturl.port))
        d.addCallback(self.assertEquals, ('client.com', 5060))
        return d

    def testUnregister(self):
        self.register()
        self.unregister()
        dest, m = self.sent[1]
        self.assertEquals((dest.host, dest.port), ("client.com", 5060))
        self.assertEquals(m.code, 200)
        self.assertEquals(m.headers["via"], ["SIP/2.0/UDP client.com:5060"])
        self.assertEquals(m.headers["to"], ["sip:joe@bell.example.com"])
        self.assertEquals(m.headers["contact"], ["sip:joe@client.com:5060"])
        self.assertEquals(m.headers["expires"], ["0"])
        self.assertEquals(self.registry.users, {})


    def addPortal(self):
        r = TestRealm()
        p = cred.portal.Portal(r)
        c = cred.checkers.InMemoryUsernamePasswordDatabaseDontUse()
        c.addUser('userXname@127.0.0.1', 'passXword')
        p.registerChecker(c)
        self.proxy.portal = p

    def testFailedAuthentication(self):
        self.addPortal()
        self.register()
        
        self.assertEquals(len(self.registry.users), 0)
        self.assertEquals(len(self.sent), 1)
        dest, m = self.sent[0]
        self.assertEquals(m.code, 401)


    def testBasicAuthentication(self):
        self.addPortal()
        self.proxy.authorizers = self.proxy.authorizers.copy()
        self.proxy.authorizers['basic'] = sip.BasicAuthorizer()

        r = sip.Request("REGISTER", "sip:bell.example.com")
        r.addHeader("to", "sip:joe@bell.example.com")
        r.addHeader("contact", "sip:joe@client.com:1234")
        r.addHeader("via", sip.Via("client.com").toString())
        r.addHeader("authorization", "Basic " + "userXname:passXword".encode('base64'))
        self.proxy.datagramReceived(r.toString(), ("client.com", 5060))
        
        self.assertEquals(len(self.registry.users), 1)
        self.assertEquals(len(self.sent), 1)
        dest, m = self.sent[0]
        self.assertEquals(m.code, 200)

    
    def testFailedBasicAuthentication(self):
        self.addPortal()
        self.proxy.authorizers = self.proxy.authorizers.copy()
        self.proxy.authorizers['basic'] = sip.BasicAuthorizer()

        r = sip.Request("REGISTER", "sip:bell.example.com")
        r.addHeader("to", "sip:joe@bell.example.com")
        r.addHeader("contact", "sip:joe@client.com:1234")
        r.addHeader("via", sip.Via("client.com").toString())
        r.addHeader("authorization", "Basic " + "userXname:password".encode('base64'))
        self.proxy.datagramReceived(r.toString(), ("client.com", 5060))
        
        self.assertEquals(len(self.registry.users), 0)
        self.assertEquals(len(self.sent), 1)
        dest, m = self.sent[0]
        self.assertEquals(m.code, 401)

    def testWrongDomainRegister(self):
        r = sip.Request("REGISTER", "sip:wrong.com")
        r.addHeader("to", "sip:joe@bell.example.com")
        r.addHeader("contact", "sip:joe@client.com:1234")
        r.addHeader("via", sip.Via("client.com").toString())
        self.proxy.datagramReceived(r.toString(), ("client.com", 5060))
        self.assertEquals(len(self.sent), 0)

    def testWrongToDomainRegister(self):
        r = sip.Request("REGISTER", "sip:bell.example.com")
        r.addHeader("to", "sip:joe@foo.com")
        r.addHeader("contact", "sip:joe@client.com:1234")
        r.addHeader("via", sip.Via("client.com").toString())
        self.proxy.datagramReceived(r.toString(), ("client.com", 5060))
        self.assertEquals(len(self.sent), 0)

    def testWrongDomainLookup(self):
        self.register()
        url = sip.URL(username="joe", host="foo.com")
        d = self.proxy.locator.getAddress(url)
        self.assertFailure(d, LookupError)
        return d
    
    def testNoContactLookup(self):
        self.register()
        url = sip.URL(username="jane", host="bell.example.com")
        d = self.proxy.locator.getAddress(url)
        self.assertFailure(d, LookupError)
        return d


class Client(sip.Base):

    def __init__(self):
        sip.Base.__init__(self)
        self.received = []
        self.deferred = defer.Deferred()

    def handle_response(self, response, addr):
        self.received.append(response)
        self.deferred.callback(self.received)


class LiveTest(unittest.TestCase):

    def setUp(self):
        self.proxy = sip.RegisterProxy(host="127.0.0.1")
        self.registry = sip.InMemoryRegistry("bell.example.com")
        self.proxy.registry = self.proxy.locator = self.registry
        self.serverPort = reactor.listenUDP(0, self.proxy, interface="127.0.0.1")
        self.client = Client()
        self.clientPort = reactor.listenUDP(0, self.client, interface="127.0.0.1")
        self.serverAddress = (self.serverPort.getHost().host,
                              self.serverPort.getHost().port)

    def tearDown(self):
        for d, uri in self.registry.users.values():
            d.cancel()
        d1 = defer.maybeDeferred(self.clientPort.stopListening)
        d2 = defer.maybeDeferred(self.serverPort.stopListening)
        return defer.gatherResults([d1, d2])

    def testRegister(self):
        p = self.clientPort.getHost().port
        r = sip.Request("REGISTER", "sip:bell.example.com")
        r.addHeader("to", "sip:joe@bell.example.com")
        r.addHeader("contact", "sip:joe@127.0.0.1:%d" % p)
        r.addHeader("via", sip.Via("127.0.0.1", port=p).toString())
        self.client.sendMessage(sip.URL(host="127.0.0.1", port=self.serverAddress[1]),
                                r)
        d = self.client.deferred
        def check(received):
            self.assertEquals(len(received), 1)
            r = received[0]
            self.assertEquals(r.code, 200)
        d.addCallback(check)
        return d

    def testAmoralRPort(self):
        # rport is allowed without a value, apparently because server
        # implementors might be too stupid to check the received port
        # against 5060 and see if they're equal, and because client
        # implementors might be too stupid to bind to port 5060, or set a
        # value on the rport parameter they send if they bind to another
        # port.
        p = self.clientPort.getHost().port
        r = sip.Request("REGISTER", "sip:bell.example.com")
        r.addHeader("to", "sip:joe@bell.example.com")
        r.addHeader("contact", "sip:joe@127.0.0.1:%d" % p)
        r.addHeader("via", sip.Via("127.0.0.1", port=p, rport=True).toString())
        self.client.sendMessage(sip.URL(host="127.0.0.1", port=self.serverAddress[1]),
                                r)
        d = self.client.deferred
        def check(received):
            self.assertEquals(len(received), 1)
            r = received[0]
            self.assertEquals(r.code, 200)
        d.addCallback(check)
        return d
        

registerRequest = """
REGISTER sip:intarweb.us SIP/2.0\r
Via: SIP/2.0/UDP 192.168.1.100:50609\r
From: <sip:exarkun@intarweb.us:50609>\r
To: <sip:exarkun@intarweb.us:50609>\r
Contact: "exarkun" <sip:exarkun@192.168.1.100:50609>\r
Call-ID: 94E7E5DAF39111D791C6000393764646@intarweb.us\r
CSeq: 9898 REGISTER\r
Expires: 500\r
User-Agent: X-Lite build 1061\r
Content-Length: 0\r
\r
"""

challengeResponse = """\
SIP/2.0 401 Unauthorized\r
Via: SIP/2.0/UDP 192.168.1.100:50609;received=127.0.0.1;rport=5632\r
To: <sip:exarkun@intarweb.us:50609>\r
From: <sip:exarkun@intarweb.us:50609>\r
Call-ID: 94E7E5DAF39111D791C6000393764646@intarweb.us\r
CSeq: 9898 REGISTER\r
WWW-Authenticate: Digest nonce="92956076410767313901322208775",opaque="1674186428",qop-options="auth",algorithm="MD5",realm="intarweb.us"\r
\r
"""

#This one has an RFC3261-compliant 'branch' parameter in the Via header.
registerRequest2 = """
REGISTER sip:intarweb.us SIP/2.0\r
Via: SIP/2.0/UDP 192.168.1.100:50609;branch=z9hG4bK74bf9;rport\r
From: <sip:exarkun@intarweb.us:50609>\r
To: <sip:exarkun@intarweb.us:50609>\r
Contact: "exarkun" <sip:exarkun@192.168.1.100:50609>\r
Call-ID: 94E7E5DAF39111D791C6000393764646@intarweb.us\r
CSeq: 9898 REGISTER\r
Expires: 500\r
User-Agent: X-Lite build 1061\r
Content-Length: 0\r
\r
"""

challengeResponse2 = """\
SIP/2.0 401 Unauthorized\r
Via: SIP/2.0/UDP 192.168.1.100:50609;branch=z9hG4bK74bf9;received=127.0.0.1;rport=5632\r
To: <sip:exarkun@intarweb.us:50609>\r
From: <sip:exarkun@intarweb.us:50609>\r
Call-ID: 94E7E5DAF39111D791C6000393764646@intarweb.us\r
CSeq: 9898 REGISTER\r
WWW-Authenticate: Digest nonce="92956076410767313901322208775",opaque="1674186428",qop-options="auth",algorithm="MD5",realm="intarweb.us"\r
\r
"""

authRequest = """\
REGISTER sip:intarweb.us SIP/2.0\r
Via: SIP/2.0/UDP 192.168.1.100:50609\r
From: <sip:exarkun@intarweb.us:50609>\r
To: <sip:exarkun@intarweb.us:50609>\r
Contact: "exarkun" <sip:exarkun@192.168.1.100:50609>\r
Call-ID: 94E7E5DAF39111D791C6000393764646@intarweb.us\r
CSeq: 9899 REGISTER\r
Expires: 500\r
Authorization: Digest username="exarkun",realm="intarweb.us",nonce="92956076410767313901322208775",response="4a47980eea31694f997369214292374b",uri="sip:intarweb.us",algorithm=MD5,opaque="1674186428"\r
User-Agent: X-Lite build 1061\r
Content-Length: 0\r
\r
"""

okResponse = """\
SIP/2.0 200 OK\r
Via: SIP/2.0/UDP 192.168.1.100:50609;received=127.0.0.1;rport=5632\r
To: <sip:exarkun@intarweb.us:50609>\r
From: <sip:exarkun@intarweb.us:50609>\r
Call-ID: 94E7E5DAF39111D791C6000393764646@intarweb.us\r
CSeq: 9899 REGISTER\r
Contact: sip:exarkun@127.0.0.1:5632\r
Expires: 3600\r
Content-Length: 0\r
\r
"""

class FakeDigestAuthorizer(sip.DigestAuthorizer):
    def generateNonce(self):
        return '92956076410767313901322208775'
    def generateOpaque(self):
        return '1674186428'


class FakeRegistry(sip.InMemoryRegistry):
    """Make sure expiration is always seen to be 3600.

    Otherwise slow reactors fail tests incorrectly.
    """

    def _cbReg(self, reg):
        if 3600 < reg.secondsToExpiry or reg.secondsToExpiry < 3598:
            raise RuntimeError, "bad seconds to expire: %s" % reg.secondsToExpiry
        reg.secondsToExpiry = 3600
        return reg

    def getRegistrationInfo(self, uri):
        return sip.InMemoryRegistry.getRegistrationInfo(self, uri).addCallback(self._cbReg)

    def registerAddress(self, domainURL, logicalURL, physicalURL):
        return sip.InMemoryRegistry.registerAddress(self, domainURL, logicalURL, physicalURL).addCallback(self._cbReg)

class AuthorizationTestCase(unittest.TestCase):
    def setUp(self):
        self.proxy = sip.RegisterProxy(host="intarweb.us")
        self.proxy.authorizers = self.proxy.authorizers.copy()
        self.proxy.authorizers['digest'] = FakeDigestAuthorizer()
        self.registry = FakeRegistry("intarweb.us")
        self.proxy.registry = self.proxy.locator = self.registry
        self.transport = proto_helpers.FakeDatagramTransport()
        self.proxy.transport = self.transport

        r = TestRealm()
        p = cred.portal.Portal(r)
        c = cred.checkers.InMemoryUsernamePasswordDatabaseDontUse()
        c.addUser('exarkun@intarweb.us', 'password')
        p.registerChecker(c)
        self.proxy.portal = p

    def tearDown(self):
        for d, uri in self.registry.users.values():
            d.cancel()
        del self.proxy
    
    def testChallenge(self):
        self.proxy.datagramReceived(registerRequest, ("127.0.0.1", 5632))
        self.assertEquals(
            self.transport.written[-1],
            ((challengeResponse, ("127.0.0.1", 5632)))
        )
        self.transport.written = []

        self.proxy.datagramReceived(authRequest, ("127.0.0.1", 5632))
        self.assertEquals(
            self.transport.written[-1],
            ((okResponse, ("127.0.0.1", 5632)))
        )



class DeprecationTests(unittest.TestCase):
    """
    Tests for deprecation of obsolete components of L{twisted.protocols.sip}.
    """

    suppress = []

    def test_deprecatedDigestCalcHA1(self):
        """
        L{sip.DigestCalcHA1} is deprecated.
        """
        self.callDeprecated(Version("Twisted", 9, 0, 0),
                            sip.DigestCalcHA1, '', '', '', '', '', '')


    def test_deprecatedDigestCalcResponse(self):
        """
        L{sip.DigestCalcResponse} is deprecated.
        """
        self.callDeprecated(Version("Twisted", 9, 0, 0),
                            sip.DigestCalcResponse, '', '', '', '', '', '', '',
                            '')

    def test_deprecatedBasicAuthorizer(self):
        """
        L{sip.BasicAuthorizer} is deprecated.
        """
        self.callDeprecated(Version("Twisted", 9, 0, 0), sip.BasicAuthorizer)


    def test_deprecatedDigestAuthorizer(self):
        """
        L{sip.DigestAuthorizer} is deprecated.
        """
        self.callDeprecated(Version("Twisted", 9, 0, 0), sip.DigestAuthorizer)


    def test_deprecatedDigestedCredentials(self):
        """
        L{sip.DigestedCredentials} is deprecated.
        """
        self.callDeprecated(Version("Twisted", 9, 0, 0),
                            sip.DigestedCredentials, '', {}, {})
