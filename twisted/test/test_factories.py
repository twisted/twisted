# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#

"""Test code for basic Factory classes"""

from twisted.trial import unittest, util

from twisted.internet import reactor, defer
from twisted.internet.protocol import Factory, ReconnectingClientFactory
from twisted.protocols.basic import Int16StringReceiver
import pickle

class In(Int16StringReceiver):
    def __init__(self):
        self.msgs = {}

    def connectionMade(self):
        self.factory.connections += 1

    def stringReceived(self, msg):
        n, msg = pickle.loads(msg)
        self.msgs[n] = msg
        self.sendString(pickle.dumps(n))

    def connectionLost(self, reason):
        self.factory.allMessages.append(self.msgs)
        if len(self.factory.allMessages) >= self.factory.goal:
            self.factory.d.callback(None)

class Out(Int16StringReceiver):
    msgs = dict([(x, 'X' * x) for x in range(10)])

    def __init__(self):
        self.msgs = Out.msgs.copy()

    def connectionMade(self):
        for i in self.msgs.keys():
            self.sendString(pickle.dumps( (i, self.msgs[i])))

    def stringReceived(self, msg):
        n = pickle.loads(msg)
        del self.msgs[n]
        if not self.msgs:
            self.transport.loseConnection()
            self.factory.howManyTimes -= 1
            if self.factory.howManyTimes <= 0:
                self.factory.stopTrying()

class ReconnectingFactoryTestCase(unittest.TestCase):
    def testStopTrying(self):
        f = Factory()
        f.protocol = In
        f.connections = 0
        f.allMessages = []
        f.goal = 2
        f.d = defer.Deferred()

        c = ReconnectingClientFactory()
        c.initialDelay = c.delay = 0.2
        c.protocol = Out
        c.howManyTimes = 2

        port = self.port = reactor.listenTCP(0, f)
        PORT = port.getHost().port
        reactor.connectTCP('127.0.0.1', PORT, c)

        f.d.addCallback(self._testStopTrying_1, f, c)
        return f.d
    testStopTrying.timeout = 10
    def _testStopTrying_1(self, res, f, c):
        self.assertEquals(len(f.allMessages), 2,
                          "not enough messages -- %s" % f.allMessages)
        self.assertEquals(f.connections, 2,
                          "Number of successful connections incorrect %d" %
                          f.connections)
        self.assertEquals(f.allMessages, [Out.msgs] * 2)
        self.failIf(c.continueTrying, "stopTrying never called or ineffective")

    def tearDown(self):
        return self.port.stopListening()
