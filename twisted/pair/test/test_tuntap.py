# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.pair.tuntap}.
"""

from __future__ import division, absolute_import

import os
import struct
import socket
from errno import (
    EPERM, EAGAIN, EWOULDBLOCK, ENOSYS, EBADF, EINVAL, EINTR, ENOBUFS, ENOENT)
from random import randrange
from functools import wraps
from collections import deque
from itertools import cycle
from signal import SIGINT

try:
    from fcntl import ioctl as _ioctl
except ImportError:
    platformSkip = "Platform is missing fcntl/ioctl support"
    _ioctl = None
else:
    platformSkip = None

from zope.interface import implementer
from zope.interface.verify import verifyObject

from twisted.internet.protocol import DatagramProtocol
from twisted.pair.rawudp import RawUDPProtocol
from twisted.pair.ip import IPProtocol
from twisted.pair.ethernet import EthernetProtocol

from twisted.python.reflect import fullyQualifiedName
from twisted.python.compat import iterbytes
from twisted.internet.interfaces import IAddress, IReactorFDSet
from twisted.internet.protocol import AbstractDatagramProtocol, Factory
from twisted.internet.task import Clock
from twisted.trial.unittest import SkipTest, SynchronousTestCase
from twisted.internet.error import CannotListenError
from twisted.pair.raw import IRawPacketProtocol

if platformSkip is None:
    from twisted.pair.tuntap import (
        TUNSETIFF, IFNAMSIZ, TunnelType, TunnelFlags, TunnelAddress,
        TuntapPort, _RealSystem)



@implementer(IReactorFDSet)
class ReactorFDSet(object):
    """
    An implementation of L{IReactorFDSet} which only keeps track of which
    descriptors have been registered for reading and writing.

    This implementation isn't actually capable of determining readability or
    writeability and generates no events for the descriptors registered with
    it.
    """
    def __init__(self):
        self._readers = set()
        self._writers = set()
        self.addReader = self._readers.add
        self.addWriter = self._writers.add


    def removeReader(self, reader):
        try:
            self._readers.remove(reader)
        except KeyError:
            pass


    def removeWriter(self, writer):
        try:
            self._writers.remove(writer)
        except KeyError:
            pass


    def getReaders(self):
        return iter(self._readers)


    def getWriters(self):
        return iter(self._writers)


    def removeAll(self):
        try:
            return list(self._readers | self._writers)
        finally:
            self._readers = set()
            self._writers = set()
verifyObject(IReactorFDSet, ReactorFDSet())



class FSSetClock(Clock, ReactorFDSet):
    """
    An L{FSSetClock} is a L{IReactorFDSet} and an L{IReactorClock}.
    """
    def __init__(self):
        Clock.__init__(self)
        ReactorFDSet.__init__(self)



class Tunnel(object):
    """
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

        if request != TUNSETIFF:
            raise IOError(EINVAL, "Request or args is not valid.")

        name, mode = struct.unpack('%dsH' % (IFNAMSIZ,), args)
        tunnel.tunnelMode = mode
        tunnel.requestedName = name
        tunnel.name = name[:IFNAMSIZ - 3] + "123"
        return struct.pack('%dsH' % (IFNAMSIZ,), tunnel.name, mode)


    def sendUDP(self, datagram, address):
        # Just make up some random thing
        srcIP = '10.1.2.3'
        srcPort = 21345

        self._openFiles.values()[0].readBuffer.append(
            _ethernet(
                src='\x00' * 6, dst='\xff' * 6, protocol=IPv4,
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




def H(n):
    return struct.pack('>H', n)


IPv4 = 0x0800


def _ethernet(src, dst, protocol, payload):
    return dst + src + H(protocol) + payload


def _ip(src, dst, payload):
    ipHeader = (
        '\x45'  # version and header length, 4 bits each
        '\x00'  # differentiated services field
        + H(20 + len(payload))  # total length
        + '\x00\x01\x00\x00\x40\x11'
        + H(0)  # checksum
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
        H(src)                  # source port
        + H(dst)                # destination port
        + H(len(payload) + 8)   # length
        + H(0))                 # checksum
    return udpHeader + payload



class TapMixin(object):

    _TUNNEL_TYPE = staticmethod(TunnelType.TAP)

    def encapsulate(self, payload):
        return _ethernet(
            src='\x00\x00\x00\x00\x00\x00', dst='\xff\xff\xff\xff\xff\xff',
            protocol=IPv4,
            payload=_ip(
                src=self._TUNNEL_REMOTE, dst=self._TUNNEL_LOCAL,
                payload=_udp(
                    src=50000, dst=12345, payload=payload)))


    def parser(self):
        datagrams = []
        receiver = DatagramProtocol()

        def capture(*args):
            datagrams.append(args)

        receiver.datagramReceived = capture

        udp = RawUDPProtocol()
        udp.addProto(12345, receiver)

        ip = IPProtocol()
        ip.addProto(17, udp)

        ether = EthernetProtocol()
        ether.addProto(0x800, ip)

        return datagrams, ether.datagramReceived



class TunMixin(object):

    _TUNNEL_TYPE = staticmethod(TunnelType.TUN)


    def encapsulate(self, payload):
        return _ip(
            src=self._TUNNEL_REMOTE, dst=self._TUNNEL_LOCAL,
            payload=_udp(
                src=50000, dst=12345, payload=payload))


    def parser(self):
        datagrams = []
        receiver = DatagramProtocol()

        def capture(*args):
            datagrams.append(args)

        receiver.datagramReceived = capture

        udp = RawUDPProtocol()
        udp.addProto(12345, receiver)

        ip = IPProtocol()
        ip.addProto(17, udp)

        def parse(data):
            # Skip the ethernet frame
            return ip.datagramReceived(data[14:], False, None, None, None)

        return datagrams, parse



class TunnelDeviceTestsMixin(object):
    def setUp(self):
        self.system = self.system()
        self.fileno = self.system.open(b"/dev/net/tun",
                                       os.O_RDWR | os.O_NONBLOCK)
        self.addCleanup(self.system.close, self.fileno)
        config = struct.pack(
            "%dsH" % (IFNAMSIZ,), self._TUNNEL_DEVICE, self._TUNNEL_TYPE.value)
        self.system.ioctl(self.fileno, TUNSETIFF, config)


    def _invalidFileDescriptor(self):
        """
        Return an integer which is not a valid file descriptor at the time of
        this call.  After any future system call which allocates a new file
        descriptor, there is no guarantee the returned file descriptor will
        still be invalid.
        """
        fd = self.system.open(b"/dev/net/tun", os.O_RDWR)
        self.system.close(fd)
        return fd


    def test_readEBADF(self):
        """
        The device's C{read} implementation raises L{OSError} with an errno of
        C{EBADF} when called on a file descriptor which is not valid (ie, which
        has no associated file description).
        """
        fd = self._invalidFileDescriptor()
        exc = self.assertRaises(OSError, self.system.read, fd, 1024)
        self.assertEqual(EBADF, exc.errno)


    def test_writeEBADF(self):
        """
        The device's C{write} implementation raises L{OSError} with an errno of
        C{EBADF} when called on a file descriptor which is not valid (ie, which
        has no associated file description).
        """
        fd = self._invalidFileDescriptor()
        exc = self.assertRaises(OSError, self.system.write, fd, b"bytes")
        self.assertEqual(EBADF, exc.errno)


    def test_closeEBADF(self):
        """
        The device's C{close} implementation raises L{OSError} with an errno of
        C{EBADF} when called on a file descriptor which is not valid (ie, which
        has no associated file description).
        """
        fd = self._invalidFileDescriptor()
        exc = self.assertRaises(OSError, self.system.close, fd)
        self.assertEqual(EBADF, exc.errno)


    def test_ioctlEBADF(self):
        """
        The device's C{ioctl} implementation raises L{OSError} with an errno of
        C{EBADF} when called on a file descriptor which is not valid (ie, which
        has no associated file description).
        """
        fd = self._invalidFileDescriptor()
        exc = self.assertRaises(
            IOError, self.system.ioctl, fd, TUNSETIFF, b"tap0")
        self.assertEqual(EBADF, exc.errno)


    def test_ioctlEINVAL(self):
        """
        The device's C{ioctl} implementation raises L{IOError} with an errno of
        C{EINVAL} when called with a request (second argument) which is not a
        supported operation.
        """
        # Try to invent an unsupported request.  Hopefully this isn't a real
        # request on any system.
        request = 0xDEADBEEF
        exc = self.assertRaises(
            IOError, self.system.ioctl, self.fileno, request, b"garbage")
        self.assertEqual(EINVAL, exc.errno)


    def test_receive(self):
        datagrams, parse = self.parser()

        found = False
        for i in range(100):
            key = randrange(2 ** 64)
            message = "hello world:%d" % (key,)
            source = self.system.sendUDP(message, (self._TUNNEL_REMOTE, 12345))

            for j in range(100):
                try:
                    packet = self.system.read(self.fileno, 1024)
                except EnvironmentError as e:
                    if e.errno in (EAGAIN, EWOULDBLOCK):
                        break
                    raise
                else:
                    # XXX Slice off the four bytes of flag/proto prefix that
                    # always seem to be there.  Why can't I get this to work
                    # any other way?
                    parse(packet[4:])
                    if (message, source) in datagrams:
                        found = True
                        break
                    del datagrams[:]
            if found:
                break

        if not found:
            self.fail("Never saw probe UDP packet on tunnel")


    def test_send(self):
        protocol = IPv4
        key = 1234567  # randrange(2 ** 64)
        message = "hello world:%d" % (key,)

        port = self.system.receiveUDP(self.fileno, self._TUNNEL_LOCAL, 12345)

        packet = self.encapsulate(message)

        flags = 0
        self.system.write(self.fileno, H(flags) + H(protocol) + packet)

        packet = port.recv(1024)
        self.assertEqual(message, packet)



class FakeDeviceTestsMixin(object):
    _TUNNEL_DEVICE = "tap-twistedtest"
    _TUNNEL_LOCAL = "10.2.0.1"
    _TUNNEL_REMOTE = "10.2.0.2"

    def system(self):
        system = MemoryIOSystem()
        system._devices[Tunnel._DEVICE_NAME] = Tunnel
        return system



class FakeTapDeviceTests(TapMixin, FakeDeviceTestsMixin,
                         TunnelDeviceTestsMixin, SynchronousTestCase):
    pass



class FakeTunDeviceTests(TunMixin, FakeDeviceTestsMixin,
                         TunnelDeviceTestsMixin, SynchronousTestCase):
    pass



class TestRealSystem(_RealSystem):
    def open(self, filename, *args, **kwargs):
        """
        Attempt an open, but if the file is /dev/net/tun and it does not exist,
        translate the error into L{SkipTest} so that tests that require
        platform support for tuntap devices are skipped instead of failed.
        """
        try:
            return super(TestRealSystem, self).open(filename, *args, **kwargs)
        except OSError as e:
            if ENOENT == e.errno and filename == b"/dev/net/tun":
                raise SkipTest("Platform lacks /dev/net/tun")
            raise


    def ioctl(self, *args, **kwargs):
        """
        Attempt an ioctl, but translate permission denied errors into
        L{SkipTest} so that tests that require elevated system privileges and
        do not have them are skipped instead of failed.
        """
        try:
            return super(TestRealSystem, self).ioctl(*args, **kwargs)
        except IOError as e:
            if EPERM == e.errno:
                raise SkipTest("Permission to configure device denied")


    def sendUDP(self, datagram, address):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(('10.0.0.1', 0))
        s.sendto(datagram, address)
        return s.getsockname()


    def receiveUDP(self, fileno, host, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # s.setblocking(False)
        s.bind((host, port))
        return s



class RealDeviceTestsMixin(object):
    if platformSkip:
        skip = platformSkip

    def system(self):
        # Create a tap-style tunnel device.  Ethernet frames come out of this
        # and ethernet frames must be put into it.  Grant access to it to an
        # otherwise unprivileged user.
        #
        # ip tuntap add dev tap-twistedtest mode tap user exarkun group exarkun
        #
        # Bring the device up, since otherwise it's not usable for anything.
        #
        # ip link set up dev tap-twistedtest
        #
        # Give the device an address.  Just like an ethernet device may be
        # given an address, perhaps a statically allocated one.  This will also
        # implicitly create a route for traffic destined for addresses on the
        # same network as the address assigned here to travel via this device.
        #
        # ip addr add 10.0.0.1/24 dev tap-twistedtest
        #
        # Statically populate the arp cache with some addresses that might
        # exist on that network and thus be accessible via this device.
        #
        # ip neigh add 10.0.0.2 lladdr de:ad:be:ef:ca:fe dev tap-twistedtest
        #
        # Once all that's done, RealSpecial will satisfy the requirements of
        # the tests inherited by this class.
        #
        # You can undo it all just by getting rid of the tunnel device.
        #
        # ip tuntap del dev tap-twistedtest mode tap
        #
        return TestRealSystem()



class RealDeviceWithProtocolInformationTests(TapMixin, RealDeviceTestsMixin,
                                             TunnelDeviceTestsMixin,
                                             SynchronousTestCase):

    _TUNNEL_TYPE = staticmethod(TunnelType.TAP)
    _TUNNEL_DEVICE = "tap-twtest-pi"
    _TUNNEL_LOCAL = "10.1.0.1"
    _TUNNEL_REMOTE = "10.1.0.2"



class RealDeviceWithoutProtocolInformationTests(TapMixin, RealDeviceTestsMixin,
                                                TunnelDeviceTestsMixin,
                                                SynchronousTestCase):

    _TUNNEL_TYPE = staticmethod(TunnelType.TAP)
    _TUNNEL_DEVICE = "tap-twtest"
    _TUNNEL_LOCAL = "10.0.0.1"
    _TUNNEL_REMOTE = "10.0.0.2"



class TunnelTestsMixin(object):

    def setUp(self):
        self.name = b"tun0"
        self.system = MemoryIOSystem()
        self.system._devices[Tunnel._DEVICE_NAME] = Tunnel
        self.protocol = self.factory.buildProtocol(
            TunnelAddress(self.TUNNEL_TYPE, self.name))
        self.reactor = FSSetClock()
        self.port = TuntapPort(self.name, self.protocol, reactor=self.reactor, system=self.system)


    def test_startListeningOpensDevice(self):
        """
        L{TuntapPort.startListening} opens the tunnel factory character special
        device C{"/dev/net/tun"} and configures it as a I{tun} tunnel.
        """
        system = self.system
        self.port.startListening()
        tunnel = self.system.getTunnel(self.port)
        self.assertEqual(
            system.O_RDWR | system.O_CLOEXEC | system.O_NONBLOCK,
            tunnel.openFlags)
        self.assertEqual(
            b"tun0" + "\x00" * (IFNAMSIZ - len(b"tun0")), tunnel.requestedName)
        self.assertEqual(tunnel.name, self.port.interface)
        self.assertFalse(tunnel.blocking)
        self.assertTrue(tunnel.closeOnExec)
        self.assertTrue(self.port.connected)


    def test_startListeningConnectsProtocol(self):
        """
        L{TuntapPort.startListening} calls C{makeConnection} on the protocol
        the port was initialized with, passing the port as an argument.
        """
        self.port.startListening()
        self.assertIdentical(self.port, self.protocol.transport)


    def test_startListeningStartsReading(self):
        """
        L{TuntapPort.startListening} passes the port instance to the reactor's
        C{addReader} method to begin watching the port's file descriptor for
        data to read.
        """
        self.port.startListening()
        self.assertIn(self.port, self.reactor.getReaders())


    def test_startListeningHandlesOpenFailure(self):
        """
        L{TuntapPort.startListening} raises L{CannotListenError} if opening the
        tunnel factory character special device fails.
        """
        self.system.permissions.remove('open')
        self.assertRaises(CannotListenError, self.port.startListening)


    def test_startListeningHandlesConfigureFailure(self):
        """
        L{TuntapPort.startListening} raises L{CannotListenError} if the
        C{ioctl} call to configure the tunnel device fails.
        """
        self.system.permissions.remove('ioctl')
        self.assertRaises(CannotListenError, self.port.startListening)


    def _stopPort(self, port):
        stopped = port.stopListening()
        self.assertNotIn(port, self.reactor.getReaders())
        # An unfortunate implementation detail
        self.reactor.advance(0)
        self.assertIdentical(None, self.successResultOf(stopped))


    def test_stopListeningStopsReading(self):
        """
        L{TuntapPort.stopListening} returns a L{Deferred} which fires after the
        port has been removed from the reactor's reader list by passing it to
        the reactor's C{removeReader} method.
        """
        self.port.startListening()
        fileno = self.port.fileno()
        self._stopPort(self.port)

        self.assertFalse(self.port.connected)
        self.assertNotIn(fileno, self.system._openFiles)


    def test_stopListeningStopsProtocol(self):
        """
        L{TuntapPort.stopListening} calls C{doStop} on the protocol the port
        was initialized with.
        """
        self.port.startListening()
        self._stopPort(self.port)
        self.assertIdentical(None, self.protocol.transport)


    def test_stopListeningWhenStopped(self):
        """
        L{TuntapPort.stopListening} returns a L{Deferred} which succeeds
        immediately if it is called when the port is not listening.
        """
        stopped = self.port.stopListening()
        self.assertIdentical(None, self.successResultOf(stopped))


    def test_multipleStopListening(self):
        self.port.startListening()
        first = self.port.stopListening()
        second = self.port.stopListening()
        self.reactor.advance(0)
        self.assertIdentical(None, self.successResultOf(first))
        self.assertIdentical(None, self.successResultOf(second))


    def test_loseConnection(self):
        """
        L{TuntapPort.loseConnection} stops the port and is deprecated.
        """
        self.port.startListening()

        self.port.loseConnection()
        # An unfortunate implementation detail
        self.reactor.advance(0)

        self.assertFalse(self.port.connected)
        warnings = self.flushWarnings([self.test_loseConnection])
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(
            "twisted.pair.tuntap.TuntapPort.loseConnection was deprecated "
            "in Twisted 13.1.0; please use twisted.pair.tuntap.TuntapPort."
            "stopListening instead",
            warnings[0]['message'])
        self.assertEqual(1, len(warnings))


    def _stopsReadingTest(self, style):
        """
        Test that L{TuntapPort.doRead} has no side-effects under a certain
        exception condition.

        @param style: An exception instance to arrange for the (python wrapper
            around the) underlying platform I{read} call to fail with.

        @raise C{self.failureException}: If there are any observable
            side-effects.
        """
        self.port.startListening()
        tunnel = self.system.getTunnel(self.port)
        tunnel.nonBlockingExceptionStyle = style
        self.port.doRead()
        self.assertEqual([], self.protocol.received)


    def test_eagainStopsReading(self):
        """
        Once L{TuntapPort.doRead} encounters an I{EAGAIN} errno from a C{read}
        call, it returns.
        """
        self._stopsReadingTest(Tunnel.EAGAIN_STYLE)


    def test_ewouldblockStopsReading(self):
        """
        Once L{TuntapPort.doRead} encounters an I{EWOULDBLOCK} errno from a
        C{read} call, it returns.
        """
        self._stopsReadingTest(Tunnel.EWOULDBLOCK_STYLE)


    def test_eintrblockStopsReading(self):
        """
        Once L{TuntapPort.doRead} encounters an I{EINTR} errno from a C{read}
        call, it returns.
        """
        self._stopsReadingTest(Tunnel.EINTR_STYLE)


    def test_unhandledReadError(self):
        """
        If L{Tuntap.doRead} encounters any exception other than one explicitly
        handled by the code, the exception propagates to the caller.
        """
        class UnexpectedException(Exception):
            pass

        self.assertRaises(
            UnexpectedException,
            self._stopsReadingTest, UnexpectedException())


    def test_unhandledEnvironmentReadError(self):
        """
        Just like C{test_unhandledReadError}, but for the case where the
        exception that is not explicitly handled happens to be of type
        C{EnvironmentError} (C{OSError} or C{IOError}).
        """
        self.assertRaises(
            IOError,
            self._stopsReadingTest, IOError(EPERM, "Operation not permitted"))


    def test_doReadSmallDatagram(self):
        """
        L{TuntapPort.doRead} reads a datagram of fewer than
        C{TuntapPort.maxPacketSize} from the port's file descriptor and passes
        it to its protocol's C{datagramReceived} method.
        """
        datagram = b'x' * (self.port.maxPacketSize - 1)
        self.port.startListening()
        tunnel = self.system.getTunnel(self.port)
        tunnel.readBuffer.append(datagram)
        self.port.doRead()
        self.assertEqual([datagram], self.protocol.received)


    def test_doReadLargeDatagram(self):
        """
        L{TuntapPort.doRead} reads the first part of a datagram of more than
        C{TuntapPort.maxPacketSize} from the port's file descriptor and passes
        the truncated data to its protocol's C{datagramReceived} method.
        """
        datagram = b'x' * self.port.maxPacketSize
        self.port.startListening()
        tunnel = self.system.getTunnel(self.port)
        tunnel.readBuffer.append(datagram + b'y')
        self.port.doRead()
        self.assertEqual([datagram], self.protocol.received)


    def test_doReadSeveralDatagrams(self):
        """
        L{TuntapPort.doRead} reads several datagrams, of up to
        C{TuntapPort.maxThroughput} bytes total, before returning.
        """
        values = cycle(iterbytes(b'abcdefghijklmnopqrstuvwxyz'))
        total = 0
        datagrams = []
        while total < self.port.maxThroughput:
            datagrams.append(next(values) * self.port.maxPacketSize)
            total += self.port.maxPacketSize

        self.port.startListening()
        tunnel = self.system.getTunnel(self.port)
        tunnel.readBuffer.extend(datagrams)
        tunnel.readBuffer.append(b'excessive datagram, not to be read')

        self.port.doRead()
        self.assertEqual(datagrams, self.protocol.received)


    def test_datagramReceivedException(self):
        """
        If the protocol's C{datagramReceived} method raises an exception, the
        exception is logged.
        """
        self.port.startListening()
        self.system.getTunnel(self.port).readBuffer.append(b"ping")

        # Break the application logic
        self.protocol.received = None

        self.port.doRead()
        errors = self.flushLoggedErrors(AttributeError)
        self.assertEqual(1, len(errors))


    def test_write(self):
        """
        L{TuntapPort.write} sends a datagram into the tunnel.
        """
        datagram = b"a b c d e f g"
        self.port.startListening()
        self.port.write(datagram)
        self.assertEqual(
            self.system.getTunnel(self.port).writeBuffer,
            deque([datagram]))


    def test_interruptedWrite(self):
        """
        If the platform write call is interrupted (causing the Python wrapper
        to raise C{IOError} with errno set to C{EINTR}), the write is re-tried.
        """
        self.port.startListening()
        tunnel = self.system.getTunnel(self.port)
        tunnel.pendingSignals.append(SIGINT)
        self.port.write(b"hello, world")
        self.assertEqual(deque([b"hello, world"]), tunnel.writeBuffer)


    def test_unhandledWriteError(self):
        """
        Any exception raised by the underlying write call, except for EINTR, is
        propagated to the caller.
        """
        self.port.startListening()
        tunnel = self.system.getTunnel(self.port)
        self.assertRaises(
            IOError,
            self.port.write, b"x" * tunnel.SEND_BUFFER_SIZE + b"y")


    def test_writeSequence(self):
        """
        L{TuntapPort.writeSequence} sends a datagram into the tunnel by
        concatenating the byte strings in the list passed to it.
        """
        datagram = [b"a", b"b", b"c", b"d"]
        self.port.startListening()
        self.port.writeSequence(datagram)
        self.assertEqual(
            self.system.getTunnel(self.port).writeBuffer,
            deque([b"".join(datagram)]))


    def test_getHost(self):
        """
        L{TuntapPort.getHost} returns a L{TunnelAddress} including the tunnel's
        type and name.
        """
        self.port.startListening()
        address = self.port.getHost()
        self.assertIsInstance(address, TunnelAddress)
        self.assertEqual(self.TUNNEL_TYPE, address.type)
        self.assertEqual(
            self.system.getTunnel(self.port).name, address.name)


    def test_listeningString(self):
        """
        The string representation of a L{TuntapPort} instance includes the
        tunnel type and interface and the protocol associated with the port.
        """
        self.port.startListening()
        expected = "<%s listening on %s/%s>" % (
            fullyQualifiedName(self.protocol.__class__),
            self.TUNNEL_TYPE.name,
            self.system.getTunnel(self.port).name)

        self.assertEqual(expected, str(self.port))


    def test_unlisteningString(self):
        """
        The string representation of a L{TuntapPort} instance includes the
        tunnel type and interface and the protocol associated with the port.
        """
        expected = "<%s not listening on %s/%s>" % (
            fullyQualifiedName(self.protocol.__class__),
            self.TUNNEL_TYPE.name, self.name)

        self.assertEqual(expected, str(self.port))


    def test_logPrefix(self):
        """
        L{TuntapPort.logPrefix} returns a string identifying the application
        protocol and the type of tunnel.
        """
        self.assertEqual(
            "%s (%s)" % (
                self.protocol.__class__.__name__,
                self.TUNNEL_TYPE.name),
            self.port.logPrefix())



class TunnelAddressTests(SynchronousTestCase):
    """
    Tests for L{TunnelAddress}.
    """

    def test_interfaces(self):
        """
        A L{TunnelAddress} instances provides L{IAddress}.
        """
        self.assertTrue(
            verifyObject(IAddress, TunnelAddress(TunnelType.TAP, "tap0")))


    def test_indexing(self):
        """
        A L{TunnelAddress} instance can be indexed to retrieve either the byte
        string C{"TUNTAP"} or the name of the tunnel interface, while
        triggering a deprecation warning.
        """
        address = TunnelAddress(TunnelType.TAP, "tap0")
        self.assertEqual("TUNTAP", address[0])
        self.assertEqual("tap0", address[1])
        warnings = self.flushWarnings([self.test_indexing])
        message = (
            "TunnelAddress.__getitem__ is deprecated since Twisted 13.1  "
            "Use attributes instead.")
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(message, warnings[0]['message'])
        self.assertEqual(DeprecationWarning, warnings[1]['category'])
        self.assertEqual(message, warnings[1]['message'])
        self.assertEqual(2, len(warnings))



@implementer(IRawPacketProtocol)
class IPRecordingProtocol(AbstractDatagramProtocol):

    def startProtocol(self):
        self.received = []


    def datagramReceived(self, datagram, partial=False):
        self.received.append(datagram)



class TunTests(TunnelTestsMixin, SynchronousTestCase):
    """
    Tests for L{TuntapPort} when used to open a Linux I{tun} tunnel.
    """
    TUNNEL_TYPE = staticmethod(TunnelType.TUN)

    factory = Factory()
    factory.protocol = IPRecordingProtocol



class EthernetRecordingProtocol(EthernetProtocol):

    def startProtocol(self):
        self.received = []


    def datagramReceived(self, datagram, partial=False):
        self.received.append(datagram)



class TapTests(TunnelTestsMixin, SynchronousTestCase):

    TUNNEL_TYPE = staticmethod(TunnelType.TAP)

    factory = Factory()
    factory.protocol = EthernetRecordingProtocol
