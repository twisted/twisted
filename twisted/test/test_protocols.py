# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
Test cases for twisted.protocols package.
"""

from twisted.trial import unittest
from twisted.protocols import basic, wire
from twisted.internet import reactor, protocol

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
        if line[:4] == 'len ':
            self.length = int(line[4:])

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
