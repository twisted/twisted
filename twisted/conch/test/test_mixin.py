# -*- twisted.conch.test.test_mixin -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import time

from twisted.internet import reactor, protocol

from twisted.trial import unittest
from twisted.test.proto_helpers import StringTransport

from twisted.conch import mixin


class TestBufferingProto(mixin.BufferingMixin):
    scheduled = False
    rescheduled = 0
    def schedule(self):
        self.scheduled = True
        return object()

    def reschedule(self, token):
        self.rescheduled += 1



class BufferingTest(unittest.TestCase):
    def testBuffering(self):
        p = TestBufferingProto()
        t = p.transport = StringTransport()

        self.failIf(p.scheduled)

        L = ['foo', 'bar', 'baz', 'quux']

        p.write('foo')
        self.failUnless(p.scheduled)
        self.failIf(p.rescheduled)

        for s in L:
            n = p.rescheduled
            p.write(s)
            self.assertEquals(p.rescheduled, n + 1)
            self.assertEquals(t.value(), '')

        p.flush()
        self.assertEquals(t.value(), 'foo' + ''.join(L))
