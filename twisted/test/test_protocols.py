# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Test cases for twisted.protocols package.
"""

from twisted.trial import unittest
from twisted.protocols import basic, wire, portforward
from twisted.internet import reactor, protocol, defer

import string, struct
import StringIO

class StringIOWithoutClosing(StringIO.StringIO):
    def close(self):
        pass

class LineTester(basic.LineReceiver):

    delimiter = '\n'
    MAX_LENGTH = 64

    def connectionMade(self):
        self.received = []

    def lineReceived(self, line):
        self.received.append(line)
        if line == '':
            self.setRawMode()
        elif line == 'pause':
            self.pauseProducing()
            reactor.callLater(0, self.resumeProducing)
        elif line == 'rawpause':
            self.pauseProducing()
            self.setRawMode()
            self.received.append('')
            reactor.callLater(0, self.resumeProducing)
        elif line == 'stop':
            self.stopProducing()
        elif line[:4] == 'len ':
            self.length = int(line[4:])
        elif line.startswith('produce'):
            self.transport.registerProducer(self, False)
        elif line.startswith('unproduce'):
            self.transport.unregisterProducer()

    def rawDataReceived(self, data):
        data, rest = data[:self.length], data[self.length:]
        self.length = self.length - len(data)
        self.received[-1] = self.received[-1] + data
        if self.length == 0:
            self.setLineMode(rest)

    def lineLengthExceeded(self, line):
        if len(line) > self.MAX_LENGTH+1:
            self.setLineMode(line[self.MAX_LENGTH+1:])


class LineOnlyTester(basic.LineOnlyReceiver):

    delimiter = '\n'
    MAX_LENGTH = 64

    def connectionMade(self):
        self.received = []

    def lineReceived(self, line):
        self.received.append(line)

class WireTestCase(unittest.TestCase):

    def testEcho(self):
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
        t = StringIOWithoutClosing()
        a = wire.Who()
        a.makeConnection(protocol.FileWrapper(t))
        self.failUnlessEqual(t.getvalue(), "root\r\n")

    def testQOTD(self):
        t = StringIOWithoutClosing()
        a = wire.QOTD()
        a.makeConnection(protocol.FileWrapper(t))
        self.failUnlessEqual(t.getvalue(),
                             "An apple a day keeps the doctor away.\r\n")

    def testDiscard(self):
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
        for packet_size in range(1, 10):
            t = StringIOWithoutClosing()
            a = LineTester()
            a.makeConnection(protocol.FileWrapper(t))
            for i in range(len(self.pause_buf)/packet_size + 1):
                s = self.pause_buf[i*packet_size:(i+1)*packet_size]
                a.dataReceived(s)
            self.failUnlessEqual(self.pause_output1, a.received)
            reactor.iterate(0)
            self.failUnlessEqual(self.pause_output2, a.received)

    rawpause_buf = 'twiddle1\ntwiddle2\nlen 5\nrawpause\n12345twiddle3\n'

    rawpause_output1 = ['twiddle1', 'twiddle2', 'len 5', 'rawpause', '']
    rawpause_output2 = ['twiddle1', 'twiddle2', 'len 5', 'rawpause', '12345', 'twiddle3']

    def testRawPausing(self):
        for packet_size in range(1, 10):
            t = StringIOWithoutClosing()
            a = LineTester()
            a.makeConnection(protocol.FileWrapper(t))
            for i in range(len(self.rawpause_buf)/packet_size + 1):
                s = self.rawpause_buf[i*packet_size:(i+1)*packet_size]
                a.dataReceived(s)
            self.failUnlessEqual(self.rawpause_output1, a.received)
            reactor.iterate(0)
            self.failUnlessEqual(self.rawpause_output2, a.received)

    stop_buf = 'twiddle1\ntwiddle2\nstop\nmore\nstuff\n'

    stop_output = ['twiddle1', 'twiddle2', 'stop']
    def testStopProducing(self):
        for packet_size in range(1, 10):
            t = StringIOWithoutClosing()
            a = LineTester()
            a.makeConnection(protocol.FileWrapper(t))
            for i in range(len(self.stop_buf)/packet_size + 1):
                s = self.stop_buf[i*packet_size:(i+1)*packet_size]
                a.dataReceived(s)
            self.failUnlessEqual(self.stop_output, a.received)


    def testLineReceiverAsProducer(self):
        a = LineTester()
        t = StringIOWithoutClosing()
        a.makeConnection(protocol.FileWrapper(t))
        a.dataReceived('produce\nhello world\nunproduce\ngoodbye\n')
        self.assertEquals(a.received, ['produce', 'hello world', 'unproduce', 'goodbye'])


class LineOnlyReceiverTestCase(unittest.TestCase):

    buffer = """foo
    bleakness
    desolation
    plastic forks
    """

    def testBuffer(self):
        t = StringIOWithoutClosing()
        a = LineOnlyTester()
        a.makeConnection(protocol.FileWrapper(t))
        for c in self.buffer:
            a.dataReceived(c)
        self.failUnlessEqual(a.received, self.buffer.split('\n')[:-1])

    def testLineTooLong(self):
        t = StringIOWithoutClosing()
        a = LineOnlyTester()
        a.makeConnection(protocol.FileWrapper(t))
        res = a.dataReceived('x'*200)
        self.failIfEqual(res, None)
            
                
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

    illegal_strings = []
    protocol = None

    def getProtocol(self):
        t = StringIOWithoutClosing()
        a = self.protocol()
        a.makeConnection(protocol.FileWrapper(t))
        return a
    
    def testIllegal(self):
        for s in self.illegal_strings:
            r = self.getProtocol()
            for c in s:
                r.dataReceived(c)
            self.assertEquals(r.transport.closed, 1)


class NetstringReceiverTestCase(unittest.TestCase, LPTestCaseMixin):

    strings = ['hello', 'world', 'how', 'are', 'you123', ':today', "a"*515]

    illegal_strings = ['9999999999999999999999', 'abc', '4:abcde',
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


class TestInt32(TestMixin, basic.Int32StringReceiver):
    MAX_LENGTH = 50


class Int32TestCase(unittest.TestCase, LPTestCaseMixin):

    protocol = TestInt32
    strings = ["a", "b" * 16]
    illegal_strings = ["\x10\x00\x00\x00aaaaaa"]
    partial_strings = ["\x00\x00\x00", "hello there", ""]
    
    def testPartial(self):
        for s in self.partial_strings:
            r = self.getProtocol()
            r.MAX_LENGTH = 99999999
            for c in s:
                r.dataReceived(c)
            self.assertEquals(r.received, [])

    def testReceive(self):
        r = self.getProtocol()
        for s in self.strings:
            for c in struct.pack("!i",len(s))+s:
                r.dataReceived(c)
        self.assertEquals(r.received, self.strings)


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


class Portforwarding(unittest.TestCase):
    def testPortforward(self):
        serverProtocol = wire.Echo()
        realServerFactory = protocol.ServerFactory()
        realServerFactory.protocol = lambda: serverProtocol
        realServerPort = reactor.listenTCP(0, realServerFactory,
                                           interface='127.0.0.1')

        proxyServerFactory = portforward.ProxyFactory('127.0.0.1',
                                                      realServerPort.getHost().port)
        proxyServerPort = reactor.listenTCP(0, proxyServerFactory,
                                            interface='127.0.0.1')

        nBytes = 1000
        received = []
        clientProtocol = protocol.Protocol()
        clientProtocol.dataReceived = received.extend
        clientProtocol.connectionMade = lambda: clientProtocol.transport.write('x' * nBytes)
        clientFactory = protocol.ClientFactory()
        clientFactory.protocol = lambda: clientProtocol

        reactor.connectTCP('127.0.0.1', proxyServerPort.getHost().port,
                           clientFactory)

        c = 0
        while len(received) < nBytes and c < 100:
            reactor.iterate(0.01)
            c += 1

        self.assertEquals(''.join(received), 'x' * nBytes)
        
        clientProtocol.transport.loseConnection()
        serverProtocol.transport.loseConnection()
        return defer.gatherResults([
            defer.maybeDeferred(realServerPort.stopListening),
            defer.maybeDeferred(proxyServerPort.stopListening)])
