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

Please do not use this module directly.

API Stability: unstable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

# System Imports
import os
import socket
import operator
import struct

if os.name == 'nt':
    EWOULDBLOCK = 10035
elif os.name != 'java':
    from errno import EWOULDBLOCK, EINTR, EMSGSIZE, ECONNREFUSED

# Twisted Imports
from twisted.internet import protocol
from twisted.persisted import styles
from twisted.python import log, reflect

# Sibling Imports
import abstract, main, error, interfaces


class Port(abstract.FileDescriptor):
    """UDP port, listening for packets."""

    __implements__ = abstract.FileDescriptor.__implements__, interfaces.IUDPTransport
    
    def __init__(self, reactor, port, protocol, interface='', maxPacketSize=8192):
        """Initialize with a numeric port to listen on.
        """
        abstract.FileDescriptor.__init__(self, reactor)
        self.port = port
        self.protocol = protocol
        self.maxPacketSize = maxPacketSize
        self.interface = interface
        self.setLogStr()

    def __repr__(self):
        return "<%s on %s>" % (self.protocol.__class__, self.port)

    def createInternetSocket(self):
        """(internal) create an AF_INET/SOCK_DGRAM socket.
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setblocking(0)
        return s

    def __getstate__(self):
        """(internal) get my state for persistence
        """
        dct = self.__dict__.copy()
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
        self._bindSocket()
        self._connectToProtocol()
    
    def _bindSocket(self):
        log.msg("%s starting on %s"%(self.protocol.__class__, self.port))
        skt = self.createInternetSocket()
        try:
            skt.bind((self.interface, self.port))
        except socket.error, le:
            raise error.CannotListenError, (self.interface, self.port, le)
        self.connected = 1
        self.socket = skt
        self.fileno = self.socket.fileno
    
    def _connectToProtocol(self):
        self.protocol.makeConnection(self)
        self.startReading()

    def doRead(self):
        """Called when my socket is ready for reading."""
        try:
            data, addr = self.socket.recvfrom(self.maxPacketSize)
            self.protocol.datagramReceived(data, addr)
        except:
            log.deferr()

    def doWrite(self):
        """Raises an AssertionError.
        """
        raise RuntimeError, "doWrite called on a %s" % reflect.qual(self.__class__)

    def write(self, datagram, (host, port)):
        """Write a datagram."""
        try:
            return self.socket.sendto(datagram, (host, port))
        except socket.error, se:
            no = se.args[0]
            if no == EINTR:
                return self.write(datagram, (host, port))
            elif no == EMSGSIZE:
                raise error.MessageLengthError, "message too long"
            elif no == ECONNREFUSED:
                raise error.ConnectionRefusedError
            else:
                raise

    def writeSequence(self, seq, addr):
        self.write("".join(seq), addr)

    def loseConnection(self):
        """Stop accepting connections on this port.

        This will shut down my socket and call self.connectionLost().
        """
        self.stopReading()
        if self.connected:
            from twisted.internet import reactor
            reactor.callLater(0, self.connectionLost)

    stopListening = loseConnection
    
    def connectionLost(self, reason=None):
        """Cleans up my socket.
        """
        log.msg('(Port %s Closed)' % self.port)
        abstract.FileDescriptor.connectionLost(self, reason)
        if hasattr(self, "protocol"):
            # we won't have attribute in ConnectedPort, in cases
            # where there was an error in connection process
            self.protocol.doStop()
        self.connected = 0
        self.socket.close()
        del self.socket
        del self.fileno

    def setLogStr(self):
        self.logstr = reflect.qual(self.protocol.__class__) + " (UDP)"

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


class ConnectedPort(Port):
    """A connected UDP socket."""

    __implements__ = abstract.FileDescriptor.__implements__, interfaces.IUDPConnectedTransport
        
    def __init__(self, reactor, (remotehost, remoteport), port, protocol, interface='', maxPacketSize=8192):
        Port.__init__(self, reactor, port, protocol, interface, maxPacketSize)
        self.remotehost = remotehost
        self.remoteport = remoteport
    
    def startListening(self):
        self._bindSocket()
        if abstract.isIPAddress(self.remotehost):
            self.setRealAddress(self.remotehost)
        else:
            self.realAddress = None
            d = self.reactor.resolve(self.remotehost)
            d.addCallback(self.setRealAddress).addErrback(self.connectionFailed)

    def setRealAddress(self, addr):
        self.realAddress = addr
        self.socket.connect((addr, self.remoteport))
        self._connectToProtocol()
    
    def connectionFailed(self, reason):
        self.loseConnection()
        self.protocol.connectionFailed(reason)
        del self.protocol
    
    def doRead(self):
        """Called when my socket is ready for reading."""
        try:
            data, addr = self.socket.recvfrom(self.maxPacketSize)
            self.protocol.datagramReceived(data)
        except:
            log.deferr()

    def write(self, data):
        """Write a datagram."""
        try:
            return self.socket.send(data)
        except socket.error, se:
            no = se.args[0]
            if no == EINTR:
                return self.write(data)
            elif no == EMSGSIZE:
                raise error.MessageLengthError, "message too long"
            elif no == ECONNREFUSED:
                raise error.ConnectionRefusedError
            else:
                raise

    def getPeer(self):
        """
        Returns a tuple of ('INET_UDP', hostname, port), indicating
        the remote address.
        """
        return ('INET_UDP', self.remotehost, self.remoteport)


class MulticastMixin:
    """Implement multicast functionality.

    Initial implementation, probably needs some changes for Windows support.
    """

    def getOutgoingInterface(self):
        i = self.socket.getsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF)
        # is this cross-platform?
        return socket.inet_ntoa(struct.pack("<l", i))
    
    def setOutgoingInterface(self, addr):
        """Returns Deferred of success."""
        return self.reactor.resolve(addr).addCallback(self._setInterface)

    def _setInterface(self, addr):
        i = socket.inet_aton(addr)
        self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, i)
        return 1
    
    def getLoopbackMode(self):
        return self.socket.getsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP)
    
    def setLoopbackMode(self, mode):
        mode = struct.pack("b", operator.truth(mode))
        self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, mode)

    def getTTL(self):
        return self.socket.getsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL)
    
    def setTTL(self, ttl):
        ttl = struct.pack("b", ttl)
        self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)

    def joinGroup(self, addr, interface=""):
        """Join a multicast group. Returns Deferred of success."""
        return self.reactor.resolve(addr).addCallback(self._joinAddr1, interface, 1)

    def _joinAddr1(self, addr, interface, join):
        return self.reactor.resolve(interface).addCallback(self._joinAddr2, addr, join)

    def _joinAddr2(self, interface, addr, join):
        addr = socket.inet_aton(addr)
        interface = socket.inet_aton(interface)
        if join:
            cmd = socket.IP_ADD_MEMBERSHIP
        else:
            cmd = socket.IP_DROP_MEMBERSHIP
        self.socket.setsockopt(socket.IPPROTO_IP, cmd, addr + interface)
        return 1
    
    def leaveGroup(self, addr, interface=""):
        """Leave multicast group, return Deferred of success."""
        return self.reactor.resolve(addr).addCallback(self._joinAddr1, interface, 0)


class MulticastPort(MulticastMixin, Port):
    """UDP Port that supports multicasting."""

    __implements__ = Port.__implements__, interfaces.IMulticastTransport


class ConnectedMulticastPort(MulticastMixin, ConnectedPort):
    """Connected UDP Port that supports multicasting."""

    __implements__ = ConnectedPort.__implements__, interfaces.IMulticastTransport
