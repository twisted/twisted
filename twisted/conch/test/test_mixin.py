# -*- twisted.conch.test.test_mixin -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

import time

from twisted.internet import reactor, protocol

from twisted.trial import unittest
from twisted.test.proto_helpers import StringTransport

from twisted.conch import mixin

class BufferingTest(unittest.TestCase):
    def testBuffering(self):
        p = mixin.BufferingMixin()
        t = p.transport = StringTransport()

        L = ['foo', 'bar', 'baz', 'quux']

        for s in L:
            p.write(s)
            self.assertEquals(t.value(), '')

        for i in range(10):
            reactor.iterate(0.01)
            if t.value():
                break

        self.assertEquals(t.value(), ''.join(L))

class BufferingProtocol(protocol.Protocol, mixin.BufferingMixin):
    pass

class UnbufferingProtocol(protocol.Protocol):
    def connectionMade(self):
        self.write = self.transport.write
        self.flush = lambda: None

class BufferingTiming(unittest.TestCase):
    def setUp(self):
        f = protocol.ServerFactory()
        f.protocol = protocol.Protocol
        self.server = reactor.listenTCP(0, f)

        f2 = protocol.ClientCreator(reactor, BufferingProtocol)
        self.buffered = f2.connectTCP('127.0.0.1', self.server.getHost().port)

        f3 = protocol.ClientCreator(reactor, UnbufferingProtocol)
        self.unbuffered = f3.connectTCP('127.0.0.1', self.server.getHost().port)

    def benchmarkBuffering(self, clock=time.clock, sleep=time.sleep):
        bufp = unittest.deferredResult(self.buffered)
        unbufp = unittest.deferredResult(self.unbuffered)

        one = 'x'
        ten = one * 10
        hundred = ten * 10
        thousand = hundred * 10

        for p in bufp, unbufp:
            write = p.write
            iteration = xrange(100)
            start = clock()

            write(one)
            for i in iteration:
                write(ten)

            end = clock()
            print 'Took', end - start

