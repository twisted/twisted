
import telnet

from twisted.trial import unittest
from twisted.test import proto_helpers

class TestHandler:
    bytes = ''
    def dataReceived(self, bytes):
        self.bytes += bytes

class TelnetTestCase(unittest.TestCase):
    def setUp(self):
        self.p = telnet.Telnet2()
        self.t = proto_helpers.StringTransport()
        self.p.makeConnection(self.t)

    def testRegularBytes(self):
        h = self.p.handler = TestHandler()

        L = ["here are some bytes la la la",
             "some more arrive here",
             "lots of bytes to play with",
             "la la la",
             "ta de da",
             "dum"]
        for b in L:
            self.p.dataReceived(b)

        self.assertEquals(h.bytes, ''.join(L))

    def testIACEscape(self):
        h = self.p.handler = TestHandler()

        L = ["here are some bytes\xff\xff with an embedded IAC",
             "and here is a test of a border escape\xff",
             "\xff did you get that IAC?"]

        for b in L:
            self.p.dataReceived(b)

        self.assertEquals(h.bytes, ''.join(L).replace('\xff\xff', '\xff'))

