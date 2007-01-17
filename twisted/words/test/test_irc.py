# Copyright (c) 2001-2005 Twisted Matrix Laboratories.
# See LICENSE for details.

from StringIO import StringIO
import time

from twisted.trial import unittest
from twisted.trial.unittest import TestCase
from twisted.words.protocols import irc
from twisted.words.protocols.irc import IRCClient
from twisted.internet import protocol


class StringIOWithoutClosing(StringIO):
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

def pop(dict, key, default):
    try:
        value = dict[key]
    except KeyError:
        return default
    else:
        del dict[key]
        return value

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
        host = pop(kw, 'host', 'server.host')
        nick = pop(kw, 'nick', 'nickname')
        args = pop(kw, 'args', '')

        message = (":" +
                   host + " " +
                   code + " " +
                   nick + " " +
                   args + " :" +
                   msg + "\r\n")

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

    def testLuserClient(self):
        msg = "There are 9227 victims and 9542 hiding on 24 servers"
        self._serverTestImpl("251", msg, "luserClient",
                             info=msg)

    def testISupport(self):
        args = ("MODES=4 CHANLIMIT=#:20 NICKLEN=16 USERLEN=10 HOSTLEN=63 "
                "TOPICLEN=450 KICKLEN=450 CHANNELLEN=30 KEYLEN=23 CHANTYPES=# "
                "PREFIX=(ov)@+ CASEMAPPING=ascii CAPAB IRCD=dancer")
        msg = "are available on this server"
        self._serverTestImpl("005", msg, "isupport", args=args,
                             options=['MODES=4',
                                      'CHANLIMIT=#:20',
                                      'NICKLEN=16',
                                      'USERLEN=10',
                                      'HOSTLEN=63',
                                      'TOPICLEN=450',
                                      'KICKLEN=450',
                                      'CHANNELLEN=30',
                                      'KEYLEN=23',
                                      'CHANTYPES=#',
                                      'PREFIX=(ov)@+',
                                      'CASEMAPPING=ascii',
                                      'CAPAB',
                                      'IRCD=dancer'])

    def testBounce(self):
        msg = "Try server some.host, port 321"
        self._serverTestImpl("005", msg, "bounce",
                             info=msg)

    def testLuserChannels(self):
        args = "7116"
        msg = "channels formed"
        self._serverTestImpl("254", msg, "luserChannels", args=args,
                             channels=int(args))

    def testLuserOp(self):
        args = "34"
        msg = "flagged staff members"
        self._serverTestImpl("252", msg, "luserOp", args=args,
                             ops=int(args))

    def testLuserMe(self):
        msg = "I have 1937 clients and 0 servers"
        self._serverTestImpl("255", msg, "luserMe",
                             info=msg)

    def testMOTD(self):
        lines = [
            ":host.name 375 nickname :- host.name Message of the Day -",
            ":host.name 372 nickname :- Welcome to host.name",
            ":host.name 376 nickname :End of /MOTD command."]
        for L in lines:
            self.assertEquals(self.client.calls, [])
            self.client.dataReceived(L + '\r\n')

        self.assertEquals(
            self.client.calls,
            [("receivedMOTD", {"motd": ["host.name Message of the Day -", "Welcome to host.name"]})])


    def _clientTestImpl(self, sender, group, type, msg, func, **kw):
        ident = pop(kw, 'ident', 'ident')
        host = pop(kw, 'host', 'host')

        wholeUser = sender + '!' + ident + '@' + host
        message = (":" +
                   wholeUser + " " +
                   type + " " +
                   group + " :" +
                   msg + "\r\n")
        self.client.dataReceived(message)
        self.assertEquals(
            self.client.calls,
            [(func, kw)])
        self.client.calls = []

    def testPrivmsg(self):
        msg = "Tooty toot toot."
        self._clientTestImpl("sender", "#group", "PRIVMSG", msg, "privmsg",
                             ident="ident", host="host",
                             # Expected results below
                             user="sender!ident@host",
                             channel="#group",
                             message=msg)

        self._clientTestImpl("sender", "recipient", "PRIVMSG", msg, "privmsg",
                             ident="ident", host="host",
                             # Expected results below
                             user="sender!ident@host",
                             channel="recipient",
                             message=msg)

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

    def testWhois(self):
        """
        Verify that a whois by the client receives the right protocol actions
        from the server.
        """
        timestamp = int(time.time()-100)
        hostname = self.p.hostname
        req = 'requesting-nick'
        targ = 'target-nick'
        self.p.whois(req, targ, 'target', 'host.com', 
                'Target User', 'irc.host.com', 'A fake server', False, 
                12, timestamp, ['#fakeusers', '#fakemisc'])
        expected = '\r\n'.join([
':%(hostname)s 311 %(req)s %(targ)s target host.com * :Target User',
':%(hostname)s 312 %(req)s %(targ)s irc.host.com :A fake server',
':%(hostname)s 317 %(req)s %(targ)s 12 %(timestamp)s :seconds idle, signon time',
':%(hostname)s 319 %(req)s %(targ)s :#fakeusers #fakemisc',
':%(hostname)s 318 %(req)s %(targ)s :End of WHOIS list.',
'']) % dict(hostname=hostname, timestamp=timestamp, req=req, targ=targ)
        self.check(expected)


