# -*- test-case-name: twisted.conch.test.test_telnet -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.conch.telnet}.
"""

from zope.interface import implementer
from zope.interface.verify import verifyObject

from twisted.internet import defer

from twisted.conch import telnet

from twisted.trial import unittest
from twisted.test import proto_helpers



@implementer(telnet.ITelnetProtocol)
class TestProtocol:
    localEnableable = ()
    remoteEnableable = ()

    def __init__(self):
        self.bytes = ''
        self.subcmd = ''
        self.calls = []

        self.enabledLocal = []
        self.enabledRemote = []
        self.disabledLocal = []
        self.disabledRemote = []

    def makeConnection(self, transport):
        d = transport.negotiationMap = {}
        d['\x12'] = self.neg_TEST_COMMAND

        d = transport.commandMap = transport.commandMap.copy()
        for cmd in ('NOP', 'DM', 'BRK', 'IP', 'AO', 'AYT', 'EC', 'EL', 'GA'):
            d[getattr(telnet, cmd)] = lambda arg, cmd=cmd: self.calls.append(cmd)

    def dataReceived(self, bytes):
        self.bytes += bytes

    def connectionLost(self, reason):
        pass

    def neg_TEST_COMMAND(self, payload):
        self.subcmd = payload

    def enableLocal(self, option):
        if option in self.localEnableable:
            self.enabledLocal.append(option)
            return True
        return False

    def disableLocal(self, option):
        self.disabledLocal.append(option)

    def enableRemote(self, option):
        if option in self.remoteEnableable:
            self.enabledRemote.append(option)
            return True
        return False

    def disableRemote(self, option):
        self.disabledRemote.append(option)



class InterfacesTests(unittest.TestCase):
    def test_interface(self):
        """
        L{telnet.TelnetProtocol} implements L{telnet.ITelnetProtocol}
        """
        p = telnet.TelnetProtocol()
        verifyObject(telnet.ITelnetProtocol, p)



class TelnetTransportTests(unittest.TestCase):
    """
    Tests for L{telnet.TelnetTransport}.
    """
    def setUp(self):
        self.p = telnet.TelnetTransport(TestProtocol)
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

        self.assertEqual(h.bytes, ''.join(L))

    def testNewlineHandling(self):
        # Send various kinds of newlines and make sure they get translated
        # into \n.
        h = self.p.protocol

        L = ["here is the first line\r\n",
             "here is the second line\r\0",
             "here is the third line\r\n",
             "here is the last line\r\0"]

        for b in L:
            self.p.dataReceived(b)

        self.assertEqual(h.bytes, L[0][:-2] + '\n' +
                          L[1][:-2] + '\r' +
                          L[2][:-2] + '\n' +
                          L[3][:-2] + '\r')

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

        self.assertEqual(h.bytes, ''.join(L).replace('\xff\xff', '\xff'))

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

        self.assertEqual(h.calls, [cmdName])
        self.assertEqual(h.bytes, ''.join(L).replace(cmd, ''))

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

        cmd = telnet.IAC + telnet.SB + '\x12hello world' + telnet.IAC + telnet.SE
        L = ["These are some bytes but soon" + cmd,
             "there will be some more"]

        for b in L:
            self.p.dataReceived(b)

        self.assertEqual(h.bytes, ''.join(L).replace(cmd, ''))
        self.assertEqual(h.subcmd, list("hello world"))

    def testSubnegotiationWithEmbeddedSE(self):
        # Send a subnegotiation command with an embedded SE.  Make sure
        # that SE gets passed to the correct method.
        h = self.p.protocol

        cmd = (telnet.IAC + telnet.SB +
               '\x12' + telnet.SE +
               telnet.IAC + telnet.SE)

        L = ["Some bytes are here" + cmd + "and here",
             "and here"]

        for b in L:
            self.p.dataReceived(b)

        self.assertEqual(h.bytes, ''.join(L).replace(cmd, ''))
        self.assertEqual(h.subcmd, [telnet.SE])

    def testBoundarySubnegotiation(self):
        # Send a subnegotiation command.  Split it at every possible byte boundary
        # and make sure it always gets parsed and that it is passed to the correct
        # method.
        cmd = (telnet.IAC + telnet.SB +
               '\x12' + telnet.SE + 'hello' +
               telnet.IAC + telnet.SE)

        for i in range(len(cmd)):
            h = self.p.protocol = TestProtocol()
            h.makeConnection(self.p)

            a, b = cmd[:i], cmd[i:]
            L = ["first part" + a,
                 b + "last part"]

            for bytes in L:
                self.p.dataReceived(bytes)

            self.assertEqual(h.bytes, ''.join(L).replace(cmd, ''))
            self.assertEqual(h.subcmd, [telnet.SE] + list('hello'))

    def _enabledHelper(self, o, eL=[], eR=[], dL=[], dR=[]):
        self.assertEqual(o.enabledLocal, eL)
        self.assertEqual(o.enabledRemote, eR)
        self.assertEqual(o.disabledLocal, dL)
        self.assertEqual(o.disabledRemote, dR)

    def testRefuseWill(self):
        # Try to enable an option.  The server should refuse to enable it.
        cmd = telnet.IAC + telnet.WILL + '\x12'

        bytes = "surrounding bytes" + cmd + "to spice things up"
        self.p.dataReceived(bytes)

        self.assertEqual(self.p.protocol.bytes, bytes.replace(cmd, ''))
        self.assertEqual(self.t.value(), telnet.IAC + telnet.DONT + '\x12')
        self._enabledHelper(self.p.protocol)

    def testRefuseDo(self):
        # Try to enable an option.  The server should refuse to enable it.
        cmd = telnet.IAC + telnet.DO + '\x12'

        bytes = "surrounding bytes" + cmd + "to spice things up"
        self.p.dataReceived(bytes)

        self.assertEqual(self.p.protocol.bytes, bytes.replace(cmd, ''))
        self.assertEqual(self.t.value(), telnet.IAC + telnet.WONT + '\x12')
        self._enabledHelper(self.p.protocol)

    def testAcceptDo(self):
        # Try to enable an option.  The option is in our allowEnable
        # list, so we will allow it to be enabled.
        cmd = telnet.IAC + telnet.DO + '\x19'
        bytes = 'padding' + cmd + 'trailer'

        h = self.p.protocol
        h.localEnableable = ('\x19',)
        self.p.dataReceived(bytes)

        self.assertEqual(self.t.value(), telnet.IAC + telnet.WILL + '\x19')
        self._enabledHelper(h, eL=['\x19'])

    def testAcceptWill(self):
        # Same as testAcceptDo, but reversed.
        cmd = telnet.IAC + telnet.WILL + '\x91'
        bytes = 'header' + cmd + 'padding'

        h = self.p.protocol
        h.remoteEnableable = ('\x91',)
        self.p.dataReceived(bytes)

        self.assertEqual(self.t.value(), telnet.IAC + telnet.DO + '\x91')
        self._enabledHelper(h, eR=['\x91'])

    def testAcceptWont(self):
        # Try to disable an option.  The server must allow any option to
        # be disabled at any time.  Make sure it disables it and sends
        # back an acknowledgement of this.
        cmd = telnet.IAC + telnet.WONT + '\x29'

        # Jimmy it - after these two lines, the server will be in a state
        # such that it believes the option to have been previously enabled
        # via normal negotiation.
        s = self.p.getOptionState('\x29')
        s.him.state = 'yes'

        bytes = "fiddle dee" + cmd
        self.p.dataReceived(bytes)

        self.assertEqual(self.p.protocol.bytes, bytes.replace(cmd, ''))
        self.assertEqual(self.t.value(), telnet.IAC + telnet.DONT + '\x29')
        self.assertEqual(s.him.state, 'no')
        self._enabledHelper(self.p.protocol, dR=['\x29'])

    def testAcceptDont(self):
        # Try to disable an option.  The server must allow any option to
        # be disabled at any time.  Make sure it disables it and sends
        # back an acknowledgement of this.
        cmd = telnet.IAC + telnet.DONT + '\x29'

        # Jimmy it - after these two lines, the server will be in a state
        # such that it believes the option to have beenp previously enabled
        # via normal negotiation.
        s = self.p.getOptionState('\x29')
        s.us.state = 'yes'

        bytes = "fiddle dum " + cmd
        self.p.dataReceived(bytes)

        self.assertEqual(self.p.protocol.bytes, bytes.replace(cmd, ''))
        self.assertEqual(self.t.value(), telnet.IAC + telnet.WONT + '\x29')
        self.assertEqual(s.us.state, 'no')
        self._enabledHelper(self.p.protocol, dL=['\x29'])

    def testIgnoreWont(self):
        # Try to disable an option.  The option is already disabled.  The
        # server should send nothing in response to this.
        cmd = telnet.IAC + telnet.WONT + '\x47'

        bytes = "dum de dum" + cmd + "tra la la"
        self.p.dataReceived(bytes)

        self.assertEqual(self.p.protocol.bytes, bytes.replace(cmd, ''))
        self.assertEqual(self.t.value(), '')
        self._enabledHelper(self.p.protocol)

    def testIgnoreDont(self):
        # Try to disable an option.  The option is already disabled.  The
        # server should send nothing in response to this.  Doing so could
        # lead to a negotiation loop.
        cmd = telnet.IAC + telnet.DONT + '\x47'

        bytes = "dum de dum" + cmd + "tra la la"
        self.p.dataReceived(bytes)

        self.assertEqual(self.p.protocol.bytes, bytes.replace(cmd, ''))
        self.assertEqual(self.t.value(), '')
        self._enabledHelper(self.p.protocol)

    def testIgnoreWill(self):
        # Try to enable an option.  The option is already enabled.  The
        # server should send nothing in response to this.  Doing so could
        # lead to a negotiation loop.
        cmd = telnet.IAC + telnet.WILL + '\x56'

        # Jimmy it - after these two lines, the server will be in a state
        # such that it believes the option to have been previously enabled
        # via normal negotiation.
        s = self.p.getOptionState('\x56')
        s.him.state = 'yes'

        bytes = "tra la la" + cmd + "dum de dum"
        self.p.dataReceived(bytes)

        self.assertEqual(self.p.protocol.bytes, bytes.replace(cmd, ''))
        self.assertEqual(self.t.value(), '')
        self._enabledHelper(self.p.protocol)

    def testIgnoreDo(self):
        # Try to enable an option.  The option is already enabled.  The
        # server should send nothing in response to this.  Doing so could
        # lead to a negotiation loop.
        cmd = telnet.IAC + telnet.DO + '\x56'

        # Jimmy it - after these two lines, the server will be in a state
        # such that it believes the option to have been previously enabled
        # via normal negotiation.
        s = self.p.getOptionState('\x56')
        s.us.state = 'yes'

        bytes = "tra la la" + cmd + "dum de dum"
        self.p.dataReceived(bytes)

        self.assertEqual(self.p.protocol.bytes, bytes.replace(cmd, ''))
        self.assertEqual(self.t.value(), '')
        self._enabledHelper(self.p.protocol)

    def testAcceptedEnableRequest(self):
        # Try to enable an option through the user-level API.  This
        # returns a Deferred that fires when negotiation about the option
        # finishes.  Make sure it fires, make sure state gets updated
        # properly, make sure the result indicates the option was enabled.
        d = self.p.do('\x42')

        h = self.p.protocol
        h.remoteEnableable = ('\x42',)

        self.assertEqual(self.t.value(), telnet.IAC + telnet.DO + '\x42')

        self.p.dataReceived(telnet.IAC + telnet.WILL + '\x42')

        d.addCallback(self.assertEqual, True)
        d.addCallback(lambda _:  self._enabledHelper(h, eR=['\x42']))
        return d


    def test_refusedEnableRequest(self):
        """
        If the peer refuses to enable an option we request it to enable, the
        L{Deferred} returned by L{TelnetProtocol.do} fires with an
        L{OptionRefused} L{Failure}.
        """
        # Try to enable an option through the user-level API.  This returns a
        # Deferred that fires when negotiation about the option finishes.  Make
        # sure it fires, make sure state gets updated properly, make sure the
        # result indicates the option was enabled.
        self.p.protocol.remoteEnableable = ('\x42',)
        d = self.p.do('\x42')

        self.assertEqual(self.t.value(), telnet.IAC + telnet.DO + '\x42')

        s = self.p.getOptionState('\x42')
        self.assertEqual(s.him.state, 'no')
        self.assertEqual(s.us.state, 'no')
        self.assertEqual(s.him.negotiating, True)
        self.assertEqual(s.us.negotiating, False)

        self.p.dataReceived(telnet.IAC + telnet.WONT + '\x42')

        d = self.assertFailure(d, telnet.OptionRefused)
        d.addCallback(lambda ignored: self._enabledHelper(self.p.protocol))
        d.addCallback(
            lambda ignored: self.assertEqual(s.him.negotiating, False))
        return d


    def test_refusedEnableOffer(self):
        """
        If the peer refuses to allow us to enable an option, the L{Deferred}
        returned by L{TelnetProtocol.will} fires with an L{OptionRefused}
        L{Failure}.
        """
        # Try to offer an option through the user-level API.  This returns a
        # Deferred that fires when negotiation about the option finishes.  Make
        # sure it fires, make sure state gets updated properly, make sure the
        # result indicates the option was enabled.
        self.p.protocol.localEnableable = ('\x42',)
        d = self.p.will('\x42')

        self.assertEqual(self.t.value(), telnet.IAC + telnet.WILL + '\x42')

        s = self.p.getOptionState('\x42')
        self.assertEqual(s.him.state, 'no')
        self.assertEqual(s.us.state, 'no')
        self.assertEqual(s.him.negotiating, False)
        self.assertEqual(s.us.negotiating, True)

        self.p.dataReceived(telnet.IAC + telnet.DONT + '\x42')

        d = self.assertFailure(d, telnet.OptionRefused)
        d.addCallback(lambda ignored: self._enabledHelper(self.p.protocol))
        d.addCallback(
            lambda ignored: self.assertEqual(s.us.negotiating, False))
        return d


    def testAcceptedDisableRequest(self):
        # Try to disable an option through the user-level API.  This
        # returns a Deferred that fires when negotiation about the option
        # finishes.  Make sure it fires, make sure state gets updated
        # properly, make sure the result indicates the option was enabled.
        s = self.p.getOptionState('\x42')
        s.him.state = 'yes'

        d = self.p.dont('\x42')

        self.assertEqual(self.t.value(), telnet.IAC + telnet.DONT + '\x42')

        self.p.dataReceived(telnet.IAC + telnet.WONT + '\x42')

        d.addCallback(self.assertEqual, True)
        d.addCallback(lambda _: self._enabledHelper(self.p.protocol,
                                                    dR=['\x42']))
        return d

    def testNegotiationBlocksFurtherNegotiation(self):
        # Try to disable an option, then immediately try to enable it, then
        # immediately try to disable it.  Ensure that the 2nd and 3rd calls
        # fail quickly with the right exception.
        s = self.p.getOptionState('\x24')
        s.him.state = 'yes'
        self.p.dont('\x24') # fires after the first line of _final

        def _do(x):
            d = self.p.do('\x24')
            return self.assertFailure(d, telnet.AlreadyNegotiating)

        def _dont(x):
            d = self.p.dont('\x24')
            return self.assertFailure(d, telnet.AlreadyNegotiating)

        def _final(x):
            self.p.dataReceived(telnet.IAC + telnet.WONT + '\x24')
            # an assertion that only passes if d2 has fired
            self._enabledHelper(self.p.protocol, dR=['\x24'])
            # Make sure we allow this
            self.p.protocol.remoteEnableable = ('\x24',)
            d = self.p.do('\x24')
            self.p.dataReceived(telnet.IAC + telnet.WILL + '\x24')
            d.addCallback(self.assertEqual, True)
            d.addCallback(lambda _: self._enabledHelper(self.p.protocol,
                                                        eR=['\x24'],
                                                        dR=['\x24']))
            return d

        d = _do(None)
        d.addCallback(_dont)
        d.addCallback(_final)
        return d

    def testSuperfluousDisableRequestRaises(self):
        # Try to disable a disabled option.  Make sure it fails properly.
        d = self.p.dont('\xab')
        return self.assertFailure(d, telnet.AlreadyDisabled)

    def testSuperfluousEnableRequestRaises(self):
        # Try to disable a disabled option.  Make sure it fails properly.
        s = self.p.getOptionState('\xab')
        s.him.state = 'yes'
        d = self.p.do('\xab')
        return self.assertFailure(d, telnet.AlreadyEnabled)

    def testLostConnectionFailsDeferreds(self):
        d1 = self.p.do('\x12')
        d2 = self.p.do('\x23')
        d3 = self.p.do('\x34')

        class TestException(Exception):
            pass

        self.p.connectionLost(TestException("Total failure!"))

        d1 = self.assertFailure(d1, TestException)
        d2 = self.assertFailure(d2, TestException)
        d3 = self.assertFailure(d3, TestException)
        return defer.gatherResults([d1, d2, d3])


class TestTelnet(telnet.Telnet):
    """
    A trivial extension of the telnet protocol class useful to unit tests.
    """
    def __init__(self):
        telnet.Telnet.__init__(self)
        self.events = []


    def applicationDataReceived(self, bytes):
        """
        Record the given data in C{self.events}.
        """
        self.events.append(('bytes', bytes))


    def unhandledCommand(self, command, bytes):
        """
        Record the given command in C{self.events}.
        """
        self.events.append(('command', command, bytes))


    def unhandledSubnegotiation(self, command, bytes):
        """
        Record the given subnegotiation command in C{self.events}.
        """
        self.events.append(('negotiate', command, bytes))



class TelnetTests(unittest.TestCase):
    """
    Tests for L{telnet.Telnet}.

    L{telnet.Telnet} implements the TELNET protocol (RFC 854), including option
    and suboption negotiation, and option state tracking.
    """
    def setUp(self):
        """
        Create an unconnected L{telnet.Telnet} to be used by tests.
        """
        self.protocol = TestTelnet()


    def test_enableLocal(self):
        """
        L{telnet.Telnet.enableLocal} should reject all options, since
        L{telnet.Telnet} does not know how to implement any options.
        """
        self.assertFalse(self.protocol.enableLocal('\0'))


    def test_enableRemote(self):
        """
        L{telnet.Telnet.enableRemote} should reject all options, since
        L{telnet.Telnet} does not know how to implement any options.
        """
        self.assertFalse(self.protocol.enableRemote('\0'))


    def test_disableLocal(self):
        """
        It is an error for L{telnet.Telnet.disableLocal} to be called, since
        L{telnet.Telnet.enableLocal} will never allow any options to be enabled
        locally.  If a subclass overrides enableLocal, it must also override
        disableLocal.
        """
        self.assertRaises(NotImplementedError, self.protocol.disableLocal, '\0')


    def test_disableRemote(self):
        """
        It is an error for L{telnet.Telnet.disableRemote} to be called, since
        L{telnet.Telnet.enableRemote} will never allow any options to be
        enabled remotely.  If a subclass overrides enableRemote, it must also
        override disableRemote.
        """
        self.assertRaises(NotImplementedError, self.protocol.disableRemote, '\0')


    def test_requestNegotiation(self):
        """
        L{telnet.Telnet.requestNegotiation} formats the feature byte and the
        payload bytes into the subnegotiation format and sends them.

        See RFC 855.
        """
        transport = proto_helpers.StringTransport()
        self.protocol.makeConnection(transport)
        self.protocol.requestNegotiation('\x01', '\x02\x03')
        self.assertEqual(
            transport.value(),
            # IAC SB feature bytes IAC SE
            '\xff\xfa\x01\x02\x03\xff\xf0')


    def test_requestNegotiationEscapesIAC(self):
        """
        If the payload for a subnegotiation includes I{IAC}, it is escaped by
        L{telnet.Telnet.requestNegotiation} with another I{IAC}.

        See RFC 855.
        """
        transport = proto_helpers.StringTransport()
        self.protocol.makeConnection(transport)
        self.protocol.requestNegotiation('\x01', '\xff')
        self.assertEqual(
            transport.value(),
            '\xff\xfa\x01\xff\xff\xff\xf0')


    def _deliver(self, bytes, *expected):
        """
        Pass the given bytes to the protocol's C{dataReceived} method and
        assert that the given events occur.
        """
        received = self.protocol.events = []
        self.protocol.dataReceived(bytes)
        self.assertEqual(received, list(expected))


    def test_oneApplicationDataByte(self):
        """
        One application-data byte in the default state gets delivered right
        away.
        """
        self._deliver('a', ('bytes', 'a'))


    def test_twoApplicationDataBytes(self):
        """
        Two application-data bytes in the default state get delivered
        together.
        """
        self._deliver('bc', ('bytes', 'bc'))


    def test_threeApplicationDataBytes(self):
        """
        Three application-data bytes followed by a control byte get
        delivered, but the control byte doesn't.
        """
        self._deliver('def' + telnet.IAC, ('bytes', 'def'))


    def test_escapedControl(self):
        """
        IAC in the escaped state gets delivered and so does another
        application-data byte following it.
        """
        self._deliver(telnet.IAC)
        self._deliver(telnet.IAC + 'g', ('bytes', telnet.IAC + 'g'))


    def test_carriageReturn(self):
        """
        A carriage return only puts the protocol into the newline state.  A
        linefeed in the newline state causes just the newline to be
        delivered.  A nul in the newline state causes a carriage return to
        be delivered.  An IAC in the newline state causes a carriage return
        to be delivered and puts the protocol into the escaped state. 
        Anything else causes a carriage return and that thing to be
        delivered.
        """
        self._deliver('\r')
        self._deliver('\n', ('bytes', '\n'))
        self._deliver('\r\n', ('bytes', '\n'))

        self._deliver('\r')
        self._deliver('\0', ('bytes', '\r'))
        self._deliver('\r\0', ('bytes', '\r'))

        self._deliver('\r')
        self._deliver('a', ('bytes', '\ra'))
        self._deliver('\ra', ('bytes', '\ra'))

        self._deliver('\r')
        self._deliver(
            telnet.IAC + telnet.IAC + 'x', ('bytes', '\r' + telnet.IAC + 'x'))


    def test_applicationDataBeforeSimpleCommand(self):
        """
        Application bytes received before a command are delivered before the
        command is processed.
        """
        self._deliver(
            'x' + telnet.IAC + telnet.NOP,
            ('bytes', 'x'), ('command', telnet.NOP, None))


    def test_applicationDataBeforeCommand(self):
        """
        Application bytes received before a WILL/WONT/DO/DONT are delivered
        before the command is processed.
        """
        self.protocol.commandMap = {}
        self._deliver(
            'y' + telnet.IAC + telnet.WILL + '\x00',
            ('bytes', 'y'), ('command', telnet.WILL, '\x00'))


    def test_applicationDataBeforeSubnegotiation(self):
        """
        Application bytes received before a subnegotiation command are
        delivered before the negotiation is processed.
        """
        self._deliver(
            'z' + telnet.IAC + telnet.SB + 'Qx' + telnet.IAC + telnet.SE,
            ('bytes', 'z'), ('negotiate', 'Q', ['x']))
