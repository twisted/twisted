
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

"""Various asynchronous UDP classes.
"""

# System Imports
import os
import copy
import socket
import traceback

# Twisted Imports
from twisted.protocols import protocol
from twisted.persisted import styles
from twisted.python import log

# Sibling Imports
import abstract

class Port(abstract.FileDescriptor):
    """I am a UDP server port, listening for packets.

    When a packet is received, I will call my factory's packetReceived
    with the packet and an address.
    """
    
    def __init__(self, port, factory, maxPacketSize=8192):
        """Initialize with a numeric port to listen on.
        """
        self.port = port
        self.factory = factory
        self.maxPacketSize = maxPacketSize

    def __repr__(self):
        return "<%s on %s>" % (self.factory.__class__, self.port)
        
    def createInternetSocket(self):
        """(internal) create an AF_INET/SOCK_DGRAM socket.
        """
        s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        return s

    def __getstate__(self):
        """(internal) get my state for persistence
        """
        dct = copy.copy(self.__dict__)
        try: del dct['socket']
        except KeyError: pass
        try: del dct['fileno']
        except KeyError: pass

        return dct

    def startListening(self):
        """Create and bind my socket, and begin listening on it.
        
        This is called on unserialization, and must be called after creating a
        server to begin listening on the specified port.
        """
        log.msg("%s starting on %s"%(self.factory.__class__, self.port))
        skt = self.createInternetSocket()
        skt.bind( ('',self.port) )
        self.connected = 1
        self.socket = skt
        self.fileno = self.socket.fileno
        self.startReading()

    def doRead(self):
        """Called when my socket is ready for reading.
        
        This gets a packet and calls the factory's packetReceived
        method to handle it.
        """
        try:
            data, addr = self.socket.recvfrom(self.maxPacketSize)
            self.factory.packetReceived(data, addr, self)
        except:
            traceback.print_exc(file=log.logfile)

    def doWrite(self):
        """Raises an AssertionError.
        """
        assert 0, "doWrite called on a %s" % str(self.__class__)

    def loseConnection(self):
        """ Stop accepting connections on this port.
        
        This will shut down my socket and call self.connectionLost().
        """
        # Since ports can't, by definition, write any data, we can just close
        # instantly (no need for the more complex stuff for selectables which
        # write)
        removeReader(self)
        self.connectionLost()

    def connectionLost(self):
        """Cleans up my socket.
        """
        log.msg('(Port %s Closed)' % self.port)
        abstract.FileDescriptor.connectionLost(self)
        self.connected = 0
        self.socket.close()
        del self.socket
        del self.fileno

    def logPrefix(self):
        """Returns the name of my class, to prefix log entries with.
        """
        return str(self.factory.__class__)
