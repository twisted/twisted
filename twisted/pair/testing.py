# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tools for automated testing of L{twisted.pair}-based applications.
"""

import struct
import socket
from errno import (
    EPERM, EAGAIN, EWOULDBLOCK, ENOSYS, EBADF, EINVAL, EINTR, ENOBUFS)
from collections import deque
from functools import wraps

from twisted.internet.protocol import DatagramProtocol
from twisted.pair.ethernet import EthernetProtocol
from twisted.pair.rawudp import RawUDPProtocol
from twisted.pair.ip import IPProtocol
from twisted.pair.tuntap import (
    _IFNAMSIZ, _TUNSETIFF, TunnelType, TunnelFlags)


def _H(n):
    return struct.pack('>H', n)


_IPv4 = 0x0800


def _ethernet(src, dst, protocol, payload):
    return dst + src + _H(protocol) + payload


def _ip(src, dst, payload):
    ipHeader = (
        '\x45'  # version and header length, 4 bits each
        '\x00'  # differentiated services field
        + _H(20 + len(payload))  # total length
        + '\x00\x01\x00\x00\x40\x11'
        + _H(0)  # checksum
        + socket.inet_pton(socket.AF_INET, src)  # source address
        + socket.inet_pton(socket.AF_INET, dst))  # destination address

    # Total all of the 16-bit integers in the header
    checksumStep1 = sum(struct.unpack('!10H', ipHeader))
    # Pull off the carry
    carry = checksumStep1 >> 16
    # And add it to what was left over
    checksumStep2 = (checksumStep1 & 0xFFFF) + carry
    # Compute the one's complement sum
    checksumStep3 = checksumStep2 ^ 0xFFFF

    # Reconstruct the IP header including the correct checksum so the
    # platform IP stack, if there is one involved in this test, doesn't drop
    # it on the floor as garbage.
    ipHeader = (
        ipHeader[:10] +
        struct.pack('!H', checksumStep3) +
        ipHeader[12:])

    return ipHeader + payload



def _udp(src, dst, payload):
    udpHeader = (
        _H(src)                  # source port
        + _H(dst)                # destination port
        + _H(len(payload) + 8)   # length
        + _H(0))                 # checksum
    return udpHeader + payload



class Tunnel(object):
    """
    An in-memory implementation of a tun or tap device.

    @cvar _DEVICE_NAME: A string representing the conventional filesystem entry
        for the tunnel factory character special device.
    @type _DEVICE_NAME: C{bytes}
    """
    _DEVICE_NAME = b"/dev/net/tun"

    # Between POSIX and Python, there are 4 combinations.  Here are two, at
    # least.
    EAGAIN_STYLE = IOError(EAGAIN, "Resource temporarily unavailable")
    EWOULDBLOCK_STYLE = OSError(EWOULDBLOCK, "Operation would block")

    # Oh yea, and then there's the case where maybe we would've read, but
    # someone sent us a signal instead.
    EINTR_STYLE = IOError(EINTR, "Interrupted function call")

    nonBlockingExceptionStyle = EAGAIN_STYLE

    SEND_BUFFER_SIZE = 1024

    def __init__(self, system, openFlags, fileMode):
        self.system = system

        # Drop fileMode on the floor - evidence and logic suggest it is
        # irrelevant with respect to /dev/net/tun
        self.openFlags = openFlags
        self.tunnelMode = None
        self.requestedName = None
        self.name = None
        self.readBuffer = deque()
        self.writeBuffer = deque()
        self.pendingSignals = deque()


    @property
    def blocking(self):
        return not (self.openFlags & self.system.O_NONBLOCK)


    @property
    def closeOnExec(self):
        return self.openFlags & self.system.O_CLOEXEC


    def read(self, limit):
        if self.readBuffer:
            header = ""
            if not self.tunnelMode & TunnelFlags.IFF_NO_PI.value:
                header = "\x00\x00\x00\x00"
                limit -= 4
            return header + self.readBuffer.popleft()[:limit]
        elif self.blocking:
            raise OSError(ENOSYS, "Function not implemented")
        else:
            raise self.nonBlockingExceptionStyle


    def write(self, datagram):
        if self.pendingSignals:
            self.pendingSignals.popleft()
            raise IOError(EINTR, "Interrupted system call")

        if len(datagram) > self.SEND_BUFFER_SIZE:
            raise IOError(ENOBUFS, "No buffer space available")

        self.writeBuffer.append(datagram)
        return len(datagram)



def privileged(original):
    """
    Wrap a L{MemoryIOSystem} method with permission-checking logic.  The
    returned function will check C{self.permissions} and raise L{IOError} with
    L{errno.EPERM} if the function name is not listed as an available
    permission.
    """
    @wraps(original)
    def permissionChecker(self, *args, **kwargs):
        if original.func_name not in self.permissions:
            raise IOError(EPERM, "Operation not permitted")
        return original(self, *args, **kwargs)
    return permissionChecker



class MemoryIOSystem(object):
    """
    An in-memory implementation of basic I/O primitives, useful in the context
    of unit testing as a drop-in replacement for parts of the C{os} module.

    @ivar _devices:
    @ivar _openFiles:
    @ivar permissions:

    @ivar _counter:
    """
    _counter = 8192

    O_RDWR = 1 << 0
    O_NONBLOCK = 1 << 1
    O_CLOEXEC = 1 << 2

    def __init__(self):
        self._devices = {}
        self._openFiles = {}
        self.permissions = set(['open', 'ioctl'])


    def getTunnel(self, port):
        """
        Get the L{Tunnel} object associated with the given L{TuntapPort}.

        @param port: A L{TuntapPort} previously initialized using this
            L{MemoryIOSystem}.
        """
        return self._openFiles[port.fileno()]


    @privileged
    def open(self, name, flags, mode=None):
        """
        A replacement for C{os.open}.  This initializes state in this
        L{MemoryIOSystem} which will be reflected in the behavior of the other
        file descriptor-related methods (eg L{MemoryIOSystem.read},
        L{MemoryIOSystem.write}, etc).

        @param name: A string giving the name of the file to open.
        @type name: C{bytes}

        @param flags: The flags with which to open the file.
        @type flags: C{int}

        @param mode: The mode with which to open the file.
        @type mode: C{int}
        """
        if name in self._devices:
            fd = self._counter
            self._counter += 1
            self._openFiles[fd] = self._devices[name](self, flags, mode)
            return fd
        raise OSError(ENOSYS, "Function not implemented")


    def read(self, fd, limit):
        try:
            return self._openFiles[fd].read(limit)
        except KeyError:
            raise OSError(EBADF, "Bad file descriptor")


    def write(self, fd, data):
        try:
            return self._openFiles[fd].write(data)
        except KeyError:
            raise OSError(EBADF, "Bad file descriptor")


    def close(self, fd):
        try:
            del self._openFiles[fd]
        except KeyError:
            raise OSError(EBADF, "Bad file descriptor")


    @privileged
    def ioctl(self, fd, request, args):
        try:
            tunnel = self._openFiles[fd]
        except KeyError:
            raise IOError(EBADF, "Bad file descriptor")

        if request != _TUNSETIFF:
            raise IOError(EINVAL, "Request or args is not valid.")

        name, mode = struct.unpack('%dsH' % (_IFNAMSIZ,), args)
        tunnel.tunnelMode = mode
        tunnel.requestedName = name
        tunnel.name = name[:_IFNAMSIZ - 3] + "123"
        return struct.pack('%dsH' % (_IFNAMSIZ,), tunnel.name, mode)


    def sendUDP(self, datagram, address):
        # Just make up some random thing
        srcIP = '10.1.2.3'
        srcPort = 21345

        self._openFiles.values()[0].readBuffer.append(
            _ethernet(
                src='\x00' * 6, dst='\xff' * 6, protocol=_IPv4,
                payload=_ip(
                    src=srcIP, dst=address[0], payload=_udp(
                        src=srcPort, dst=address[1], payload=datagram))))

        return (srcIP, srcPort)


    def receiveUDP(self, fileno, host, port):
        return _FakePort(self, fileno)



class _FakePort(object):
    def __init__(self, system, fileno):
        self._system = system
        self._fileno = fileno


    def recv(self, nbytes):
        data = self._system._openFiles[self._fileno].writeBuffer.popleft()

        datagrams = []
        receiver = DatagramProtocol()

        def capture(datagram, address):
            datagrams.append(datagram)

        receiver.datagramReceived = capture

        udp = RawUDPProtocol()
        udp.addProto(12345, receiver)

        ip = IPProtocol()
        ip.addProto(17, udp)

        if (self._system._openFiles[self._fileno].tunnelMode ==
                TunnelType.TAP.value):
            ether = EthernetProtocol()
            ether.addProto(0x800, ip)
            datagramReceived = ether.datagramReceived
        else:
            datagramReceived = lambda data: ip.datagramReceived(
                data, None, None, None, None)

        datagramReceived(data[4:])
        return datagrams[0][:nbytes]