class DummyClient(irc.IRCClient):
    def __init__(self):
        self.lines = []
    def sendLine(self, m):
        self.lines.append(m)


class ClientMsgTests(unittest.TestCase):
    def setUp(self):
        self.client = DummyClient()

    def testSingleLine(self):
        self.client.msg('foo', 'bar')
        self.assertEquals(self.client.lines, ['PRIVMSG foo :bar'])

    def testDodgyMaxLength(self):
        self.assertRaises(ValueError, self.client.msg, 'foo', 'bar', 0)
        self.assertRaises(ValueError, self.client.msg, 'foo', 'bar', 3)

    def testMultipleLine(self):
        maxLen = len('PRIVMSG foo :') + 3 + 2 # 2 for line endings
        self.client.msg('foo', 'barbazbo', maxLen)
        self.assertEquals(self.client.lines, ['PRIVMSG foo :bar',
                                              'PRIVMSG foo :baz',
                                              'PRIVMSG foo :bo'])

    def testSufficientWidth(self):
        msg = 'barbazbo'
        maxLen = len('PRIVMSG foo :%s' % (msg,)) + 2
        self.client.msg('foo', msg, maxLen)
        self.assertEquals(self.client.lines, ['PRIVMSG foo :%s' % (msg,)])
        self.client.lines = []
        self.client.msg('foo', msg, maxLen-1)
        self.assertEquals(2, len(self.client.lines))
        self.client.lines = []
        self.client.msg('foo', msg, maxLen+1)
        self.assertEquals(1, len(self.client.lines))

    def testSplitSanity(self):
        # Whiteboxing
        self.assertRaises(ValueError, irc.split, 'foo', -1)
        self.assertRaises(ValueError, irc.split, 'foo', 0)
        self.assertEquals([], irc.split('', 1))
        self.assertEquals([], irc.split(''))


class ClientTests(TestCase):
    """
    Tests for the protocol-level behavior of IRCClient methods intended to
    be called by application code.
    """
    def setUp(self):
        self.transport = StringIO()
        self.protocol = IRCClient()
        self.protocol.performLogin = False
        self.protocol.makeConnection(self.transport)

        # Sanity check - we don't want anything to have happened at this
        # point, since we're not in a test yet.
        self.failIf(self.transport.getvalue())


    def test_register(self):
        """
        Verify that the L{IRCClient.register} method sends a a USER command
        with the correct arguments.
        """
        username = 'testuser'
        hostname = 'testhost'
        servername = 'testserver'
        self.protocol.realname = 'testname'
        self.protocol.password = None
        self.protocol.register(username, hostname, servername)
        expected = [
            'NICK %s' % (username,),
            'USER %s %s %s :%s' % (
                username, hostname, servername, self.protocol.realname),
            '']
        self.assertEqual(self.transport.getvalue().split('\r\n'), expected)


    def test_registerWithPassword(self):
        """
        Verify that if the C{password} attribute of L{IRCClient} is not
        C{None}, the C{register} method also authenticates using it.
        """
        username = 'testuser'
        hostname = 'testhost'
        servername = 'testserver'
        self.protocol.realname = 'testname'
        self.protocol.password = 'testpass'
        self.protocol.register(username, hostname, servername)
        expected = [
            'PASS %s' % (self.protocol.password,),
            'NICK %s' % (username,),
            'USER %s %s %s :%s' % (
                username, hostname, servername, self.protocol.realname),
            '']
        self.assertEqual(self.transport.getvalue().split('\r\n'), expected)
