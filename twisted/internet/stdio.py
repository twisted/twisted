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

"""Standard input/out/err support.

API Stability: unstable (pending deprecation in favor of a reactor-based API)

Future Plans:

    support for stderr, perhaps
    Rewrite to use the reactor instead of an ad-hoc mechanism for connecting
        protocols to transport.

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

# system imports
import sys, os, select, errno

# Sibling Imports
import abstract, fdesc, protocol
from main import CONNECTION_LOST


_stdio_in_use = 0

class StandardIOWriter(abstract.FileDescriptor):

    connected = 1
    ic = 0

    def __init__(self):
        abstract.FileDescriptor.__init__(self)
        self.fileno = sys.__stdout__.fileno
        fdesc.setNonBlocking(self.fileno())
    
    def writeSomeData(self, data):
        try:
            return os.write(self.fileno(), data)
            return rv
        except IOError, io:
            if io.args[0] == errno.EAGAIN:
                return 0
            elif io.args[0] == errno.EPERM:
                return 0
            return CONNECTION_LOST
        except OSError, ose:
            if ose.errno == errno.EPIPE:
                return CONNECTION_LOST
            if ose.errno == errno.EAGAIN:
                return 0
            raise

    def connectionLost(self, reason):
        abstract.FileDescriptor.connectionLost(self, reason)
        os.close(self.fileno())


class StandardIO(abstract.FileDescriptor):
    """I can connect Standard IO to a twisted.protocol
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
        self.startReading()
        self.writer = StandardIOWriter()
        self.protocol.makeConnection(self)
    
    def write(self, data):
        """Write some data to standard output.
        """
        self.writer.write(data)
        
    def doRead(self):
        """Some data's readable from standard input.
        """
        return fdesc.readFromFD(self.fileno(), self.protocol.dataReceived)

    def closeStdin(self):
        """Close standard input.
        """
        self.writer.loseConnection()

    def connectionLost(self, reason):
        """The connection was lost.
        """
        try:
            self.protocol.connectionLost(reason)
        except TypeError:
            import warnings
            warnings.warn("Protocol.connectionLost() should take a 'reason' argument")
            self.protocol.connectionLost()
