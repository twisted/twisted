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

# system imports
import sys

# Twisted Imports
from twisted.internet import protocol

# Sibling Imports
import abstract, fdesc


_stdio_in_use = 0

class StandardIO(abstract.FileDescriptor):
    """I can connect Standard IO to a twisted.protocol.

    I act as a selectable for sys.stdin, and provide a write method that writes
    to stdout.
    """
    
    def __init__(self, protocol):
        """Create me with a protocol.

        This will fail if a StandardIO has already been instantiated.
        """
        abstract.FileDescriptor.__init__(self)
        global _stdio_in_use
        if _stdio_in_use:
            raise RuntimeError, "Standard IO already in use."
        _stdio_in_use = 1
        self.fileno = sys.__stdin__.fileno
        fdesc.setNonBlocking(self.fileno())
        self.protocol = protocol
        self.protocol.makeConnection(self)
        self.startReading()

    def write(self, data):
        """Write some data to standard output.
        """
        sys.__stdout__.write(data)
        # This is an asynchronous framework, but stdout *really* ought to be
        # flushable in a reasonable amount of time.
        sys.__stdout__.flush()
        
    def doRead(self):
        """Some data's readable from standard input.
        """
        return fdesc.readFromFD(self.fileno(), self.protocol.dataReceived)

    def connectionLost(self, reason):
        """The connection was lost.
        """
        self.protocol.connectionLost()
