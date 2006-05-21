# -*- test-case-name: twisted.test.test_udp -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


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
from zope.interface import implements

from twisted.python.runtime import platformType
if platformType == 'win32':
    from errno import WSAEWOULDBLOCK as EWOULDBLOCK
    from errno import WSAEINTR as EINTR
    from errno import WSAEMSGSIZE as EMSGSIZE
    from errno import WSAECONNREFUSED as ECONNREFUSED
    from errno import WSAECONNRESET
    EAGAIN=EWOULDBLOCK
else:
    from errno import EWOULDBLOCK, EINTR, EMSGSIZE, ECONNREFUSED, EAGAIN

# Twisted Imports
from twisted.internet import protocol, base, defer, address
from twisted.persisted import styles
from twisted.python import log, reflect, components, failure

# Sibling Imports
import abstract, error, interfaces


class Port(base.BasePort):
    """UDP port, listening for packets."""

    implements(interfaces.IUDPTransport, interfaces.ISystemHandle)

    addressFamily = socket.AF_INET
    socketType = socket.SOCK_DGRAM
    maxThroughput = 256 * 1024 # max bytes we read in one eventloop iteration

    # Actual port number being listened on, only set to a non-None
    # value when we are actually listening.
    _realPortNumber = None

    def __init__(self, port, proto, interface='', maxPacketSize=8192, reactor=None):
        """Initialize with a numeric port to listen on.
        """
        base.BasePort.__init__(self, reactor)
        self.port = port
        self.protocol = proto
        self.maxPacketSize = maxPacketSize
        self.interface = interface
        self.setLogStr()
        self._connectedAddr = None

    def __repr__(self):
        if self._realPortNumber is not None:
            return "<%s on %s>" % (self.protocol.__class__, self._realPortNumber)
        else:
            return "<%s not connected>" % (self.protocol.__class__,)

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
        try:
            skt = self.createInternetSocket()
            skt.bind((self.interface, self.port))
        except socket.error, le:
            raise error.CannotListenError, (self.interface, self.port, le)

        # Make sure that if we listened on port 0, we update that to
        # reflect what the OS actually assigned us.
        self._realPortNumber = skt.getsockname()[1]

        log.msg("%s starting on %s"%(self.protocol.__class__, self._realPortNumber))

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
            except socket.error, se:
                no = se.args[0]
                if no in (EAGAIN, EINTR, EWOULDBLOCK):
                    return
                if (no == ECONNREFUSED) or (platformType == "win32" and no == WSAECONNRESET):
                    if self._connectedAddr:
                        self.protocol.connectionRefused()
                else:
                    raise
            else:
                read += len(data)
                try:
                    self.protocol.datagramReceived(data, addr)
                except:
                    log.err()


    def write(self, datagram, addr=None):
        """Write a datagram.

        @param addr: should be a tuple (ip, port), can be None in connected mode.
        """
        if self._connectedAddr:
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
                elif no == ECONNREFUSED:
                    # in non-connected UDP ECONNREFUSED is platform dependent, I think
                    # and the info is not necessarily useful. Nevertheless maybe we
                    # should call connectionRefused? XXX
                    return
                else:
                    raise

    def writeSequence(self, seq, addr):
        self.write("".join(seq), addr)

    def connect(self, host, port):
        """'Connect' to remote server."""
        if self._connectedAddr:
            raise RuntimeError, "already connected, reconnecting is not currently supported (talk to itamar if you want this)"
        if not abstract.isIPAddress(host):
            raise ValueError, "please pass only IP addresses, not domain names"
        self._connectedAddr = (host, port)
        self.socket.connect((host, port))

    def _loseConnection(self):
        self.stopReading()
        if self.connected: # actually means if we are *listening*
            from twisted.internet import reactor
            reactor.callLater(0, self.connectionLost)

    def stopListening(self):
        if self.connected:
            result = self.d = defer.Deferred()
        else:
            result = None
        self._loseConnection()
        return result

    def loseConnection(self):
        warnings.warn("Please use stopListening() to disconnect port", DeprecationWarning, stacklevel=2)
        self.stopListening()

    def connectionLost(self, reason=None):
        """Cleans up my socket.
        """
        log.msg('(Port %s Closed)' % self._realPortNumber)
        self._realPortNumber = None
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

    implements(interfaces.IUDPConnectedTransport)

    def __init__(self, (remotehost, remoteport), port, proto, interface='', maxPacketSize=8192, reactor=None):
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
        self._loseConnection()
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
        ttl = struct.pack("B", ttl)
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
        try:
            self.socket.setsockopt(socket.IPPROTO_IP, cmd, addr + interface)
        except socket.error, e:
            return failure.Failure(error.MulticastJoinError(addr, interface, *e.args))

    def leaveGroup(self, addr, interface=""):
        """Leave multicast group, return Deferred of success."""
        return self.reactor.resolve(addr).addCallback(self._joinAddr1, interface, 0)


class MulticastPort(MulticastMixin, Port):
    """UDP Port that supports multicasting."""

    implements(interfaces.IMulticastTransport)

    def __init__(self, port, proto, interface='', maxPacketSize=8192, reactor=None, listenMultiple=False):
        Port.__init__(self, port, proto, interface, maxPacketSize, reactor)
        self.listenMultiple = listenMultiple

    def createInternetSocket(self):
        skt = Port.createInternetSocket(self)
        if self.listenMultiple:
            skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        return skt


class ConnectedMulticastPort(MulticastMixin, ConnectedPort):
    """DEPRECATED.

    Connected UDP Port that supports multicasting."""

    implements(interfaces.IMulticastTransport)
