# -*- coding: Latin-1 -*-

from irc2 import AdvancedClient
from irc2 import NoSuchNickname, NoSuchChannel
from irc2 import NicknameMissing, NicknameCollision
from irc2 import ErroneousNickname, NicknameInUse

from twisted.python import log
from twisted.internet import defer
from twisted.internet import protocol
from twisted.trial import unittest
from twisted.test.proto_helpers import LineSendingProtocol
from twisted.protocols import loopback

class AdvancedTestClient(AdvancedClient):
    nickname = "user"

    def __init__(self):
        self.onC = defer.Deferred()
        AdvancedClient.__init__(self)

    def connectionMade(self):
        # Intentional don't call the superclass method
        self.onC.callback(self)
        

class SimpleActionTestCase(unittest.TestCase):
    success = False
    failure = None

    def succeed(self, proto):
        self.success = True
        proto.transport.loseConnection()
    
    def fail(self, failure, proto):
        self.failure = failure
        proto.transport.loseConnection()

    def testJoin(self):
        server = LineSendingProtocol([
            ":user!ident@hostmask JOIN :#channel",
        ], False)
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: p.join("#channel")
            ).addCallback(self.succeed
            ).addErrback(self.fail
            )
        loopback.loopback(server, client)
        self.failUnless(self.success)
    
    def testIllegalJoin(self):
        server = LineSendingProtocol([
            ":host.domain.tld 403 user #nonexist :That channel doesn't exist",
        ], False)
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: p.join("#nonexist")
            ).addCallback(self.succeed
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.failIf(self.success)
        self.failure.trap(NoSuchChannel)

    def testPart(self):
        server = LineSendingProtocol([
            ":user!ident@hostmask PART #channel :Reason"
        ], False)
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: p.part("#channel")
            ).addCallback(self.succeed
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.failUnless(self.success)
    
    def testIllegalPart(self):
        server = LineSendingProtocol([
            ":host.domain.tld 403 user #nonexist :That channel doesn't exist",
        ], False)
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: p.part("#nonexist")
            ).addCallback(self.succeed
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.failIf(self.success)
        self.failure.trap(NoSuchChannel)

    def testQuit(self):
        server = protocol.Protocol()
        server.dataReceived = lambda data: server.transport.loseConnection()
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: p.quit()
            ).addCallback(self.succeed
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.failUnless(self.success)
    
    def testNames(self):
        server = LineSendingProtocol([
            ":server 353 user = #channel :user another1 another2 another3",
            ":server 353 user = #channel :another4 another5",
            ":server 366 user #channel :End of /NAMES list."
        ], False)
        client = AdvancedTestClient()
        names = {}
        client.onC.addCallback(lambda p: p.names("#channel")
            ).addCallback(names.update
            ).addCallback(lambda _: client.transport.loseConnection()
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.assertEquals(names, {'#channel': [
            "user", "another1", "another2", "another3", "another4",
            "another5"
        ]})

    def testWho(self):
        server = LineSendingProtocol([
            ":server 352 user pattern jjs9GN0GAm hostmask3 servername1 user1 H :0 fullname2",
            ":server 352 user pattern 15j7VkjDbD hostmask1 servername2 user2 H :2 fullname3",
            ":server 352 user pattern 4X7zQjVK7h hostmask2 servername3 user3 H :3 fullname1",
            ":server 315 user pattern :End of /WHO list.",
        ], False)
        client = AdvancedTestClient()
        who = []
        client.onC.addCallback(lambda p: p.who("pattern")
            ).addCallback(who.extend
            ).addCallback(lambda _: client.transport.loseConnection()
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.assertEquals(who, [
            ("jjs9GN0GAm", "hostmask3", "servername1", "user1", "H", 0, "fullname2"),
            ("15j7VkjDbD", "hostmask1", "servername2", "user2", "H", 2, "fullname3"),
            ("4X7zQjVK7h", "hostmask2", "servername3", "user3", "H", 3, "fullname1"),
        ])

    def testWhois(self):
        server = LineSendingProtocol([
            ":server 311 user targetUser 4X7zQjVK7h hostmask * :Fullname",
            ":server 312 user targetUser irc.server.tld :http://server.tld/",
            ":server 320 user targetUser :is an identified user",
            ":server 317 user targetUser 227 1064473941 :seconds idle, signon time",
            ":server 318 user targetUser :End of /WHOIS list.",
        ], False)
        client = AdvancedTestClient()
        whois = {}
        client.onC.addCallback(lambda p: p.whois("targetUser")
            ).addCallback(whois.update
            ).addCallback(lambda _: client.transport.loseConnection()
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.assertEquals(whois, {
            'user': ('4X7zQjVK7h', 'hostmask', 'Fullname'),
            'server': ('irc.server.tld', 'http://server.tld/'),
            'idle': 227,
            320: [['user', 'targetUser', 'is an identified user']],
        })

    def testIllegalWhois(self):
        server = LineSendingProtocol([
            ":server 401 user targetUser :No such nick/channel",
        ], False)
        client = AdvancedTestClient()
        whois = {}
        client.onC.addCallback(lambda p: p.whois("targetUser")
            ).addCallback(whois.update
            ).addCallback(lambda _: client.transport.loseConnection()
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.failIf(whois)
        self.failure.trap(NoSuchNickname)

    def testTopic(self):
        server = LineSendingProtocol([
            ":server 332 user #channel :topic text",
        ], False)
        topic = []
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: p.topic("#channel")
            ).addCallback(topic.append
            ).addCallback(lambda _: client.transport.loseConnection()
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.assertEquals(topic, ["topic text"])
    
    def testNoTopic(self):
        server = LineSendingProtocol([
            ":server 331 user #channel :There is no set topic.",
        ], False)
        topic = []
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: p.topic("#channel")
            ).addCallback(topic.append
            ).addCallback(lambda _: client.transport.loseConnection()
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.assertEquals(topic, [None])
    
    def testTopicNoChannel(self):
        server = LineSendingProtocol([
            ":server 403 user #channel :That channel doesn't exist.",
        ], False)
        topic = []
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: p.topic("#channel")
            ).addCallback(topic.append
            ).addCallback(lambda _: client.transport.loseConnection()
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.failIf(topic)
        self.failure.trap(NoSuchChannel)

    def testNick(self):
        server = LineSendingProtocol([
            ":user!ident@hostmask NICK :newNick",
        ], False)
        nick = []
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: p.nick("newNick")
            ).addCallback(nick.append
            ).addCallback(lambda _: client.transport.loseConnection()
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.assertEquals(nick, ["newNick"])

    def testMissingNick(self):
        server = LineSendingProtocol([
            ":server 431 user :No nickname given",
        ], False)
        nick = []
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: p.nick("")
            ).addCallback(nick.append
            ).addCallback(lambda _: client.transport.loseConnection()
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.failIf(nick)
        self.failure.trap(NicknameMissing)

    def testErroneousNick(self):
        server = LineSendingProtocol([
            ":server 432 user illegalNick :Erroneous Nickname",
        ], False)
        nick = []
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: p.nick("illegalNick")
            ).addCallback(nick.append
            ).addCallback(lambda _: client.transport.loseConnection()
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.failIf(nick)
        self.failure.trap(ErroneousNickname)

    def testNickInUse(self):
        server = LineSendingProtocol([
            ":server 433 user usedNickname :Nickname is already in use.",
        ], False)
        nick = []
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: p.nick("usedNickname")
            ).addCallback(nick.append
            ).addCallback(lambda _: client.transport.loseConnection()
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.failIf(nick)
        self.failure.trap(NicknameInUse)

    def testNickCollision(self):
        server = LineSendingProtocol([
            ":server 436 user usedNickname :Nickname collision",
        ], False)
        nick = []
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: p.nick("usedNickname")
            ).addCallback(nick.append
            ).addCallback(lambda _: client.transport.loseConnection()
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.failIf(nick)
        self.failure.trap(NicknameCollision)
