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
Test cases for twisted.protocols.stateful
"""

from twisted.test import test_protocols
from twisted.protocols.stateful import StatefulProtocol

from struct import pack, unpack

class MyInt32StringReceiver(StatefulProtocol):
    MAX_LENGTH = 99999

    def getInitialState(self):
        return self._getHeader, 4

    def _getHeader(self, msg):
        length, = unpack("!i", msg)
        if length > self.MAX_LENGTH:
            self.transport.loseConnection()
            return
        return self._getString, length

    def _getString(self, msg):
        self.stringReceived(msg)
        return self._getHeader, 4

    def stringReceived(self, msg):
        """Override this.
        """
        raise NotImplementedError

    def sendString(self, data):
        """Send an int32-prefixed string to the other end of the connection.
        """
        self.transport.write(pack("!i",len(data))+data)

class TestInt32(MyInt32StringReceiver):
    def connectionMade(self):
        self.received = []

    def stringReceived(self, s):
        self.received.append(s)

    MAX_LENGTH = 50
    closed = 0

    def connectionLost(self, reason):
        self.closed = 1

class Int32TestCase(test_protocols.Int32TestCase):
    protocol = TestInt32
    def testBigReceive(self):
        r = self.getProtocol()
        big = ""
        for s in self.strings * 4:
            big += pack("!i",len(s))+s
        r.dataReceived(big)
        self.assertEquals(r.received, self.strings * 4)

