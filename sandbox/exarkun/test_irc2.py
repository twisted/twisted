# -*- coding: Latin-1 -*-

from irc2 import NoSuchChannel, AdvancedClient

from twisted.python import log
from twisted.internet import defer
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
