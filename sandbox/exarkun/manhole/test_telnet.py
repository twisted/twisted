
import telnet

from twisted.trial import unittest
from twisted.test import proto_helpers

class TestHandler:
    def __init__(self, proto):
        self.bytes = ''
        self.subcmd = ''
        self.calls = []

        d = proto.negotiationMap = {}
        d['\x12'] = self.neg_TEST_COMMAND

        d = proto.commandMap = proto.commandMap.copy()
        for cmd in ('NOP', 'DM', 'BRK', 'IP', 'AO', 'AYT', 'EC', 'EL', 'GA'):
            d[getattr(telnet, cmd)] = lambda arg, cmd=cmd: self.calls.append(cmd)

    def connectionMade(self):
        pass

    def dataReceived(self, bytes):
        self.bytes += bytes

    def connectionLost(self, reason):
        pass

    def neg_TEST_COMMAND(self, payload):
        self.subcmd = payload

class TelnetTestCase(unittest.TestCase):
    def setUp(self):
        self.p = telnet.Telnet2()
        self.p.handlerFactory = TestHandler
        self.t = proto_helpers.StringTransport()
        self.p.makeConnection(self.t)

    def testRegularBytes(self):
        # Just send a bunch of bytes.  None of these do anything
        # with telnet.  They should pass right through to the
        # application layer.
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
        # Send a bunch of bytes and a couple quoted \xFFs.  Unquoted,
        # \xFF is a telnet command.  Quoted, one of them from each pair
        # should be passed through to the application layer.
        h = self.p.handler

        L = ["here are some bytes\xff\xff with an embedded IAC",
             "and here is a test of a border escape\xff",
             "\xff did you get that IAC?"]

        for b in L:
            self.p.dataReceived(b)

        self.assertEquals(h.bytes, ''.join(L).replace('\xff\xff', '\xff'))

    def _simpleCommandTest(self, cmdName):
        # Send a single simple telnet command and make sure
        # it gets noticed and the appropriate method gets
        # called.
        h = self.p.handler

        cmd = telnet.IAC + getattr(telnet, cmdName)
        L = ["Here's some bytes, tra la la",
             "But ono!" + cmd + " an interrupt"]

        for b in L:
            self.p.dataReceived(b)

        self.assertEquals(h.calls, [cmdName])
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
        # Send a subnegotiation command and make sure it gets
        # parsed and that the correct method is called.
        h = self.p.handler

        cmd = telnet.IAC + telnet.SB + '\x12hello world' + telnet.SE
        L = ["These are some bytes but soon" + cmd,
             "there will be some more"]

        for b in L:
            self.p.dataReceived(b)

        self.assertEquals(h.bytes, ''.join(L).replace(cmd, ''))
        self.assertEquals(h.subcmd, list("hello world"))

    def testSubnegotiationWithEscape(self):
        # Send a subnegotiation command with an embedded escaped SE.  Make sure
        # that SE gets passed to the correct method.
        h = self.p.handler

        cmd = telnet.IAC + telnet.SB + '\x12' + telnet.IAC + telnet.SE + telnet.SE
        L = ["Some bytes are here" + cmd + "and here",
             "and here"]

        for b in L:
            self.p.dataReceived(b)

        self.assertEquals(h.bytes, ''.join(L).replace(cmd, ''))
        self.assertEquals(h.subcmd, [telnet.SE])

    def testBoundardySubnegotiation(self):
        # Send a subnegotiation command.  Split it at every possible byte boundary
        # and make sure it always gets parsed and that it is passed to the correct
        # method.
        cmd = telnet.IAC + telnet.SB + '\x12' + telnet.IAC + telnet.SE + 'hello' + telnet.SE
        for i in range(len(cmd)):
            h = self.p.handler = TestHandler(self.p)

            a, b = cmd[:i], cmd[i:]
            L = ["first part" + a,
                 b + "last part"]

            for bytes in L:
                self.p.dataReceived(bytes)

            self.assertEquals(h.bytes, ''.join(L).replace(cmd, ''))
            self.assertEquals(h.subcmd, [telnet.SE] + list('hello'))

    def testRefuseWill(self):
        # Try to enable an option.  The server should refuse to enable it.
        cmd = telnet.IAC + telnet.WILL + '\x12'

        bytes = "surrounding bytes" + cmd + "to spice things up"
        self.p.dataReceived(bytes)

        self.assertEquals(self.p.handler.bytes, bytes.replace(cmd, ''))
        self.assertEquals(self.t.value(), telnet.IAC + telnet.DONT + '\x12')

    def testRefuseDo(self):
        # Try to enable an option.  The server should refuse to enable it.
        cmd = telnet.IAC + telnet.DO + '\x12'

        bytes = "surrounding bytes" + cmd + "to spice things up"
        self.p.dataReceived(bytes)

        self.assertEquals(self.p.handler.bytes, bytes.replace(cmd, ''))
        self.assertEquals(self.t.value(), telnet.IAC + telnet.WONT + '\x12')

