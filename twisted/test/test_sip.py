# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Session Initialization Protocol tests."""

from twisted.trial import unittest
from twisted.protocols import sip
from twisted.internet import defer, reactor

from twisted import cred
import twisted.cred.portal
import twisted.cred.checkers

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
        r = sip.Response(200, "OK")
        r.addHeader("foo", "bar")
        r.addHeader("Content-Length", "4")
        r.bodyDataReceived("1234")
        self.assertEquals(r.toString(), "SIP/2.0 200 OK\r\nFoo: bar\r\nContent-length: 4\r\n\r\n1234")

    def testStatusCode(self):
        r = sip.Response(200)
        self.assertEquals(r.toString(), "SIP/2.0 200 OK\r\n\r\n")


class ViaTestCase(unittest.TestCase):

    def checkRoundtrip(self, v):
        s = v.toString()
        self.assertEquals(s, sip.parseViaHeader(s).toString())
    
    def testComplex(self):
        s = "SIP/2.0/UDP first.example.com:4000;ttl=16;maddr=224.2.0.1 ;branch=a7c6a8dlze (Example)"
        v = sip.parseViaHeader(s)
        self.assertEquals(v.transport, "UDP")
        self.assertEquals(v.host, "first.example.com")
        self.assertEquals(v.port, 4000)
        self.assertEquals(v.ttl, 16)
        self.assertEquals(v.maddr, "224.2.0.1")
        self.assertEquals(v.branch, "a7c6a8dlze")
        self.assertEquals(v.hidden, 0)
        self.assertEquals(v.toString(),
                          "SIP/2.0/UDP first.example.com:4000;ttl=16;branch=a7c6a8dlze;maddr=224.2.0.1")
        self.checkRoundtrip(v)
    
    def testSimple(self):
        s = "SIP/2.0/UDP example.com;hidden"
        v = sip.parseViaHeader(s)
        self.assertEquals(v.transport, "UDP")
        self.assertEquals(v.host, "example.com")
        self.assertEquals(v.port, 5060)
        self.assertEquals(v.ttl, None)
        self.assertEquals(v.maddr, None)
        self.assertEquals(v.branch, None)
        self.assertEquals(v.hidden, 1)
        self.assertEquals(v.toString(),
                          "SIP/2.0/UDP example.com:5060;hidden")
        self.checkRoundtrip(v)
    
    def testSimpler(self):
        v = sip.Via("example.com")
        self.checkRoundtrip(v)


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
    __implements__ = sip.ILocator,
    def getAddress(self, logicalURL):
        return defer.succeed(("server.com", 2345))

class FailingLocator:
    __implements__ = sip.ILocator,
    def getAddress(self, logicalURL):
        return defer.fail(LookupError())
    

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
        self.proxy.datagramReceived(r.toString(), ("1.2.3.4", 5060))
        self.assertEquals(len(self.sent), 1)
        dest, m = self.sent[0]
        self.assertEquals(dest, ("server.com", 2345))
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

    testCantForwardResponse.skip = "not implemented yet"


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
    
    def testRegister(self):
        self.register()
        dest, m = self.sent[0]
        self.assertEquals((dest.host, dest.port), ("client.com", 5060))
        self.assertEquals(m.code, 200)
        self.assertEquals(m.headers["via"], ["SIP/2.0/UDP client.com:5060"])
        self.assertEquals(m.headers["to"], ["sip:joe@bell.example.com"])
        self.assertEquals(m.headers["contact"], ["sip:joe@client.com:1234"])
        self.failUnless(int(m.headers["expires"][0]) in (3600, 3601, 3599, 3598))
        self.assertEquals(len(self.registry.users), 1)
        dc, uri = self.registry.users["joe"]
        self.assertEquals(uri.toString(), "sip:joe@client.com:1234")
        desturl = unittest.deferredResult(
            self.proxy.locator.getAddress(sip.URL(username="joe", host="bell.example.com")))
        self.assertEquals((desturl.host, desturl.port), ("client.com", 1234))

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
        f = unittest.deferredError(self.proxy.locator.getAddress(url))
        f.trap(LookupError)
    
    def testNoContactLookup(self):
        self.register()
        url = sip.URL(username="jane", host="bell.example.com")
        f = unittest.deferredError(self.proxy.locator.getAddress(url))
        f.trap(LookupError)


class Client(sip.Base):

    def __init__(self):
        sip.Base.__init__(self)
        self.received = []

    def handle_response(self, response, addr):
        self.received.append(response)


class LiveTest(unittest.TestCase):

    def setUp(self):
        self.proxy = sip.RegisterProxy(host="127.0.0.1")
        self.registry = sip.InMemoryRegistry("bell.example.com")
        self.proxy.registry = self.proxy.locator = self.registry
        self.serverPort = reactor.listenUDP(0, self.proxy, interface="127.0.0.1")
        self.client = Client()
        self.clientPort = reactor.listenUDP(0, self.client, interface="127.0.0.1")
        self.serverAddress = self.serverPort.getHost()[1:]

    def tearDown(self):
        self.clientPort.stopListening()
        self.serverPort.stopListening()
        for d, uri in self.registry.users.values():
            d.cancel()
        reactor.iterate()
        reactor.iterate()

    def testRegister(self):
        p = self.clientPort.getHost()[-1]
        r = sip.Request("REGISTER", "sip:bell.example.com")
        r.addHeader("to", "sip:joe@bell.example.com")
        r.addHeader("contact", "sip:joe@127.0.0.1:%d" % p)
        r.addHeader("via", sip.Via("127.0.0.1", port=p).toString())
        self.client.sendMessage(sip.URL(host="127.0.0.1", port=self.serverAddress[1]),
                                r)
        while not len(self.client.received):
            reactor.iterate()
        self.assertEquals(len(self.client.received), 1)
        r = self.client.received[0]
        self.assertEquals(r.code, 200)
