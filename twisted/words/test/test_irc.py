
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.trial import unittest
from twisted.words.protocols import irc
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

class NoticingClient(object, IRCClientWithoutLogin):
    methods = {
        'created': ('when',),
        'yourHost': ('info',),
        'myInfo': ('servername', 'version', 'umodes', 'cmodes'),
        'luserClient': ('info',),
        'bounce': ('info',),
        'isupport': ('options',),
        'luserChannels': ('channels',),
        'luserOp': ('ops',),
        'luserMe': ('info',),
        'receivedMOTD': ('motd',),

        'privmsg': ('user', 'channel', 'message'),
        'joined': ('channel',),
        'left': ('channel',),
        'noticed': ('user', 'channel', 'message'),
        'modeChanged': ('user', 'channel', 'set', 'modes', 'args'),
        'pong': ('user', 'secs'),
        'signedOn': (),
        'kickedFrom': ('channel', 'kicker', 'message'),
        'nickChanged': ('nick',),

        'userJoined': ('user', 'channel'),
        'userLeft': ('user', 'channel'),
        'userKicked': ('user', 'channel', 'kicker', 'message'),
        'action': ('user', 'channel', 'data'),
        'topicUpdated': ('user', 'channel', 'newTopic'),
        'userRenamed': ('oldname', 'newname')}

    def __init__(self, *a, **kw):
        object.__init__(self)
        self.calls = []

    def __getattribute__(self, name):
        if name.startswith('__') and name.endswith('__'):
            return super(NoticingClient, self).__getattribute__(name)
        try:
            args = super(NoticingClient, self).__getattribute__('methods')[name]
        except KeyError:
            return super(NoticingClient, self).__getattribute__(name)
        else:
            return self.makeMethod(name, args)

    def makeMethod(self, fname, args):
        def method(*a, **kw):
            if len(a) > len(args):
                raise TypeError("TypeError: %s() takes %d arguments "
                                "(%d given)" % (fname, len(args), len(a)))
            for (name, value) in zip(args, a):
                if name in kw:
                    raise TypeError("TypeError: %s() got multiple values "
                                    "for keyword argument '%s'" % (fname, name))
                else:
                    kw[name] = value
            if len(kw) != len(args):
                raise TypeError("TypeError: %s() takes %d arguments "
                                "(%d given)" % (fname, len(args), len(a)))
            self.calls.append((fname, kw))
        return method

class ModeTestCase(unittest.TestCase):
    def setUp(self):
        self.file = StringIOWithoutClosing()
        self.transport = protocol.FileWrapper(self.file)
        self.client = NoticingClient()
        self.client.makeConnection(self.transport)

    def tearDown(self):
        self.transport.loseConnection()
        self.client.connectionLost()
        del self.client
        del self.transport

    def testModeChange(self):
        message = ":ChanServ!ChanServ@services. MODE #tanstaafl +o exarkun\r\n"
        self.client.dataReceived(message)
        self.assertEquals(
            self.client.calls,
            [('modeChanged', {'user': "ChanServ!ChanServ@services.",
                              'channel': '#tanstaafl',
                              'set': True,
                              'modes': 'o',
                              'args': ('exarkun',)})])

    def _serverTestImpl(self, code, msg, func, **kw):
        host = kw.pop('host', 'server.host')
        nick = kw.pop('nick', 'nickname')

        message = ":" + host + " " + code + " " + nick + " :" + msg + "\r\n"

        self.client.dataReceived(message)
        self.assertEquals(
            self.client.calls,
            [(func, kw)])

    def testYourHost(self):
        msg = "Your host is some.host[blah.blah/6667], running version server-version-3"
        self._serverTestImpl("002", msg, "yourHost", info=msg)

    def testCreated(self):
        msg = "This server was cobbled together Fri Aug 13 18:00:25 UTC 2004"
        self._serverTestImpl("003", msg, "created", when=msg)

    def testMyInfo(self):
        msg = "server.host server-version abcDEF bcdEHI"
        self._serverTestImpl("004", msg, "myInfo",
                             servername="server.host",
                             version="server-version",
                             umodes="abcDEF",
                             cmodes="bcdEHI")

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
