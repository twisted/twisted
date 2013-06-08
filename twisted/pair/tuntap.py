# -*- test-case-name: twisted.pair.test.test_tuntap -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Support for Linux ethernet and IP tunnel devices.
"""

import os
import fcntl
import errno
import struct
import warnings
from collections import namedtuple

from zope.interface import implementer

from twisted.python.constants import Flags, FlagConstant
from twisted.python import log
from twisted.internet import base, error, task, interfaces, defer
from twisted.pair import ethernet, raw



IFNAMSIZ = 16
TUNSETIFF = 0x400454ca
TUNGETIFF = 0x800454d2
TUN_KO_PATH = b"/dev/net/tun"



class TunnelType(Flags):
    """
    L{TunnelType} defines flags which are used to configure the behavior of a
    tunnel device.
    """
    # XXX these are the kernel internal names I think
    TUN = FlagConstant(1)
    TAP = FlagConstant(2)

    TUN_FASYNC = FlagConstant(0x0010)
    TUN_NOCHECKSUM = FlagConstant(0x0020)
    TUN_NO_PI = FlagConstant(0x0040)
    TUN_ONE_QUEUE = FlagConstant(0x0080)
    TUN_PERSIST = FlagConstant(0x0100)
    TUN_VNET_HDR = FlagConstant(0x0200)



class TunnelFlags(Flags):
    # XXX Should have TUN and TAP constants here and use them
    IFF_NO_PI = FlagConstant(0x1000)
    IFF_ONE_QUEUE = FlagConstant(0x2000)
    IFF_VNET_HDR = FlagConstant(0x4000)
    IFF_TUN_EXCL = FlagConstant(0x8000)



@implementer(interfaces.IAddress)
class TunnelAddress(object):
    """
    A L{TunnelAddress} represents the tunnel to which a L{TuntapPort} is bound.
    """
    def __init__(self, type, name):
        """
        @param type: One of the L{TunnelType} constants representing the type
            of this tunnel.

        @param name: The system name of the tunnel.
        @type name: L{bytes}
        """
        self.type = type
        self.name = name


    def __getitem__(self, index):
        """
        Deprecated accessor for the tunnel name.  Use attributes instead.
        """
        warnings.warn(
            "TunnelAddress.__getitem__ is deprecated since Twisted 13.1  "
            "Use attributes instead.", category=DeprecationWarning,
            stacklevel=2)
        return ('TUNTAP', self.name)[index]



class _TunnelDescription(namedtuple("_TunnelDescription", "fileno name")):
    """
    Describe an existing tunnel.

    @ivar fileno: An L{int} giving the file descriptor associated with the
        tunnel.
    @ivar name: A L{bytes} instance giving the name of the tunnel.
    """



class TuntapPort(base.BasePort):
    """
    A Port that reads and writes packets from/to a TUN/TAP-device.

    TODO: Share general start/stop etc implementation details with
    twisted.internet.udp.Port.
    """

    _open = staticmethod(os.open)
    _read = staticmethod(os.read)
    _write = staticmethod(os.write)
    _close = staticmethod(os.close)
    _ioctl = staticmethod(fcntl.ioctl)

    _O_RDWR = os.O_RDWR
    _O_NONBLOCK = os.O_NONBLOCK
    # Introduced in Python 3.x
    # Ubuntu 12.04, /usr/include/x86_64-linux-gnu/bits/fcntl.h
    _O_CLOEXEC = getattr(os, "O_CLOEXEC", 0o2000000)

    maxThroughput = 256 * 1024  # Max bytes we read in one eventloop iteration

    def __init__(self, interface, proto, maxPacketSize=8192, reactor=None):
        if ethernet.IEthernetProtocol.providedBy(proto):
            self.ethernet = 1
            self._mode = TunnelType.TAP
        else:
            self.ethernet = 0
            self._mode = TunnelType.TUN
            assert raw.IRawPacketProtocol.providedBy(proto)

        base.BasePort.__init__(self, reactor)
        self.interface = interface
        self.protocol = proto
        self.maxPacketSize = maxPacketSize

        logPrefix = self._getLogPrefix(self.protocol)
        self.logstr = "%s (%s)" % (logPrefix, self._mode.name)


    def __repr__(self):
        args = (self.protocol.__class__,)
        if self.connected:
            args = args + ("",)
        else:
            args = args + ("not ",)
        args = args + (self._mode.name, self.interface)
        return "<%s %slistening on %s/%s>" % args


    def startListening(self):
        """
        Create and bind my socket, and begin listening on it.

        This is called on unserialization, and must be called after creating a
        server to begin listening on the specified port.
        """
        self._bindSocket()
        self._connectToProtocol()


    def _openTunnel(self, name, mode):
        """
        Open the named tunnel using the given mode.

        @param name: The name of the tunnel to open.
        @type name: L{bytes}

        @param mode: XXX It's a mixup

        @return: A L{_TunnelDescription} representing the newly opened tunnel.
        """
        flags = self._O_RDWR | self._O_CLOEXEC | self._O_NONBLOCK
        config = struct.pack("%dsH" % (IFNAMSIZ,), name, mode.value)
        fileno = self._open(TUN_KO_PATH, flags)
        result = self._ioctl(fileno, TUNSETIFF, config)
        return _TunnelDescription(fileno, result[:IFNAMSIZ].strip('\x00'))


    def _bindSocket(self):
        log.msg("%s starting on %s" % (self.protocol.__class__,
                                       self.interface))
        try:
            fileno, interface = self._openTunnel(
                self.interface, self._mode | TunnelFlags.IFF_NO_PI)
        except (IOError, OSError) as e:
            raise error.CannotListenError(None, self.interface, e)

        self.interface = interface
        self._fileno = fileno

        self.connected = 1


    def fileno(self):
        return self._fileno


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
                data = self._read(self._fileno, self.maxPacketSize)
            except EnvironmentError as e:
                if e.errno in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EINTR):
                    return
                else:
                    raise
            except:
                raise
            read += len(data)
            # TODO pkt.isPartial()?
            try:
                self.protocol.datagramReceived(data, partial=0)
            except:
                log.err(None, "monkeys")



    def write(self, datagram):
        """
        Write a datagram.
        """
        try:
            return self._write(self._fileno, datagram)
        except IOError as e:
            if e.errno == errno.EINTR:
                return self.write(datagram)
            raise


    def writeSequence(self, seq):
        self.write("".join(seq))


    def stopListening(self):
        """
        Stop accepting connections on this port.

        This will shut down my socket and call self.connectionLost().
        """
        self.stopReading()
        if self.disconnecting:
            return self._stoppedDeferred
        elif self.connected:
            self._stoppedDeferred = task.deferLater(
                self.reactor, 0, self.connectionLost)
            self.disconnecting = True
            return self._stoppedDeferred
        else:
            return defer.succeed(None)


    def loseConnection(self):
        warnings.warn(
            "TuntapPort.loseConnection is deprecated since Twisted 13.1  "
            "Use TuntapPort.stopListening instead.",
            category=DeprecationWarning, stacklevel=2)
        self.stopListening().addErrback(log.err)


    def connectionLost(self, reason=None):
        """
        Cleans up my socket.
        """
        log.msg('(Tuntap %s Closed)' % self.interface)
        base.BasePort.connectionLost(self, reason)
        self.protocol.doStop()
        self.connected = 0
        self._close(self._fileno)
        self._fileno = -1


    def logPrefix(self):
        """
        Returns the name of my class, to prefix log entries with.
        """
        return self.logstr


    def getHost(self):
        """
        Get the local address of this L{TuntapPort}.

        @return: A L{TunnelAddress} which describes the tunnel device to which
            this object is bound.
        @rtype: L{TunnelAddress}
        """
        return TunnelAddress(self._mode, self.interface)
