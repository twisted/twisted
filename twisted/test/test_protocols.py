# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Test cases for twisted.protocols package.
"""

from twisted.trial import unittest
from twisted.protocols import basic, wire, portforward
from twisted.internet import reactor, protocol, defer, task, error
from twisted.test import proto_helpers

import struct
import StringIO

class StringIOWithoutClosing(StringIO.StringIO):
    """
    A StringIO that can't be closed.
    """
    def close(self):
        """
        Do nothing.
        """

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
    def testEcho(self):
        """
        Test wire.Echo protocol: send some data and check it send it back.
        """
        t = StringIOWithoutClosing()
        a = wire.Echo()
        a.makeConnection(protocol.FileWrapper(t))
        a.dataReceived("hello")
        a.dataReceived("world")
        a.dataReceived("how")
        a.dataReceived("are")
        a.dataReceived("you")
        self.failUnlessEqual(t.getvalue(), "helloworldhowareyou")

    def testWho(self):
        """
        Test wire.Who protocol.
        """
        t = StringIOWithoutClosing()
        a = wire.Who()
        a.makeConnection(protocol.FileWrapper(t))
        self.failUnlessEqual(t.getvalue(), "root\r\n")

    def testQOTD(self):
        """
        Test wire.QOTD protocol.
        """
        t = StringIOWithoutClosing()
        a = wire.QOTD()
        a.makeConnection(protocol.FileWrapper(t))
        self.failUnlessEqual(t.getvalue(),
                             "An apple a day keeps the doctor away.\r\n")

    def testDiscard(self):
        """
        Test wire.Discard protocol.
        """
        t = StringIOWithoutClosing()
        a = wire.Discard()
        a.makeConnection(protocol.FileWrapper(t))
        a.dataReceived("hello")
        a.dataReceived("world")
        a.dataReceived("how")
        a.dataReceived("are")
        a.dataReceived("you")
        self.failUnlessEqual(t.getvalue(), "")

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
            t = StringIOWithoutClosing()
            a = LineTester()
            a.makeConnection(protocol.FileWrapper(t))
            for i in range(len(self.buffer)/packet_size + 1):
                s = self.buffer[i*packet_size:(i+1)*packet_size]
                a.dataReceived(s)
            self.failUnlessEqual(self.output, a.received)


    pause_buf = 'twiddle1\ntwiddle2\npause\ntwiddle3\n'

    pause_output1 = ['twiddle1', 'twiddle2', 'pause']
    pause_output2 = pause_output1+['twiddle3']

    def testPausing(self):
        """
        Test pause inside data receiving. It uses fake clock to see if
        pausing/resuming work.
        """
        for packet_size in range(1, 10):
            t = StringIOWithoutClosing()
            clock = task.Clock()
            a = LineTester(clock)
            a.makeConnection(protocol.FileWrapper(t))
            for i in range(len(self.pause_buf)/packet_size + 1):
                s = self.pause_buf[i*packet_size:(i+1)*packet_size]
                a.dataReceived(s)
            self.failUnlessEqual(self.pause_output1, a.received)
            clock.advance(0)
            self.failUnlessEqual(self.pause_output2, a.received)

    rawpause_buf = 'twiddle1\ntwiddle2\nlen 5\nrawpause\n12345twiddle3\n'

    rawpause_output1 = ['twiddle1', 'twiddle2', 'len 5', 'rawpause', '']
    rawpause_output2 = ['twiddle1', 'twiddle2', 'len 5', 'rawpause', '12345',
                        'twiddle3']

    def testRawPausing(self):
        """
        Test pause inside raw date receiving.
        """
        for packet_size in range(1, 10):
            t = StringIOWithoutClosing()
            clock = task.Clock()
            a = LineTester(clock)
            a.makeConnection(protocol.FileWrapper(t))
            for i in range(len(self.rawpause_buf)/packet_size + 1):
                s = self.rawpause_buf[i*packet_size:(i+1)*packet_size]
                a.dataReceived(s)
            self.failUnlessEqual(self.rawpause_output1, a.received)
            clock.advance(0)
            self.failUnlessEqual(self.rawpause_output2, a.received)

    stop_buf = 'twiddle1\ntwiddle2\nstop\nmore\nstuff\n'

    stop_output = ['twiddle1', 'twiddle2', 'stop']

    def testStopProducing(self):
        """
        Test stop inside producing.
        """
        for packet_size in range(1, 10):
            t = StringIOWithoutClosing()
            a = LineTester()
            a.makeConnection(protocol.FileWrapper(t))
            for i in range(len(self.stop_buf)/packet_size + 1):
                s = self.stop_buf[i*packet_size:(i+1)*packet_size]
                a.dataReceived(s)
            self.failUnlessEqual(self.stop_output, a.received)


    def testLineReceiverAsProducer(self):
        """
        Test produce/unproduce in receiving.
        """
        a = LineTester()
        t = StringIOWithoutClosing()
        a.makeConnection(protocol.FileWrapper(t))
        a.dataReceived('produce\nhello world\nunproduce\ngoodbye\n')
        self.assertEquals(a.received,
                          ['produce', 'hello world', 'unproduce', 'goodbye'])


class LineOnlyReceiverTestCase(unittest.TestCase):
    """
    Test line only receiveer.
    """
    buffer = """foo
    bleakness
    desolation
    plastic forks
    """

    def testBuffer(self):
        """
        Test buffering over line protocol: data received should match buffer.
        """
        t = StringIOWithoutClosing()
        a = LineOnlyTester()
        a.makeConnection(protocol.FileWrapper(t))
        for c in self.buffer:
            a.dataReceived(c)
        self.failUnlessEqual(a.received, self.buffer.split('\n')[:-1])

    def testLineTooLong(self):
        """
        Test sending a line too long: it should close the connection.
        """
        t = StringIOWithoutClosing()
        a = LineOnlyTester()
        a.makeConnection(protocol.FileWrapper(t))
        res = a.dataReceived('x'*200)
        self.assertTrue(isinstance(res, error.ConnectionLost))



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
    pass


class LPTestCaseMixin:

    illegalStrings = []
    protocol = None

    def getProtocol(self):
        t = StringIOWithoutClosing()
        a = self.protocol()
        a.makeConnection(protocol.FileWrapper(t))
        return a

    def test_illegal(self):
        """
        Assert that illegal strings cause the transport to be closed.
        """
        for s in self.illegalStrings:
            r = self.getProtocol()
            for c in s:
                r.dataReceived(c)
            self.assertEquals(r.transport.closed, 1)


class NetstringReceiverTestCase(unittest.TestCase, LPTestCaseMixin):

    strings = ['hello', 'world', 'how', 'are', 'you123', ':today', "a"*515]

    illegalStrings = [
        '9999999999999999999999', 'abc', '4:abcde',
        '51:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab,',]

    protocol = TestNetstring

    def testBuffer(self):
        for packet_size in range(1, 10):
            t = StringIOWithoutClosing()
            a = TestNetstring()
            a.MAX_LENGTH = 699
            a.makeConnection(protocol.FileWrapper(t))
            for s in self.strings:
                a.sendString(s)
            out = t.getvalue()
            for i in range(len(out)/packet_size + 1):
                s = out[i*packet_size:(i+1)*packet_size]
                if s:
                    a.dataReceived(s)
            self.assertEquals(a.received, self.strings)


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
            for c in struct.pack(self.protocol.structFormat,len(s)) + s:
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
        self.assertEquals(r.transport.file.getvalue(),
            struct.pack(self.protocol.structFormat, 16) + "b" * 16)


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
        r.dataReceived(struct.pack(self.protocol.structFormat, 11))
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
            struct.pack(self.protocol.structFormat, 11) + 'x' * 11)
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
        self.assertEquals(r.transport.file.getvalue(), "\x00\x00\x00\x03foo")
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
        self.assertEquals(r.transport.file.getvalue(), "\x00\x03foo")
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
        self.assertEquals(r.transport.file.getvalue(), "\x03foo")
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
            self.proxyServerFactory.clientFactoryInstance.protoInstance.transport.loseConnection()
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
