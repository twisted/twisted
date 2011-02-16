# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test code for basic Factory classes.
"""

import pickle

from twisted.trial.unittest import TestCase

from twisted.internet import reactor, defer
from twisted.internet.task import Clock
from twisted.internet.protocol import Factory, ReconnectingClientFactory
from twisted.protocols.basic import Int16StringReceiver



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



class FakeConnector(object):
    """
    A fake connector class, to be used to mock connections failed or lost.
    """

    def stopConnecting(self):
        pass


    def connect(self):
        pass



class ReconnectingFactoryTestCase(TestCase):
    """
    Tests for L{ReconnectingClientFactory}.
    """

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

        port = reactor.listenTCP(0, f)
        self.addCleanup(port.stopListening)
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


    def test_stopTryingDoesNotReconnect(self):
        """
        Calling stopTrying on a L{ReconnectingClientFactory} doesn't attempt a
        retry on any active connector.
        """
        class FactoryAwareFakeConnector(FakeConnector):
            attemptedRetry = False

            def stopConnecting(self):
                """
                Behave as though an ongoing connection attempt has now
                failed, and notify the factory of this.
                """
                f.clientConnectionFailed(self, None)

            def connect(self):
                """
                Record an attempt to reconnect, since this is what we
                are trying to avoid.
                """
                self.attemptedRetry = True

        f = ReconnectingClientFactory()
        f.clock = Clock()

        # simulate an active connection - stopConnecting on this connector should
        # be triggered when we call stopTrying
        f.connector = FactoryAwareFakeConnector()
        f.stopTrying()

        # make sure we never attempted to retry
        self.assertFalse(f.connector.attemptedRetry)
        self.assertFalse(f.clock.getDelayedCalls())


    def test_serializeUnused(self):
        """
        A L{ReconnectingClientFactory} which hasn't been used for anything
        can be pickled and unpickled and end up with the same state.
        """
        original = ReconnectingClientFactory()
        reconstituted = pickle.loads(pickle.dumps(original))
        self.assertEqual(original.__dict__, reconstituted.__dict__)


    def test_serializeWithClock(self):
        """
        The clock attribute of L{ReconnectingClientFactory} is not serialized,
        and the restored value sets it to the default value, the reactor.
        """
        clock = Clock()
        original = ReconnectingClientFactory()
        original.clock = clock
        reconstituted = pickle.loads(pickle.dumps(original))
        self.assertIdentical(reconstituted.clock, None)


    def test_deserializationResetsParameters(self):
        """
        A L{ReconnectingClientFactory} which is unpickled does not have an
        L{IConnector} and has its reconnecting timing parameters reset to their
        initial values.
        """
        factory = ReconnectingClientFactory()
        factory.clientConnectionFailed(FakeConnector(), None)
        self.addCleanup(factory.stopTrying)

        serialized = pickle.dumps(factory)
        unserialized = pickle.loads(serialized)
        self.assertEqual(unserialized.connector, None)
        self.assertEqual(unserialized._callID, None)
        self.assertEqual(unserialized.retries, 0)
        self.assertEqual(unserialized.delay, factory.initialDelay)
        self.assertEqual(unserialized.continueTrying, True)


    def test_parametrizedClock(self):
        """
        The clock used by L{ReconnectingClientFactory} can be parametrized, so
        that one can cleanly test reconnections.
        """
        clock = Clock()
        factory = ReconnectingClientFactory()
        factory.clock = clock

        factory.clientConnectionLost(FakeConnector(), None)
        self.assertEquals(len(clock.calls), 1)
