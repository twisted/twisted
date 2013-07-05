# -*- test-case-name: twisted.test.test_udp -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Various asynchronous UDP classes.

Please do not use this module directly.

@var _sockErrReadIgnore: list of symbolic error constants (from the C{errno}
    module) representing socket errors where the error is temporary and can be
    ignored.

@var _sockErrReadRefuse: list of symbolic error constants (from the C{errno}
    module) representing socket errors that indicate connection refused.
"""

from __future__ import division, absolute_import

# System Imports
import socket
import operator
import struct
import warnings

from zope.interface import implementer

from twisted.python.runtime import platformType
if platformType == 'win32':
    from errno import WSAEWOULDBLOCK
    from errno import WSAEINTR, WSAEMSGSIZE, WSAETIMEDOUT
    from errno import WSAECONNREFUSED, WSAECONNRESET, WSAENETRESET
    from errno import WSAEINPROGRESS

    # Classify read and write errors
    _sockErrReadIgnore = [WSAEINTR, WSAEWOULDBLOCK, WSAEMSGSIZE, WSAEINPROGRESS]
    _sockErrReadRefuse = [WSAECONNREFUSED, WSAECONNRESET, WSAENETRESET,
                          WSAETIMEDOUT]

    # POSIX-compatible write errors
    EMSGSIZE = WSAEMSGSIZE
    ECONNREFUSED = WSAECONNREFUSED
    EAGAIN = WSAEWOULDBLOCK
    EINTR = WSAEINTR
else:
    from errno import EWOULDBLOCK, EINTR, EMSGSIZE, ECONNREFUSED, EAGAIN
    _sockErrReadIgnore = [EAGAIN, EINTR, EWOULDBLOCK]
    _sockErrReadRefuse = [ECONNREFUSED]

# Twisted Imports
from twisted.internet import base, defer, address
from twisted.python import log, failure
from twisted.internet import abstract, error, interfaces


@implementer(
    interfaces.IListeningPort, interfaces.IUDPTransport,
    interfaces.ISystemHandle)
class Port(base.BasePort):
    """
    UDP port, listening for packets.
    """

    addressFamily = socket.AF_INET
    socketType = socket.SOCK_DGRAM
    maxThroughput = 256 * 1024 # max bytes we read in one eventloop iteration

    # Actual port number being listened on, only set to a non-None
    # value when we are actually listening.
    _realPortNumber = None

    def __init__(self, port, proto, interface='', maxPacketSize=8192, reactor=None):
        """
        Initialize with a numeric port to listen on.
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
        """
        Return a socket object.
        """
        return self.socket

    def startListening(self):
        """
        Create and bind my socket, and begin listening on it.

        This is called on unserialization, and must be called after creating a
        server to begin listening on the specified port.
        """
        self._bindSocket()
        self._connectToProtocol()

    def _bindSocket(self):
        try:
            skt = self.createInternetSocket()
            skt.bind((self.interface, self.port))
        except socket.error as le:
            raise error.CannotListenError(self.interface, self.port, le)

        # Make sure that if we listened on port 0, we update that to
        # reflect what the OS actually assigned us.
        self._realPortNumber = skt.getsockname()[1]

        log.msg("%s starting on %s" % (
                self._getLogPrefix(self.protocol), self._realPortNumber))

        self.connected = 1
        self.socket = skt
        self.fileno = self.socket.fileno

    def _connectToProtocol(self):
        self.protocol.makeConnection(self)
        self.startReading()


    def doRead(self):
        """
        Called when my socket is ready for reading.
        """
        read = 0
        while read < self.maxThroughput:
            try:
                data, addr = self.socket.recvfrom(self.maxPacketSize)
            except socket.error as se:
                no = se.args[0]
                if no in _sockErrReadIgnore:
                    return
                if no in _sockErrReadRefuse:
                    if self._connectedAddr:
                        self.protocol.connectionRefused()
                    return
                raise
            else:
                read += len(data)
                try:
                    self.protocol.datagramReceived(data, addr)
                except:
                    log.err()


    def write(self, datagram, addr=None):
        """
        Write a datagram.

        @type datagram: C{str}
        @param datagram: The datagram to be sent.

        @type addr: C{tuple} containing C{str} as first element and C{int} as
            second element, or C{None}
        @param addr: A tuple of (I{stringified dotted-quad IP address},
            I{integer port number}); can be C{None} in connected mode.
        """
        if self._connectedAddr:
            assert addr in (None, self._connectedAddr)
            try:
                return self.socket.send(datagram)
            except socket.error as se:
                no = se.args[0]
                if no == EINTR:
                    return self.write(datagram)
                elif no == EMSGSIZE:
                    raise error.MessageLengthError("message too long")
                elif no == ECONNREFUSED:
                    self.protocol.connectionRefused()
                else:
                    raise
        else:
            assert addr != None
            if not addr[0].replace(".", "").isdigit() and addr[0] != "<broadcast>":
                warnings.warn("Please only pass IPs to write(), not hostnames",
                              DeprecationWarning, stacklevel=2)
            try:
                return self.socket.sendto(datagram, addr)
            except socket.error as se:
                no = se.args[0]
                if no == EINTR:
                    return self.write(datagram, addr)
                elif no == EMSGSIZE:
                    raise error.MessageLengthError("message too long")
                elif no == ECONNREFUSED:
                    # in non-connected UDP ECONNREFUSED is platform dependent, I
                    # think and the info is not necessarily useful. Nevertheless
                    # maybe we should call connectionRefused? XXX
                    return
                else:
                    raise

    def writeSequence(self, seq, addr):
        self.write("".join(seq), addr)

    def connect(self, host, port):
        """
        'Connect' to remote server.
        """
        if self._connectedAddr:
            raise RuntimeError("already connected, reconnecting is not currently supported")
        if not abstract.isIPAddress(host):
            raise ValueError("please pass only IP addresses, not domain names")
        self._connectedAddr = (host, port)
        self.socket.connect((host, port))

    def _loseConnection(self):
        self.stopReading()
        if self.connected: # actually means if we are *listening*
            self.reactor.callLater(0, self.connectionLost)

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
        """
        Cleans up my socket.
        """
        log.msg('(UDP Port %s Closed)' % self._realPortNumber)
        self._realPortNumber = None
        base.BasePort.connectionLost(self, reason)
        self.protocol.doStop()
        self.socket.close()
        del self.socket
        del self.fileno
        if hasattr(self, "d"):
            self.d.callback(None)
            del self.d


    def setLogStr(self):
        """
        Initialize the C{logstr} attribute to be used by C{logPrefix}.
        """
        logPrefix = self._getLogPrefix(self.protocol)
        self.logstr = "%s (UDP)" % logPrefix


    def logPrefix(self):
        """
        Return the prefix to log with.
        """
        return self.logstr


    def getHost(self):
        """
        Returns an IPv4Address.

        This indicates the address from which I am connecting.
        """
        return address.IPv4Address('UDP', *self.socket.getsockname())



class MulticastMixin:
    """
    Implement multicast functionality.
    """

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
        except socket.error as e:
            return failure.Failure(error.MulticastJoinError(addr, interface, *e.args))

    def leaveGroup(self, addr, interface=""):
        """Leave multicast group, return Deferred of success."""
        return self.reactor.resolve(addr).addCallback(self._joinAddr1, interface, 0)


@implementer(interfaces.IMulticastTransport)
class MulticastPort(MulticastMixin, Port):
    """
    UDP Port that supports multicasting.
    """

    def __init__(self, port, proto, interface='', maxPacketSize=8192, reactor=None, listenMultiple=False):
        """
        @see: L{twisted.internet.interfaces.IReactorMulticast.listenMulticast}
        """
        Port.__init__(self, port, proto, interface, maxPacketSize, reactor)
        self.listenMultiple = listenMultiple

    def createInternetSocket(self):
        skt = Port.createInternetSocket(self)
        if self.listenMultiple:
            skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        return skt
