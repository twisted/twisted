# -*- test-case-name: twisted.test.test_udp -*-

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

API Stability: semi-stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

# System Imports
import os
import socket
import operator
import struct
import warnings

from twisted.python.runtime import platformType
if platformType == 'win32':
    from errno import WSAEWOULDBLOCK as EWOULDBLOCK
    from errno import WSAEINTR as EINTR
    from errno import WSAEMSGSIZE as EMSGSIZE
    from errno import WSAECONNREFUSED as ECONNREFUSED
    from errno import WSAECONNRESET
    from errno import EAGAIN
elif platformType != 'java':
    from errno import EWOULDBLOCK, EINTR, EMSGSIZE, ECONNREFUSED, EAGAIN

# Twisted Imports
from twisted.internet import protocol, base, defer, address
from twisted.persisted import styles
from twisted.python import log, reflect

# Sibling Imports
import abstract, main, error, interfaces


class Port(base.BasePort):
    """UDP port, listening for packets."""

    __implements__ = base.BasePort.__implements__, interfaces.IUDPTransport, interfaces.ISystemHandle

    addressFamily = socket.AF_INET
    socketType = socket.SOCK_DGRAM
    maxThroughput = 256 * 1024 # max bytes we read in one eventloop iteration

    def __init__(self, port, proto, interface='', maxPacketSize=8192, reactor=None):
        """Initialize with a numeric port to listen on.
        """
        assert isinstance(proto, protocol.DatagramProtocol)
        base.BasePort.__init__(self, reactor)
        self.port = port
        self.protocol = proto
        self.maxPacketSize = maxPacketSize
        self.interface = interface
        self.setLogStr()
        self._connected = False
        self._connectedAddr = None
    
    def __repr__(self):
        return "<%s on %s>" % (self.protocol.__class__, self.port)

    def getHandle(self):
        """Return a socket object."""
        return self.socket
    
    def startListening(self):
        """Create and bind my socket, and begin listening on it.

        This is called on unserialization, and must be called after creating a
        server to begin listening on the specified port.
        """
        self._bindSocket()
        self._connectToProtocol()

    def _bindSocket(self):
        log.msg("%s starting on %s"%(self.protocol.__class__, self.port))
        try:
            skt = self.createInternetSocket()
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
        read = 0
        while read < self.maxThroughput:
            try:
                data, addr = self.socket.recvfrom(self.maxPacketSize)
                read += len(data)
                self.protocol.datagramReceived(data, addr)
            except socket.error, se:
                no = se.args[0]
                if no in (EAGAIN, EINTR, EWOULDBLOCK):
                    return
                if (no == ECONNREFUSED) or (platformType == "win32" and no == WSAECONNRESET):
                    # XXX for the moment we don't deal with connection refused
                    # in non-connected UDP sockets.
                    pass
                else:
                    raise
            except:
                log.deferr()

    def write(self, datagram, addr=None):
        """Write a datagram.

        @param addr: should be a tuple (ip, port), can be None in connected mode.
        """
        if self._connected:
            assert addr in (None, self._connectedAddr)
            try:
                return self.socket.send(datagram)
            except socket.error, se:
                no = se.args[0]
                if no == EINTR:
                    return self.write(datagram)
                elif no == EMSGSIZE:
                    raise error.MessageLengthError, "message too long"
                elif no == ECONNREFUSED:
                    self.protocol.connectionRefused()
                else:
                    raise
        else:
            assert addr != None
            if not addr[0].replace(".", "").isdigit():
                warnings.warn("Please only pass IPs to write(), not hostnames", DeprecationWarning, stacklevel=2)
            try:
                return self.socket.sendto(datagram, addr)
            except socket.error, se:
                no = se.args[0]
                if no == EINTR:
                    return self.write(datagram, addr)
                elif no == EMSGSIZE:
                    raise error.MessageLengthError, "message too long"
                else:
                    raise

    def writeSequence(self, seq, addr):
        self.write("".join(seq), addr)

    def connect(self, host, port):
        """'Connect' to remote server."""
        if self._connected:
            raise RuntimeError, "already connected, reconnecting is not currently supported"
        if not abstract.isIPAddress(host):
            raise ValueError, "please pass only IP addresses, not domain names"
        self._connected = True
        self._connectedAddr = (host, port)
        self.socket.connect((host, port))
    
    def loseConnection(self):
        """Stop accepting connections on this port.

        This will shut down my socket and call self.connectionLost().
        """
        self.stopReading()
        if self.connected:
            from twisted.internet import reactor
            reactor.callLater(0, self.connectionLost)

    def stopListening(self):
        if self.connected:
            result = self.d = defer.Deferred()
        else:
            result = None
        self.loseConnection()
        return result

    def connectionLost(self, reason=None):
        """Cleans up my socket.
        """
        log.msg('(Port %s Closed)' % self.port)
        base.BasePort.connectionLost(self, reason)
        if hasattr(self, "protocol"):
            # we won't have attribute in ConnectedPort, in cases
            # where there was an error in connection process
            self.protocol.doStop()
        self.connected = 0
        self.socket.close()
        del self.socket
        del self.fileno
        if hasattr(self, "d"):
            self.d.callback(None)
            del self.d

    def setLogStr(self):
        self.logstr = reflect.qual(self.protocol.__class__) + " (UDP)"

    def logPrefix(self):
        """Returns the name of my class, to prefix log entries with.
        """
        return self.logstr

    def getHost(self):
        """
        Returns an IPv4Address.

        This indicates the address from which I am connecting.
        """
        return address.IPv4Address('UDP', *(self.socket.getsockname() + ('INET_UDP',)))


class ConnectedPort(Port):
    """DEPRECATED.

    A connected UDP socket."""

    __implements__ = Port.__implements__, interfaces.IUDPConnectedTransport

    def __init__(self, (remotehost, remoteport), port, proto, interface='', maxPacketSize=8192, reactor=None):
        assert isinstance(proto, protocol.ConnectedDatagramProtocol)
        Port.__init__(self, port, proto, interface, maxPacketSize, reactor)
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
        read = 0
        while read < self.maxThroughput:
            try:
                data, addr = self.socket.recvfrom(self.maxPacketSize)
                read += len(data)
                self.protocol.datagramReceived(data)
            except socket.error, se:
                no = se.args[0]
                if no in (EAGAIN, EINTR, EWOULDBLOCK):
                    return
                if (no == ECONNREFUSED) or (platformType == "win32" and no == WSAECONNRESET):
                    self.protocol.connectionRefused()
                else:
                    raise
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
                self.protocol.connectionRefused()
            else:
                raise

    def getPeer(self):
        """
        Returns a tuple of ('INET_UDP', hostname, port), indicating
        the remote address.
        """
        return address.IPv4Address('UDP', self.remotehost, self.remoteport, 'INET_UDP')


class MulticastMixin:
    """Implement multicast functionality."""

    def getOutgoingInterface(self):
        i = self.socket.getsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF)
        return socket.inet_ntoa(struct.pack("@i", i))

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
    """DEPRECATED.

    Connected UDP Port that supports multicasting."""

    __implements__ = ConnectedPort.__implements__, interfaces.IMulticastTransport
