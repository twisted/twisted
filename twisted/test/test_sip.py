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
        self.assertEquals(m.uri, uri)
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
        self.assertEquals(r.toString(), "INVITE sip:foo SIP/2.0\r\nfoo: bar\r\n\r\n")

    def testResponse(self):
        r = sip.Response(200, "OK")
        r.addHeader("foo", "bar")
        r.addHeader("Content-Length", "4")
        r.bodyDataReceived("1234")
        self.assertEquals(r.toString(), "SIP/2.0 200 OK\r\nfoo: bar\r\ncontent-length: 4\r\n\r\n1234")


class ViaTestCase(unittest.TestCase):

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
