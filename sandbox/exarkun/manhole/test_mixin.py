
from twisted.internet import reactor

from twisted.trial import unittest
from twisted.test.proto_helpers import StringTransport

import mixin

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
