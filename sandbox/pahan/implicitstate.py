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

from twisted.internet import protocol

from cStringIO import StringIO
from struct import pack, unpack

def _blowUp(data):
    """A kind reminder"""
    raise NotImplementedError, "please override the implicit_state tuple attribute in the subclass"

class ImplicitStateProtocol(protocol.Protocol):
    implicit_state = (_blowUp, 0)
    buffer = None

    def dataReceived(self, data):
        if not self.buffer:
            self.buffer = StringIO()
        left = self.implicit_state[1] - self.buffer.tell()
        if left > len(data):
            self.buffer.write(data)
            return
        self.buffer.write(data[:left])
        data = data[left:]
        message = self.buffer.getvalue()
        self.buffer.reset()
        self.buffer.truncate()
        next = self.implicit_state[0](message)
        if next is None:
            self.transport.loseConnection()
            return
        self.implicit_state = next

class MyInt32StringReceiver(ImplicitStateProtocol):
    MAX_LENGTH = 99999

    def __init__(self):
        self.implicit_state = (self._getHeader, 4)

    def _getHeader(self, msg):
        length, = unpack("!i", msg)
        if length > self.MAX_LENGTH:
            return None
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

