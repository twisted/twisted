
import telnet

from twisted.trial import unittest
from twisted.test import proto_helpers

class TestHandler:
    def __init__(self, proto):
        self.bytes = ''
        self.subcmd = ''
        self.calls = []

        d = proto.subcommandMap = {}
        d['\x12'] = 'test_command'

    def connectionMade(self):
        pass

    def dataReceived(self, bytes):
        self.bytes += bytes

    def connectionLost(self, reason):
        pass

    def __getattr__(self, name):
        if name.startswith('telnet_'):
            return lambda: self.calls.append(name)
        raise AttributeError(name)

    def subcmd_TEST_COMMAND(self, payload):
        self.subcmd = payload

class TelnetTestCase(unittest.TestCase):
    def setUp(self):
        self.p = telnet.Telnet2()
        self.p.handlerFactory = TestHandler
        self.t = proto_helpers.StringTransport()
        self.p.makeConnection(self.t)

    def testRegularBytes(self):
        h = self.p.handler

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
        h = self.p.handler

        L = ["here are some bytes\xff\xff with an embedded IAC",
             "and here is a test of a border escape\xff",
             "\xff did you get that IAC?"]

        for b in L:
            self.p.dataReceived(b)

        self.assertEquals(h.bytes, ''.join(L).replace('\xff\xff', '\xff'))

    def _simpleCommandTest(self, cmdName):
        h = self.p.handler

        cmd = telnet.IAC + getattr(telnet, cmdName)
        L = ["Here's some bytes, tra la la",
             "But ono!" + cmd + " an interrupt"]

        for b in L:
            self.p.dataReceived(b)

        self.assertEquals(h.calls, ['telnet_' + cmdName])
        self.assertEquals(h.bytes, ''.join(L).replace(cmd, ''))

    def testInterrupt(self):
        self._simpleCommandTest("IP")

    def testNoOperation(self):
        self._simpleCommandTest("NOP")

    def testDataMark(self):
        self._simpleCommandTest("DM")

    def testBreak(self):
        self._simpleCommandTest("BRK")

    def testAbortOutput(self):
        self._simpleCommandTest("AO")

    def testAreYouThere(self):
        self._simpleCommandTest("AYT")

    def testEraseCharacter(self):
        self._simpleCommandTest("EC")

    def testEraseLine(self):
        self._simpleCommandTest("EL")

    def testGoAhead(self):
        self._simpleCommandTest("GA")

    def testSubnegotiation(self):
        h = self.p.handler

        cmd = telnet.IAC + telnet.SB + '\x12hello world' + telnet.SE
        L = ["These are some bytes but soon" + cmd,
             "there will be some more"]

        for b in L:
            self.p.dataReceived(b)

        self.assertEquals(h.bytes, ''.join(L).replace(cmd, ''))
        self.assertEquals(h.subcmd, list("hello world"))

    def testSubnegotiationWithEscape(self):
        h = self.p.handler

        cmd = telnet.IAC + telnet.SB + '\x12' + telnet.IAC + telnet.SE + telnet.SE
        L = ["Some bytes are here" + cmd + "and here",
             "and here"]

        for b in L:
            self.p.dataReceived(b)

        self.assertEquals(h.bytes, ''.join(L).replace(cmd, ''))
        self.assertEquals(h.subcmd, [telnet.SE])

