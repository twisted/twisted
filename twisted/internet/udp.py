
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

if os.name == 'nt':
    EWOULDBLOCK = 10035
elif os.name != 'java':
    from errno import EWOULDBLOCK

# Twisted Imports
from twisted.protocols import protocol
from twisted.persisted import styles
from twisted.python import log, defer

# Sibling Imports
import abstract, main


class Connection(abstract.FileDescriptor,
                 protocol.Transport,
                 styles.Ephemeral):
    """This is a UDP virtual connection

    This transport connects to a given host/port over UDP. By nature
    of UDP, only outgoing communications are allowed.  If a connection
    is initiated by a packet arriving at a UDP port, it is up to the
    port to call dataReceived with that packet.  By default, once data
    is written once to the connection, it is lost.
    """

    keepConnection = 0

    def __init__(self, skt, protocol, remote, local, sessionno, reactor=None):
        self.socket = skt
        self.fileno = skt.fileno
        self.remote = remote
        self.protocol = protocol
        self.local = local
        self.sessionno = sessionno
        self.connected = 1
        self.logstr = "%s,%s,%s (UDP)" % (self.protocol.__class__.__name__,
                                          sessionno, self.remote[0])
        if reactor is None:
            from twisted.internet import reactor
        self.reactor = reactor
        if abstract.isIPAddress(self.remote[0]):
            self.realAddress = self.remote[0]
        else:
            self.realAddress = None
            deferred = self.reactor.resolve(self.remote[0]
                                       ).addCallbacks(
                self.setRealAddress, self.connectionLost
                )

    def setRealAddress(self, address):
        self.realAddress = address
        self.startWriting()

    def write(self,data):
        res = abstract.FileDescriptor.write(self,data)
        if not self.keepConnection:
            self.loseConnection()
        if self.realAddress is None:
            self.stopWriting()
        return res

    def writeSomeData(self, data):
        """Connection.writeSomeData(data) -> #of bytes written | CONNECTION_LOST
        This writes as much data as possible to the socket and returns either
        the number of bytes read (which is positive) or a connection error code
        (which is negative)
        """
        if len(data) > 0:
            try:
                return self.socket.sendto(data, self.remote)
            except socket.error, se:
                if se.args[0] == EWOULDBLOCK:
                    return 0
                return main.CONNECTION_LOST
        else:
            return 0

    def connectionLost(self):
        """See abstract.FileDescriptor.connectionLost().
        """
        protocol = self.protocol
        del self.protocol
        abstract.FileDescriptor.connectionLost(self)
        self.socket.close()
        del self.socket
        del self.fileno
        protocol.connectionLost()

    def logPrefix(self):
        """Return the prefix to log with when I own the logging thread.
        """
        return self.logstr

    def getPeer(self):
        """
        Returns a tuple of ('INET_UDP', hostname, port), indicating
        the connected client's address
        """
        return ('INET_UDP',)+self.remote

    def getHost(self):
        """
        Returns a tuple of ('INET_UDP', hostname, port), indicating
        the servers address
        """
        return ('INET_UDP',)+self.socket.getsockname()


class Port(abstract.FileDescriptor):
    """I am a UDP server port, listening for packets."""

    sessionno = 0

    def __init__(self, port, factory, interface='', maxPacketSize=8192):
        """Initialize with a numeric port to listen on.
        """
        self.port = port
        self.factory = factory
        self.maxPacketSize = maxPacketSize
        self.interface = interface
        self.setLogStr()

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
        self.factory.doStart()
        skt = self.createInternetSocket()
        skt.bind( (self.interface ,self.port) )
        self.connected = 1
        self.socket = skt
        self.fileno = self.socket.fileno
        self.startReading()

    def createConnection(self, addr):
        """Creates a virtual connection over UDP"""
        protocol = self.factory.buildProtocol(addr)
        s = self.sessionno
        self.sessionno = s+1
        transport = Connection(self.socket.dup(), protocol, addr, self, s)
        protocol.makeConnection(transport)
        return transport

    def doRead(self):
        """Called when my socket is ready for reading."""
        try:
            data, addr = self.socket.recvfrom(self.maxPacketSize)
            transport = self.createConnection(addr)
            # Ugly patch needed because logically control passes here
            # from the port to the transport.
            self.logstr = transport.logPrefix()
            transport.protocol.dataReceived(data)
            self.setLogStr()
        except:
            log.deferr()

    def doWrite(self):
        """Raises an AssertionError.
        """
        assert 0, "doWrite called on a %s" % str(self.__class__)

    def loseConnection(self):
        """ Stop accepting connections on this port.

        This will shut down my socket and call self.connectionLost().
        """
        self.stopReading()
        if self.connected:
            from twisted.internet import reactor
            reactor.callLater(0, self.connectionLost)

    def connectionLost(self):
        """Cleans up my socket.
        """
        log.msg('(Port %s Closed)' % self.port)
        abstract.FileDescriptor.connectionLost(self)
        self.factory.doStop()
        self.connected = 0
        self.socket.close()
        del self.socket
        del self.fileno

    def setLogStr(self):
        self.logstr = str(self.factory.__class__) + " (UDP)"

    def logPrefix(self):
        """Returns the name of my class, to prefix log entries with.
        """
        return self.logstr

    def getHost(self):
        """
        Returns a tuple of ('INET_UDP', hostname, port), indicating
        the servers address
        """
        return ('INET_UDP',)+self.socket.getsockname()
