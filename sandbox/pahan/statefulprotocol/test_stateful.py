from twisted.test import test_protocols
from stateful import MyInt32StringReceiver

import struct

class TestInt32(MyInt32StringReceiver):
    def connectionMade(self):
        MyInt32StringReceiver.connectionMade(self)
        self.received = []

    def stringReceived(self, s):
        self.received.append(s)

    MAX_LENGTH = 50
    closed = 0

    def connectionLost(self, reason):
        self.closed = 1

class Int32TestCase(test_protocols.Int32TestCase):
    protocol = TestInt32
    def testBigReceive(self):
        r = self.getProtocol()
        big = ""
        for s in self.strings * 4:
            big += struct.pack("!i",len(s))+s
        r.dataReceived(big)
        self.assertEquals(r.received, self.strings * 4)

