# -*- coding: Latin-1 -*-

from twisted.trial import unittest

from twisted.internet import reactor
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

        c = ReconnectingClientFactory()
        c.protocol = Out
        c.howManyTimes = 2

        PORT=9000
        reactor.connectTCP('localhost', PORT, c)
        reactor.listenTCP(PORT, f)
        
        howLong = 500
        while howLong and len(f.allMessages) != 2:
            howLong -= 1
            reactor.iterate(0.1)
        
        self.failIf(c.continueTrying, "stopTrying never called or ineffective")
        self.assertEquals(f.connections, 2, "Number of successful connections incorrect")
        self.assertEquals(f.allMessages, [Out.msgs] * 2)
        