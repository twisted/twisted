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

from twisted.python.versions import Version
from twisted.python.deprecate import deprecated
from twisted.python.constants import Flags, FlagConstant
from twisted.python import log
from twisted.internet import abstract, error, task, interfaces, defer
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



class _RealSystem(object):
    """
    An interface to the parts of the operating system which L{TuntapPort}
    relies on.
    """
    open = staticmethod(os.open)
    read = staticmethod(os.read)
    write = staticmethod(os.write)
    close = staticmethod(os.close)
    ioctl = staticmethod(fcntl.ioctl)

    O_RDWR = os.O_RDWR
    O_NONBLOCK = os.O_NONBLOCK
    # Introduced in Python 3.x
    # Ubuntu 12.04, /usr/include/x86_64-linux-gnu/bits/fcntl.h
    O_CLOEXEC = getattr(os, "O_CLOEXEC", 0o2000000)



class TuntapPort(abstract.FileDescriptor):
    """
    A Port that reads and writes packets from/to a TUN/TAP-device.
    """
    maxThroughput = 256 * 1024  # Max bytes we read in one eventloop iteration

    def __init__(self, interface, proto, maxPacketSize=8192, reactor=None, system=None):
        if ethernet.IEthernetProtocol.providedBy(proto):
            self.ethernet = 1
            self._mode = TunnelType.TAP
        else:
            self.ethernet = 0
            self._mode = TunnelType.TUN
            assert raw.IRawPacketProtocol.providedBy(proto)

        if system is None:
            system = _RealSystem()
        self._system = system

        abstract.FileDescriptor.__init__(self, reactor)
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

        This must be called after creating a server to begin listening on the
        specified tunnel.
        """
        self._bindSocket()
        self.protocol.makeConnection(self)
        self.startReading()


    def _openTunnel(self, name, mode):
        """
        Open the named tunnel using the given mode.

        @param name: The name of the tunnel to open.
        @type name: L{bytes}

        @param mode: XXX It's a mixup

        @return: A L{_TunnelDescription} representing the newly opened tunnel.
        """
        flags = (
            self._system.O_RDWR | self._system.O_CLOEXEC |
            self._system.O_NONBLOCK)
        config = struct.pack("%dsH" % (IFNAMSIZ,), name, mode.value)
        fileno = self._system.open(TUN_KO_PATH, flags)
        result = self._system.ioctl(fileno, TUNSETIFF, config)
        return _TunnelDescription(fileno, result[:IFNAMSIZ].strip('\x00'))


    def _bindSocket(self):
        """
        Open the tunnel.
        """
        log.msg(
            format="%(protocol)s starting on %(interface)s",
            protocol=self.protocol.__class__,
            interface=self.interface)
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


    def doRead(self):
        """
        Called when my socket is ready for reading.
        """
        read = 0
        while read < self.maxThroughput:
            try:
                data = self._system.read(self._fileno, self.maxPacketSize)
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
            return self._system.write(self._fileno, datagram)
        except IOError as e:
            if e.errno == errno.EINTR:
                return self.write(datagram)
            raise


    def writeSequence(self, seq):
        """
        Write a datagram constructed for a list of L{bytes}.
        """
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
        """
        Close this tunnel.  This is Use L{TuntapPort.stopListening} instead.
        """
        self.stopListening().addErrback(log.err)


    def connectionLost(self, reason=None):
        """
        Cleans up my socket.
        """
        log.msg('(Tuntap %s Closed)' % self.interface)
        abstract.FileDescriptor.connectionLost(self, reason)
        self.protocol.doStop()
        self.connected = 0
        self._system.close(self._fileno)
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

TuntapPort.loseConnection = deprecated(
    Version("Twisted", 13, 1, 0),
    TuntapPort.stopListening)(TuntapPort.loseConnection)

