
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

from twisted.trial import unittest
from twisted.protocols import irc
from twisted.internet import protocol
import StringIO


class StringIOWithoutClosing(StringIO.StringIO):
    def close(self):
        pass

stringSubjects = [
    "Hello, this is a nice string with no complications.",
    "xargs%(NUL)smight%(NUL)slike%(NUL)sthis" % {'NUL': irc.NUL },
    "embedded%(CR)snewline%(CR)s%(NL)sFUN%(NL)s" % {'CR': irc.CR,
                                                    'NL': irc.NL},
    "escape!%(X)s escape!%(M)s %(X)s%(X)sa %(M)s0" % {'X': irc.X_QUOTE,
                                                      'M': irc.M_QUOTE}
    ]


class QuotingTest(unittest.TestCase):
    def test_lowquoteSanity(self):
        """Testing client-server level quote/dequote"""
        for s in stringSubjects:
            self.failUnlessEqual(s, irc.lowDequote(irc.lowQuote(s)))

    def test_ctcpquoteSanity(self):
        """Testing CTCP message level quote/dequote"""
        for s in stringSubjects:
            self.failUnlessEqual(s, irc.ctcpDequote(irc.ctcpQuote(s)))


class IRCClientWithoutLogin(irc.IRCClient):
    performLogin = 0


class CTCPTest(unittest.TestCase):
    def setUp(self):
        self.file = StringIOWithoutClosing()
        self.transport = protocol.FileWrapper(self.file)
        self.client = IRCClientWithoutLogin()
        self.client.makeConnection(self.transport)

    def test_ERRMSG(self):
        """Testing CTCP query ERRMSG.

        Not because this is this is an especially important case in the
        field, but it does go through the entire dispatch/decode/encode
        process.
        """

        errQuery = (":nick!guy@over.there PRIVMSG #theChan :"
                    "%(X)cERRMSG t%(X)c%(EOL)s"
                    % {'X': irc.X_DELIM,
                       'EOL': irc.CR + irc.LF})

        errReply = ("NOTICE nick :%(X)cERRMSG t :"
                    "No error has occoured.%(X)c%(EOL)s"
                    % {'X': irc.X_DELIM,
                       'EOL': irc.CR + irc.LF})

        self.client.dataReceived(errQuery)
        reply = self.file.getvalue()

        self.failUnlessEqual(errReply, reply)

    def tearDown(self):
        self.transport.loseConnection()
        self.client.connectionLost()
        del self.client
        del self.transport

class ModeNoticingClient(IRCClientWithoutLogin):
    user = channel = set = mode = args = None

    def modeChanged(self, *args):
        self.user, self.channel, self.set, self.mode, self.args = args


class ModeTestCase(unittest.TestCase):
    def setUp(self):
        self.file = StringIOWithoutClosing()
        self.transport = protocol.FileWrapper(self.file)
        self.client = ModeNoticingClient()
        self.client.makeConnection(self.transport)

    def tearDown(self):
        self.transport.loseConnection()
        self.client.connectionLost()
        del self.client
        del self.transport

    def test_MODE_CHANGE(self):
        message = ":ChanServ!ChanServ@services. MODE #tanstaafl +o exarkun\r\n"
        self.client.dataReceived(message)
        self.assertEquals(self.client.user, "ChanServ!ChanServ@services.")
        self.assertEquals(self.client.channel, "#tanstaafl")
        self.assertEquals(self.client.set, 1)
        self.assertEquals(self.client.mode, "o")
        self.assertEquals(self.client.args, ("exarkun",))

class BasicServerFunctionalityTestCase(unittest.TestCase):
    def setUp(self):
        self.f = StringIOWithoutClosing()
        self.t = protocol.FileWrapper(self.f)
        self.p = irc.IRC()
        self.p.makeConnection(self.t)
    
    def check(self, s):
        self.assertEquals(self.f.getvalue(), s)
    
    def testPrivmsg(self):
        self.p.privmsg("this-is-sender", "this-is-recip", "this is message")
        self.check(":this-is-sender PRIVMSG this-is-recip :this is message\r\n")

    def testNotice(self):
        self.p.notice("this-is-sender", "this-is-recip", "this is notice")
        self.check(":this-is-sender NOTICE this-is-recip :this is notice\r\n")
    
    def testAction(self):
        self.p.action("this-is-sender", "this-is-recip", "this is action")
        self.check(":this-is-sender ACTION this-is-recip :this is action\r\n")
    
    def testJoin(self):
        self.p.join("this-person", "#this-channel")
        self.check(":this-person JOIN #this-channel\r\n")
    
    def testPart(self):
        self.p.part("this-person", "#that-channel")
        self.check(":this-person PART #that-channel\r\n")


# class DCCtest(unittest.TestCase):
#     def setUp(self):
#         self.transport = StringIOWithoutClosing()
#         self.client = irc.IRCClient()
#         self.client.makeConnection(protocol.FileWrapper(transport))

#     def test_connect(self):
#         pass

#     def test_file(self):
#         pass
