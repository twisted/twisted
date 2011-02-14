# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for twisted.protocols package.
"""

import struct

from twisted.trial import unittest
from twisted.protocols import basic, wire, portforward
from twisted.internet import reactor, protocol, defer, task, error
from twisted.test import proto_helpers


class LineTester(basic.LineReceiver):
    """
    A line receiver that parses data received and make actions on some tokens.

    @type delimiter: C{str}
    @ivar delimiter: character used between received lines.
    @type MAX_LENGTH: C{int}
    @ivar MAX_LENGTH: size of a line when C{lineLengthExceeded} will be called.
    @type clock: L{twisted.internet.task.Clock}
    @ivar clock: clock simulating reactor callLater. Pass it to constructor if
        you want to use the pause/rawpause functionalities.
    """

    delimiter = '\n'
    MAX_LENGTH = 64

    def __init__(self, clock=None):
        """
        If given, use a clock to make callLater calls.
        """
        self.clock = clock


    def connectionMade(self):
        """
        Create/clean data received on connection.
        """
        self.received = []


    def lineReceived(self, line):
        """
        Receive line and make some action for some tokens: pause, rawpause,
        stop, len, produce, unproduce.
        """
        self.received.append(line)
        if line == '':
            self.setRawMode()
        elif line == 'pause':
            self.pauseProducing()
            self.clock.callLater(0, self.resumeProducing)
        elif line == 'rawpause':
            self.pauseProducing()
            self.setRawMode()
            self.received.append('')
            self.clock.callLater(0, self.resumeProducing)
        elif line == 'stop':
            self.stopProducing()
        elif line[:4] == 'len ':
            self.length = int(line[4:])
        elif line.startswith('produce'):
            self.transport.registerProducer(self, False)
        elif line.startswith('unproduce'):
            self.transport.unregisterProducer()


    def rawDataReceived(self, data):
        """
        Read raw data, until the quantity specified by a previous 'len' line is
        reached.
        """
        data, rest = data[:self.length], data[self.length:]
        self.length = self.length - len(data)
        self.received[-1] = self.received[-1] + data
        if self.length == 0:
            self.setLineMode(rest)


    def lineLengthExceeded(self, line):
        """
        Adjust line mode when long lines received.
        """
        if len(line) > self.MAX_LENGTH + 1:
            self.setLineMode(line[self.MAX_LENGTH + 1:])



class LineOnlyTester(basic.LineOnlyReceiver):
    """
    A buffering line only receiver.
    """
    delimiter = '\n'
    MAX_LENGTH = 64

    def connectionMade(self):
        """
        Create/clean data received on connection.
        """
        self.received = []


    def lineReceived(self, line):
        """
        Save received data.
        """
        self.received.append(line)



class WireTestCase(unittest.TestCase):
    """
    Test wire protocols.
    """

    def test_echo(self):
        """
        Test wire.Echo protocol: send some data and check it send it back.
        """
        t = proto_helpers.StringTransport()
        a = wire.Echo()
        a.makeConnection(t)
        a.dataReceived("hello")
        a.dataReceived("world")
        a.dataReceived("how")
        a.dataReceived("are")
        a.dataReceived("you")
        self.assertEquals(t.value(), "helloworldhowareyou")


    def test_who(self):
        """
        Test wire.Who protocol.
        """
        t = proto_helpers.StringTransport()
        a = wire.Who()
        a.makeConnection(t)
        self.assertEquals(t.value(), "root\r\n")


    def test_QOTD(self):
        """
        Test wire.QOTD protocol.
        """
        t = proto_helpers.StringTransport()
        a = wire.QOTD()
        a.makeConnection(t)
        self.assertEquals(t.value(),
                          "An apple a day keeps the doctor away.\r\n")


    def test_discard(self):
        """
        Test wire.Discard protocol.
        """
        t = proto_helpers.StringTransport()
        a = wire.Discard()
        a.makeConnection(t)
        a.dataReceived("hello")
        a.dataReceived("world")
        a.dataReceived("how")
        a.dataReceived("are")
        a.dataReceived("you")
        self.assertEqual(t.value(), "")



class LineReceiverTestCase(unittest.TestCase):
    """
    Test LineReceiver, using the C{LineTester} wrapper.
    """
    buffer = '''\
len 10

0123456789len 5

1234
len 20
foo 123

0123456789
012345678len 0
foo 5

1234567890123456789012345678901234567890123456789012345678901234567890
len 1

a'''

    output = ['len 10', '0123456789', 'len 5', '1234\n',
              'len 20', 'foo 123', '0123456789\n012345678',
              'len 0', 'foo 5', '', '67890', 'len 1', 'a']

    def testBuffer(self):
        """
        Test buffering for different packet size, checking received matches
        expected data.
        """
        for packet_size in range(1, 10):
            t = proto_helpers.StringIOWithoutClosing()
            a = LineTester()
            a.makeConnection(protocol.FileWrapper(t))
            for i in range(len(self.buffer)/packet_size + 1):
                s = self.buffer[i*packet_size:(i+1)*packet_size]
                a.dataReceived(s)
            self.failUnlessEqual(self.output, a.received)


    pause_buf = 'twiddle1\ntwiddle2\npause\ntwiddle3\n'

    pause_output1 = ['twiddle1', 'twiddle2', 'pause']
    pause_output2 = pause_output1+['twiddle3']


    def test_pausing(self):
        """
        Test pause inside data receiving. It uses fake clock to see if
        pausing/resuming work.
        """
        for packet_size in range(1, 10):
            t = proto_helpers.StringIOWithoutClosing()
            clock = task.Clock()
            a = LineTester(clock)
            a.makeConnection(protocol.FileWrapper(t))
            for i in range(len(self.pause_buf)/packet_size + 1):
                s = self.pause_buf[i*packet_size:(i+1)*packet_size]
                a.dataReceived(s)
            self.assertEquals(self.pause_output1, a.received)
            clock.advance(0)
            self.assertEquals(self.pause_output2, a.received)

    rawpause_buf = 'twiddle1\ntwiddle2\nlen 5\nrawpause\n12345twiddle3\n'

    rawpause_output1 = ['twiddle1', 'twiddle2', 'len 5', 'rawpause', '']
    rawpause_output2 = ['twiddle1', 'twiddle2', 'len 5', 'rawpause', '12345',
                        'twiddle3']


    def test_rawPausing(self):
        """
        Test pause inside raw date receiving.
        """
        for packet_size in range(1, 10):
            t = proto_helpers.StringIOWithoutClosing()
            clock = task.Clock()
            a = LineTester(clock)
            a.makeConnection(protocol.FileWrapper(t))
            for i in range(len(self.rawpause_buf)/packet_size + 1):
                s = self.rawpause_buf[i*packet_size:(i+1)*packet_size]
                a.dataReceived(s)
            self.assertEquals(self.rawpause_output1, a.received)
            clock.advance(0)
            self.assertEquals(self.rawpause_output2, a.received)

    stop_buf = 'twiddle1\ntwiddle2\nstop\nmore\nstuff\n'

    stop_output = ['twiddle1', 'twiddle2', 'stop']


    def test_stopProducing(self):
        """
        Test stop inside producing.
        """
        for packet_size in range(1, 10):
            t = proto_helpers.StringIOWithoutClosing()
            a = LineTester()
            a.makeConnection(protocol.FileWrapper(t))
            for i in range(len(self.stop_buf)/packet_size + 1):
                s = self.stop_buf[i*packet_size:(i+1)*packet_size]
                a.dataReceived(s)
            self.assertEquals(self.stop_output, a.received)


    def test_lineReceiverAsProducer(self):
        """
        Test produce/unproduce in receiving.
        """
        a = LineTester()
        t = proto_helpers.StringIOWithoutClosing()
        a.makeConnection(protocol.FileWrapper(t))
        a.dataReceived('produce\nhello world\nunproduce\ngoodbye\n')
        self.assertEquals(a.received,
                          ['produce', 'hello world', 'unproduce', 'goodbye'])


    def test_clearLineBuffer(self):
        """
        L{LineReceiver.clearLineBuffer} removes all buffered data and returns
        it as a C{str} and can be called from beneath C{dataReceived}.
        """
        class ClearingReceiver(basic.LineReceiver):
            def lineReceived(self, line):
                self.line = line
                self.rest = self.clearLineBuffer()

        protocol = ClearingReceiver()
        protocol.dataReceived('foo\r\nbar\r\nbaz')
        self.assertEqual(protocol.line, 'foo')
        self.assertEqual(protocol.rest, 'bar\r\nbaz')

        # Deliver another line to make sure the previously buffered data is
        # really gone.
        protocol.dataReceived('quux\r\n')
        self.assertEqual(protocol.line, 'quux')
        self.assertEqual(protocol.rest, '')



class LineOnlyReceiverTestCase(unittest.TestCase):
    """
    Test line only receiveer.
    """
    buffer = """foo
    bleakness
    desolation
    plastic forks
    """

    def test_buffer(self):
        """
        Test buffering over line protocol: data received should match buffer.
        """
        t = proto_helpers.StringTransport()
        a = LineOnlyTester()
        a.makeConnection(t)
        for c in self.buffer:
            a.dataReceived(c)
        self.assertEquals(a.received, self.buffer.split('\n')[:-1])


    def test_lineTooLong(self):
        """
        Test sending a line too long: it should close the connection.
        """
        t = proto_helpers.StringTransport()
        a = LineOnlyTester()
        a.makeConnection(t)
        res = a.dataReceived('x'*200)
        self.assertIsInstance(res, error.ConnectionLost)



class TestMixin:

    def connectionMade(self):
        self.received = []


    def stringReceived(self, s):
        self.received.append(s)

    MAX_LENGTH = 50
    closed = 0


    def connectionLost(self, reason):
        self.closed = 1



class TestNetstring(TestMixin, basic.NetstringReceiver):

    def stringReceived(self, s):
        self.received.append(s)
        self.transport.write(s)



class LPTestCaseMixin:

    illegalStrings = []
    protocol = None


    def getProtocol(self):
        """
        Return a new instance of C{self.protocol} connected to a new instance
        of L{proto_helpers.StringTransport}.
        """
        t = proto_helpers.StringTransport()
        a = self.protocol()
        a.makeConnection(t)
        return a


    def test_illegal(self):
        """
        Assert that illegal strings cause the transport to be closed.
        """
        for s in self.illegalStrings:
            r = self.getProtocol()
            for c in s:
                r.dataReceived(c)
            self.assertTrue(r.transport.disconnecting)



class NetstringReceiverTestCase(unittest.TestCase, LPTestCaseMixin):

    strings = ['hello', 'world', 'how', 'are', 'you123', ':today', "a"*515]

    illegalStrings = [
        '9999999999999999999999', 'abc', '4:abcde',
        '51:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab,',]

    protocol = TestNetstring

    def setUp(self):
        self.transport = proto_helpers.StringTransport()
        self.netstringReceiver = TestNetstring()
        self.netstringReceiver.makeConnection(self.transport)


    def test_buffer(self):
        """
        Strings can be received in chunks of different lengths.
        """
        for packet_size in range(1, 10):
            t = proto_helpers.StringTransport()
            a = TestNetstring()
            a.MAX_LENGTH = 699
            a.makeConnection(t)
            for s in self.strings:
                a.sendString(s)
            out = t.value()
            for i in range(len(out)/packet_size + 1):
                s = out[i*packet_size:(i+1)*packet_size]
                if s:
                    a.dataReceived(s)
            self.assertEquals(a.received, self.strings)


    def test_sendNonStrings(self):
        """
        L{basic.NetstringReceiver.sendString} will send objects that are not
        strings by sending their string representation according to str().
        """
        nonStrings = [ [], { 1 : 'a', 2 : 'b' }, ['a', 'b', 'c'], 673,
                       (12, "fine", "and", "you?") ]
        a = TestNetstring()
        t = proto_helpers.StringTransport()
        a.MAX_LENGTH = 100
        a.makeConnection(t)
        for s in nonStrings:
            a.sendString(s)
            out = t.value()
            t.clear()
            length = out[:out.find(":")]
            data = out[out.find(":") + 1:-1] #[:-1] to ignore the trailing ","
            self.assertEquals(int(length), len(str(s)))
            self.assertEquals(data, str(s))

        warnings = self.flushWarnings(
            offendingFunctions=[self.test_sendNonStrings])
        self.assertEqual(len(warnings), 5)
        self.assertEqual(
            warnings[0]["message"],
            "Data passed to sendString() must be a string. Non-string support "
            "is deprecated since Twisted 10.0")
        self.assertEqual(
            warnings[0]['category'],
            DeprecationWarning)


    def test_receiveEmptyNetstring(self):
        """
        Empty netstrings (with length '0') can be received.
        """
        self.netstringReceiver.dataReceived("0:,")
        self.assertEquals(self.netstringReceiver.received, [""])


    def test_receiveOneCharacter(self):
        """
        One-character netstrings can be received.
        """
        self.netstringReceiver.dataReceived("1:a,")
        self.assertEquals(self.netstringReceiver.received, ["a"])


    def test_receiveTwoCharacters(self):
        """
        Two-character netstrings can be received.
        """
        self.netstringReceiver.dataReceived("2:ab,")
        self.assertEquals(self.netstringReceiver.received, ["ab"])


    def test_receiveNestedNetstring(self):
        """
        Netstrings with embedded netstrings. This test makes sure that
        the parser does not become confused about the ',' and ':'
        characters appearing inside the data portion of the netstring.
        """
        self.netstringReceiver.dataReceived("4:1:a,,")
        self.assertEquals(self.netstringReceiver.received, ["1:a,"])


    def test_moreDataThanSpecified(self):
        """
        Netstrings containing more data than expected are refused.
        """
        self.netstringReceiver.dataReceived("2:aaa,")
        self.assertTrue(self.transport.disconnecting)


    def test_moreDataThanSpecifiedBorderCase(self):
        """
        Netstrings that should be empty according to their length
        specification are refused if they contain data.
        """
        self.netstringReceiver.dataReceived("0:a,")
        self.assertTrue(self.transport.disconnecting)


    def test_missingNumber(self):
        """
        Netstrings without leading digits that specify the length
        are refused.
        """
        self.netstringReceiver.dataReceived(":aaa,")
        self.assertTrue(self.transport.disconnecting)


    def test_missingColon(self):
        """
        Netstrings without a colon between length specification and
        data are refused.
        """
        self.netstringReceiver.dataReceived("3aaa,")
        self.assertTrue(self.transport.disconnecting)


    def test_missingNumberAndColon(self):
        """
        Netstrings that have no leading digits nor a colon are
        refused.
        """
        self.netstringReceiver.dataReceived("aaa,")
        self.assertTrue(self.transport.disconnecting)


    def test_onlyData(self):
        """
        Netstrings consisting only of data are refused.
        """
        self.netstringReceiver.dataReceived("aaa")
        self.assertTrue(self.transport.disconnecting)


    def test_receiveNetstringPortions_1(self):
        """
        Netstrings can be received in two portions.
        """
        self.netstringReceiver.dataReceived("4:aa")
        self.netstringReceiver.dataReceived("aa,")
        self.assertEquals(self.netstringReceiver.received, ["aaaa"])
        self.assertTrue(self.netstringReceiver._payloadComplete())


    def test_receiveNetstringPortions_2(self):
        """
        Netstrings can be received in more than two portions, even if
        the length specification is split across two portions.
        """
        for part in ["1", "0:01234", "56789", ","]:
            self.netstringReceiver.dataReceived(part)
        self.assertEquals(self.netstringReceiver.received, ["0123456789"])


    def test_receiveNetstringPortions_3(self):
        """
        Netstrings can be received one character at a time.
        """
        for part in "2:ab,":
            self.netstringReceiver.dataReceived(part)
        self.assertEquals(self.netstringReceiver.received, ["ab"])


    def test_receiveTwoNetstrings(self):
        """
        A stream of two netstrings can be received in two portions,
        where the first portion contains the complete first netstring
        and the length specification of the second netstring.
        """
        self.netstringReceiver.dataReceived("1:a,1")
        self.assertTrue(self.netstringReceiver._payloadComplete())
        self.assertEquals(self.netstringReceiver.received, ["a"])
        self.netstringReceiver.dataReceived(":b,")
        self.assertEquals(self.netstringReceiver.received, ["a", "b"])


    def test_maxReceiveLimit(self):
        """
        Netstrings with a length specification exceeding the specified
        C{MAX_LENGTH} are refused.
        """
        tooLong = self.netstringReceiver.MAX_LENGTH + 1
        self.netstringReceiver.dataReceived("%s:%s" %
                                            (tooLong, "a" * tooLong))
        self.assertTrue(self.transport.disconnecting)


    def test_consumeLength(self):
        """
        C{_consumeLength} returns the expected length of the
        netstring, including the trailing comma.
        """
        self.netstringReceiver._remainingData = "12:"
        self.netstringReceiver._consumeLength()
        self.assertEquals(self.netstringReceiver._expectedPayloadSize, 13)


    def test_consumeLengthBorderCase1(self):
        """
        C{_consumeLength} works as expected if the length specification
        contains the value of C{MAX_LENGTH} (border case).
        """
        self.netstringReceiver._remainingData = "12:"
        self.netstringReceiver.MAX_LENGTH = 12
        self.netstringReceiver._consumeLength()
        self.assertEquals(self.netstringReceiver._expectedPayloadSize, 13)


    def test_consumeLengthBorderCase2(self):
        """
        C{_consumeLength} raises a L{basic.NetstringParseError} if
        the length specification exceeds the value of C{MAX_LENGTH}
        by 1 (border case).
        """
        self.netstringReceiver._remainingData = "12:"
        self.netstringReceiver.MAX_LENGTH = 11
        self.assertRaises(basic.NetstringParseError,
                          self.netstringReceiver._consumeLength)


    def test_consumeLengthBorderCase3(self):
        """
        C{_consumeLength} raises a L{basic.NetstringParseError} if
        the length specification exceeds the value of C{MAX_LENGTH}
        by more than 1.
        """
        self.netstringReceiver._remainingData = "1000:"
        self.netstringReceiver.MAX_LENGTH = 11
        self.assertRaises(basic.NetstringParseError,
                          self.netstringReceiver._consumeLength)


    def test_deprecatedModuleAttributes(self):
        """
        Accessing one of the old module attributes used by the
        NetstringReceiver parser emits a deprecation warning.
        """
        basic.LENGTH, basic.DATA, basic.COMMA, basic.NUMBER
        warnings = self.flushWarnings(
            offendingFunctions=[self.test_deprecatedModuleAttributes])

        self.assertEquals(len(warnings), 4)
        for warning in warnings:
            self.assertEquals(warning['category'], DeprecationWarning)
        self.assertEquals(
            warnings[0]['message'],
            ("twisted.protocols.basic.LENGTH was deprecated in Twisted 10.2.0: "
             "NetstringReceiver parser state is private."))
        self.assertEquals(
            warnings[1]['message'],
            ("twisted.protocols.basic.DATA was deprecated in Twisted 10.2.0: "
             "NetstringReceiver parser state is private."))
        self.assertEquals(
            warnings[2]['message'],
            ("twisted.protocols.basic.COMMA was deprecated in Twisted 10.2.0: "
             "NetstringReceiver parser state is private."))
        self.assertEquals(
            warnings[3]['message'],
            ("twisted.protocols.basic.NUMBER was deprecated in Twisted 10.2.0: "
             "NetstringReceiver parser state is private."))



class IntNTestCaseMixin(LPTestCaseMixin):
    """
    TestCase mixin for int-prefixed protocols.
    """

    protocol = None
    strings = None
    illegalStrings = None
    partialStrings = None

    def test_receive(self):
        """
        Test receiving data find the same data send.
        """
        r = self.getProtocol()
        for s in self.strings:
            for c in struct.pack(r.structFormat,len(s)) + s:
                r.dataReceived(c)
        self.assertEquals(r.received, self.strings)


    def test_partial(self):
        """
        Send partial data, nothing should be definitely received.
        """
        for s in self.partialStrings:
            r = self.getProtocol()
            for c in s:
                r.dataReceived(c)
            self.assertEquals(r.received, [])


    def test_send(self):
        """
        Test sending data over protocol.
        """
        r = self.getProtocol()
        r.sendString("b" * 16)
        self.assertEquals(r.transport.value(),
            struct.pack(r.structFormat, 16) + "b" * 16)


    def test_lengthLimitExceeded(self):
        """
        When a length prefix is received which is greater than the protocol's
        C{MAX_LENGTH} attribute, the C{lengthLimitExceeded} method is called
        with the received length prefix.
        """
        length = []
        r = self.getProtocol()
        r.lengthLimitExceeded = length.append
        r.MAX_LENGTH = 10
        r.dataReceived(struct.pack(r.structFormat, 11))
        self.assertEqual(length, [11])


    def test_longStringNotDelivered(self):
        """
        If a length prefix for a string longer than C{MAX_LENGTH} is delivered
        to C{dataReceived} at the same time as the entire string, the string is
        not passed to C{stringReceived}.
        """
        r = self.getProtocol()
        r.MAX_LENGTH = 10
        r.dataReceived(
            struct.pack(r.structFormat, 11) + 'x' * 11)
        self.assertEqual(r.received, [])



class TestInt32(TestMixin, basic.Int32StringReceiver):
    """
    A L{basic.Int32StringReceiver} storing received strings in an array.

    @ivar received: array holding received strings.
    """



class Int32TestCase(unittest.TestCase, IntNTestCaseMixin):
    """
    Test case for int32-prefixed protocol
    """
    protocol = TestInt32
    strings = ["a", "b" * 16]
    illegalStrings = ["\x10\x00\x00\x00aaaaaa"]
    partialStrings = ["\x00\x00\x00", "hello there", ""]

    def test_data(self):
        """
        Test specific behavior of the 32-bits length.
        """
        r = self.getProtocol()
        r.sendString("foo")
        self.assertEquals(r.transport.value(), "\x00\x00\x00\x03foo")
        r.dataReceived("\x00\x00\x00\x04ubar")
        self.assertEquals(r.received, ["ubar"])



class TestInt16(TestMixin, basic.Int16StringReceiver):
    """
    A L{basic.Int16StringReceiver} storing received strings in an array.

    @ivar received: array holding received strings.
    """



class Int16TestCase(unittest.TestCase, IntNTestCaseMixin):
    """
    Test case for int16-prefixed protocol
    """
    protocol = TestInt16
    strings = ["a", "b" * 16]
    illegalStrings = ["\x10\x00aaaaaa"]
    partialStrings = ["\x00", "hello there", ""]

    def test_data(self):
        """
        Test specific behavior of the 16-bits length.
        """
        r = self.getProtocol()
        r.sendString("foo")
        self.assertEquals(r.transport.value(), "\x00\x03foo")
        r.dataReceived("\x00\x04ubar")
        self.assertEquals(r.received, ["ubar"])


    def test_tooLongSend(self):
        """
        Send too much data: that should cause an error.
        """
        r = self.getProtocol()
        tooSend = "b" * (2**(r.prefixLength*8) + 1)
        self.assertRaises(AssertionError, r.sendString, tooSend)



class TestInt8(TestMixin, basic.Int8StringReceiver):
    """
    A L{basic.Int8StringReceiver} storing received strings in an array.

    @ivar received: array holding received strings.
    """



class Int8TestCase(unittest.TestCase, IntNTestCaseMixin):
    """
    Test case for int8-prefixed protocol
    """
    protocol = TestInt8
    strings = ["a", "b" * 16]
    illegalStrings = ["\x00\x00aaaaaa"]
    partialStrings = ["\x08", "dzadz", ""]


    def test_data(self):
        """
        Test specific behavior of the 8-bits length.
        """
        r = self.getProtocol()
        r.sendString("foo")
        self.assertEquals(r.transport.value(), "\x03foo")
        r.dataReceived("\x04ubar")
        self.assertEquals(r.received, ["ubar"])


    def test_tooLongSend(self):
        """
        Send too much data: that should cause an error.
        """
        r = self.getProtocol()
        tooSend = "b" * (2**(r.prefixLength*8) + 1)
        self.assertRaises(AssertionError, r.sendString, tooSend)



class OnlyProducerTransport(object):
    # Transport which isn't really a transport, just looks like one to
    # someone not looking very hard.

    paused = False
    disconnecting = False

    def __init__(self):
        self.data = []


    def pauseProducing(self):
        self.paused = True


    def resumeProducing(self):
        self.paused = False


    def write(self, bytes):
        self.data.append(bytes)



class ConsumingProtocol(basic.LineReceiver):
    # Protocol that really, really doesn't want any more bytes.

    def lineReceived(self, line):
        self.transport.write(line)
        self.pauseProducing()



class ProducerTestCase(unittest.TestCase):

    def testPauseResume(self):
        p = ConsumingProtocol()
        t = OnlyProducerTransport()
        p.makeConnection(t)

        p.dataReceived('hello, ')
        self.failIf(t.data)
        self.failIf(t.paused)
        self.failIf(p.paused)

        p.dataReceived('world\r\n')

        self.assertEquals(t.data, ['hello, world'])
        self.failUnless(t.paused)
        self.failUnless(p.paused)

        p.resumeProducing()

        self.failIf(t.paused)
        self.failIf(p.paused)

        p.dataReceived('hello\r\nworld\r\n')

        self.assertEquals(t.data, ['hello, world', 'hello'])
        self.failUnless(t.paused)
        self.failUnless(p.paused)

        p.resumeProducing()
        p.dataReceived('goodbye\r\n')

        self.assertEquals(t.data, ['hello, world', 'hello', 'world'])
        self.failUnless(t.paused)
        self.failUnless(p.paused)

        p.resumeProducing()

        self.assertEquals(t.data, ['hello, world', 'hello', 'world', 'goodbye'])
        self.failUnless(t.paused)
        self.failUnless(p.paused)

        p.resumeProducing()

        self.assertEquals(t.data, ['hello, world', 'hello', 'world', 'goodbye'])
        self.failIf(t.paused)
        self.failIf(p.paused)



class TestableProxyClientFactory(portforward.ProxyClientFactory):
    """
    Test proxy client factory that keeps the last created protocol instance.

    @ivar protoInstance: the last instance of the protocol.
    @type protoInstance: L{portforward.ProxyClient}
    """

    def buildProtocol(self, addr):
        """
        Create the protocol instance and keeps track of it.
        """
        proto = portforward.ProxyClientFactory.buildProtocol(self, addr)
        self.protoInstance = proto
        return proto



class TestableProxyFactory(portforward.ProxyFactory):
    """
    Test proxy factory that keeps the last created protocol instance.

    @ivar protoInstance: the last instance of the protocol.
    @type protoInstance: L{portforward.ProxyServer}

    @ivar clientFactoryInstance: client factory used by C{protoInstance} to
        create forward connections.
    @type clientFactoryInstance: L{TestableProxyClientFactory}
    """

    def buildProtocol(self, addr):
        """
        Create the protocol instance, keeps track of it, and makes it use
        C{clientFactoryInstance} as client factory.
        """
        proto = portforward.ProxyFactory.buildProtocol(self, addr)
        self.clientFactoryInstance = TestableProxyClientFactory()
        # Force the use of this specific instance
        proto.clientProtocolFactory = lambda: self.clientFactoryInstance
        self.protoInstance = proto
        return proto



class Portforwarding(unittest.TestCase):
    """
    Test port forwarding.
    """

    def setUp(self):
        self.serverProtocol = wire.Echo()
        self.clientProtocol = protocol.Protocol()
        self.openPorts = []


    def tearDown(self):
        try:
            self.proxyServerFactory.protoInstance.transport.loseConnection()
        except AttributeError:
            pass
        try:
            pi = self.proxyServerFactory.clientFactoryInstance.protoInstance
            pi.transport.loseConnection()
        except AttributeError:
            pass
        try:
            self.clientProtocol.transport.loseConnection()
        except AttributeError:
            pass
        try:
            self.serverProtocol.transport.loseConnection()
        except AttributeError:
            pass
        return defer.gatherResults(
            [defer.maybeDeferred(p.stopListening) for p in self.openPorts])


    def test_portforward(self):
        """
        Test port forwarding through Echo protocol.
        """
        realServerFactory = protocol.ServerFactory()
        realServerFactory.protocol = lambda: self.serverProtocol
        realServerPort = reactor.listenTCP(0, realServerFactory,
                                           interface='127.0.0.1')
        self.openPorts.append(realServerPort)
        self.proxyServerFactory = TestableProxyFactory('127.0.0.1',
                                realServerPort.getHost().port)
        proxyServerPort = reactor.listenTCP(0, self.proxyServerFactory,
                                            interface='127.0.0.1')
        self.openPorts.append(proxyServerPort)

        nBytes = 1000
        received = []
        d = defer.Deferred()

        def testDataReceived(data):
            received.extend(data)
            if len(received) >= nBytes:
                self.assertEquals(''.join(received), 'x' * nBytes)
                d.callback(None)

        self.clientProtocol.dataReceived = testDataReceived

        def testConnectionMade():
            self.clientProtocol.transport.write('x' * nBytes)

        self.clientProtocol.connectionMade = testConnectionMade

        clientFactory = protocol.ClientFactory()
        clientFactory.protocol = lambda: self.clientProtocol

        reactor.connectTCP(
            '127.0.0.1', proxyServerPort.getHost().port, clientFactory)

        return d



class StringTransportTestCase(unittest.TestCase):
    """
    Test L{proto_helpers.StringTransport} helper behaviour.
    """

    def test_noUnicode(self):
        """
        Test that L{proto_helpers.StringTransport} doesn't accept unicode data.
        """
        s = proto_helpers.StringTransport()
        self.assertRaises(TypeError, s.write, u'foo')
