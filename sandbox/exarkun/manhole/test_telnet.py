
import telnet

from twisted.trial import unittest, util
from twisted.test import proto_helpers

class TestProtocol:
    enableable = ()
    def __init__(self, proto):
        self.bytes = ''
        self.subcmd = ''
        self.calls = []

        d = proto.negotiationMap = {}
        d['\x12'] = self.neg_TEST_COMMAND

        d = proto.commandMap = proto.commandMap.copy()
        for cmd in ('NOP', 'DM', 'BRK', 'IP', 'AO', 'AYT', 'EC', 'EL', 'GA'):
            d[getattr(telnet, cmd)] = lambda arg, cmd=cmd: self.calls.append(cmd)

        self.enabled = []
        self.disabled = []

    def makeConnection(self, transport):
        pass

    def dataReceived(self, bytes):
        self.bytes += bytes

    def connectionLost(self, reason):
        pass

    def neg_TEST_COMMAND(self, payload):
        self.subcmd = payload

    def allowEnable(self, option):
        return option in self.enableable

    def enable(self, option):
        self.enabled.append(option)

    def disable(self, option):
        self.disabled.append(option)

class TelnetTestCase(unittest.TestCase):
    def setUp(self):
        self.p = telnet.TelnetTransport()
        self.p.protocolFactory = TestProtocol
        self.t = proto_helpers.StringTransport()
        self.p.makeConnection(self.t)

    def testRegularBytes(self):
        # Just send a bunch of bytes.  None of these do anything
        # with telnet.  They should pass right through to the
        # application layer.
        h = self.p.protocol

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
        h = self.p.protocol

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
        h = self.p.protocol

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
        h = self.p.protocol

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
        h = self.p.protocol

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
            h = self.p.protocol = TestProtocol(self.p)

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

        self.assertEquals(self.p.protocol.bytes, bytes.replace(cmd, ''))
        self.assertEquals(self.t.value(), telnet.IAC + telnet.DONT + '\x12')

    def testRefuseDo(self):
        # Try to enable an option.  The server should refuse to enable it.
        cmd = telnet.IAC + telnet.DO + '\x12'

        bytes = "surrounding bytes" + cmd + "to spice things up"
        self.p.dataReceived(bytes)

        self.assertEquals(self.p.protocol.bytes, bytes.replace(cmd, ''))
        self.assertEquals(self.t.value(), telnet.IAC + telnet.WONT + '\x12')

    def testAcceptWont(self):
        # Try to disable an option.  The server must allow any option to
        # be disabled at any time.  Make sure it disables it and sends
        # back an acknowledgement of this.
        cmd = telnet.IAC + telnet.WONT + '\x29'

        # Jimmy it - after these two lines, the server will be in a state
        # such that it believes the option to have beenp previously enabled
        # via normal negotiation.
        s = self.p.getOptionState('\x29')
        s.state = 'yes'

        bytes = "fiddle dee" + cmd
        self.p.dataReceived(bytes)

        self.assertEquals(self.p.protocol.bytes, bytes.replace(cmd, ''))
        self.assertEquals(self.t.value(), telnet.IAC + telnet.DONT + '\x29')

    def testAcceptDont(self):
        # Try to disable an option.  The server must allow any option to
        # be disabled at any time.  Make sure it disables it and sends
        # back an acknowledgement of this.
        cmd = telnet.IAC + telnet.DONT + '\x29'

        # Jimmy it - after these two lines, the server will be in a state
        # such that it believes the option to have beenp previously enabled
        # via normal negotiation.
        s = self.p.getOptionState('\x29')
        s.state = 'yes'

        bytes = "fiddle dum " + cmd
        self.p.dataReceived(bytes)

        self.assertEquals(self.p.protocol.bytes, bytes.replace(cmd, ''))
        self.assertEquals(self.t.value(), telnet.IAC + telnet.WONT + '\x29')

    def testIgnoreWont(self):
        # Try to disable an option.  The option is already disabled.  The
        # server should send nothing in response to this.
        cmd = telnet.IAC + telnet.WONT + '\x47'

        bytes = "dum de dum" + cmd + "tra la la"
        self.p.dataReceived(bytes)

        self.assertEquals(self.p.protocol.bytes, bytes.replace(cmd, ''))
        self.assertEquals(self.t.value(), '')

    def testIgnoreDont(self):
        # Try to disable an option.  The option is already disabled.  The
        # server should send nothing in response to this.  Doing so could
        # lead to a negotiation loop.
        cmd = telnet.IAC + telnet.DONT + '\x47'

        bytes = "dum de dum" + cmd + "tra la la"
        self.p.dataReceived(bytes)

        self.assertEquals(self.p.protocol.bytes, bytes.replace(cmd, ''))
        self.assertEquals(self.t.value(), '')

    def testIgnoreWill(self):
        # Try to enable an option.  The option is already enabled.  The
        # server should send nothing in response to this.  Doing so could
        # lead to a negotiation loop.
        cmd = telnet.IAC + telnet.WILL + '\x56'

        # Jimmy it - after these two lines, the server will be in a state
        # such that it believes the option to have beenp previously enabled
        # via normal negotiation.
        s = self.p.getOptionState('\x56')
        s.state = 'yes'

        bytes = "tra la la" + cmd + "dum de dum"
        self.p.dataReceived(bytes)

        self.assertEquals(self.p.protocol.bytes, bytes.replace(cmd, ''))
        self.assertEquals(self.t.value(), '')

    def testIgnoreDo(self):
        # Try to enable an option.  The option is already enabled.  The
        # server should send nothing in response to this.  Doing so could
        # lead to a negotiation loop.
        cmd = telnet.IAC + telnet.DO + '\x56'

        # Jimmy it - after these two lines, the server will be in a state
        # such that it believes the option to have beenp previously enabled
        # via normal negotiation.
        s = self.p.getOptionState('\x56')
        s.state = 'yes'

        bytes = "tra la la" + cmd + "dum de dum"
        self.p.dataReceived(bytes)

        self.assertEquals(self.p.protocol.bytes, bytes.replace(cmd, ''))
        self.assertEquals(self.t.value(), '')

    def testAcceptedEnableRequest(self):
        # Try to enable an option through the user-level API.  This
        # returns a Deferred that fires when negotiation about the option
        # finishes.  Make sure it fires, make sure state gets updated
        # properly, make sure the result indicates the option was enabled.
        d = self.p.requestEnable('\x42')

        self.assertEquals(self.t.value(), telnet.IAC + telnet.DO + '\x42')

        self.p.dataReceived(telnet.IAC + telnet.WILL + '\x42')

        self.assertEquals(util.wait(d), True)
        self.assertEquals(self.p.protocol.enabled, ['\x42'])
        self.assertEquals(self.p.protocol.disabled, [])

    def testRefusedEnableRequest(self):
        # Try to enable an option through the user-level API.  This
        # returns a Deferred that fires when negotiation about the option
        # finishes.  Make sure it fires, make sure state gets updated
        # properly, make sure the result indicates the option was enabled.
        d = self.p.requestEnable('\x42')

        self.assertEquals(self.t.value(), telnet.IAC + telnet.DO + '\x42')

        self.p.dataReceived(telnet.IAC + telnet.WONT + '\x42')

        self.assertEquals(util.wait(d), False)
        self.assertEquals(self.p.protocol.enabled, [])
        self.assertEquals(self.p.protocol.disabled, [])

    def testAcceptedDisableRequest(self):
        # Try to enable an option through the user-level API.  This
        # returns a Deferred that fires when negotiation about the option
        # finishes.  Make sure it fires, make sure state gets updated
        # properly, make sure the result indicates the option was enabled.
        s = self.p.getOptionState('\x42')
        s.state = 'yes'

        d = self.p.requestDisable('\x42')

        self.assertEquals(self.t.value(), telnet.IAC + telnet.DONT + '\x42')

        self.p.dataReceived(telnet.IAC + telnet.WONT + '\x42')

        self.assertEquals(util.wait(d), True)
        self.assertEquals(self.p.protocol.enabled, [])
        self.assertEquals(self.p.protocol.disabled, ['\x42'])

    def testNegotiationBlocksFurtherNegotiation(self):
        # Try to enable an option, then immediately try to enable it, then
        # immediately try to disable it.  Ensure that the 2nd and 3rd calls
        # fail quickly with the right exception.
        d = self.p.requestEnable('\x24')

        self.assertRaises(telnet.AlreadyNegotiating, util.wait, self.p.requestEnable('\x24'))
        self.assertRaises(telnet.AlreadyNegotiating, util.wait, self.p.requestDisable('\x24'))

        self.p.dataReceived(telnet.IAC + telnet.WONT + '\x24')

        d = self.p.requestEnable('\x24')
        self.p.dataReceived(telnet.IAC + telnet.WILL + '\x24')
        self.assertEquals(util.wait(d), True)

    def testSuperfluousDisableRequestRaises(self):
        # Try to disable a disabled option.  Make sure it fails properly.
        d = self.p.requestDisable('\xab')
        self.assertRaises(telnet.AlreadyDisabled, util.wait, d)

    def testSuperfluousEnableRequestRaises(self):
        # Try to disable a disabled option.  Make sure it fails properly.
        s = self.p.getOptionState('\xab')
        s.state = 'yes'
        d = self.p.requestEnable('\xab')
        self.assertRaises(telnet.AlreadyEnabled, util.wait, d)
