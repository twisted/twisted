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

from pyunit import unittest
from twisted.protocols import basic, wire
from twisted.internet import reactor, protocol

import string
import StringIO

class StringIOWithoutClosing(StringIO.StringIO):

    def close(self):
        pass

class LineTester(basic.LineReceiver):

    delimiter = '\n'

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

len 1

a'''

    output = ['len 10', '0123456789', 'len 5', '1234\n',
              'len 20', 'foo 123', '0123456789\n012345678',
              'len 0', 'foo 5', '', 'len 1', 'a']

    def testBuffer(self):
        for packet_size in range(1, 10):
            t = StringIOWithoutClosing()
            a = LineTester()
            a.makeConnection(protocol.FileWrapper(t))
            for i in range(len(self.buffer)/packet_size + 1):
                s = self.buffer[i*packet_size:(i+1)*packet_size]
                a.dataReceived(s)
            self.failUnlessEqual(self.output, a.received)

class TestNetstring(basic.NetstringReceiver):

    def connectionMade(self):
        self.received = []

    def stringReceived(self, s):
        self.received.append(s)

class TestSafeNetstring(basic.SafeNetstringReceiver):

    MAX_LENGTH = 50
    closed = 0

    def stringReceived(self, s):
        pass

    def connectionLost(self):
        self.closed = 1


class NetstringReceiverTestCase(unittest.TestCase):

    strings = ['hello', 'world', 'how', 'are', 'you123', ':today', "a"*515]

    illegal_strings = ['9999999999999999999999', 'abc', '4:abcde',
                       '51:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab,',]

    def testBuffer(self):
        for packet_size in range(1, 10):
            t = StringIOWithoutClosing()
            a = TestNetstring()
            a.makeConnection(protocol.FileWrapper(t))
            for s in self.strings:
                a.sendString(s)
            out = t.getvalue()
            for i in range(len(out)/packet_size + 1):
                s = out[i*packet_size:(i+1)*packet_size]
                if s:
                    a.dataReceived(s)
            if a.received != self.strings:
                raise AssertionError(a.received)

    def getSafeNS(self):
        t = StringIOWithoutClosing()
        a = TestSafeNetstring()
        a.makeConnection(protocol.FileWrapper(t))
        return a

    def testSafe(self):
        for s in self.illegal_strings:
            r = self.getSafeNS()
            r.dataReceived(s)
            if not r.brokenPeer:
                raise AssertionError("connection wasn't closed on illegal netstring %s" % repr(s))
