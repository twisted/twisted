# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.pair.tuntap}.
"""

from __future__ import division, absolute_import

import os, struct, socket, fcntl
from errno import EPERM, EAGAIN, EWOULDBLOCK, ENOSYS, EBADF, EINVAL, EINTR, ENOBUFS
from signal import SIGCHLD
from random import randrange
from functools import wraps
from collections import deque
from itertools import cycle

from zope.interface import implementer, providedBy
from zope.interface.verify import verifyObject

from twisted.python.reflect import fullyQualifiedName
from twisted.python.compat import iterbytes
from twisted.internet.fdesc import setNonBlocking
from twisted.internet.interfaces import IAddress, IReactorFDSet
from twisted.internet.protocol import AbstractDatagramProtocol, Factory
from twisted.internet.task import Clock
from twisted.trial.unittest import SynchronousTestCase
from twisted.internet.error import CannotListenError
from twisted.pair.raw import IRawPacketProtocol
from twisted.pair.ethernet import EthernetProtocol
from twisted.pair.tuntap import (
    TUNSETIFF, IFNAMSIZ, TunnelType, TunnelAddress, TuntapPort)


@implementer(IReactorFDSet)
class ReactorFDSet(object):
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



class CompositeReactor(object):
    def __init__(self, parts):
        seen = set()
        for p in parts:
            for i in providedBy(p):
                if i in seen:
                    raise ValueError("Redundant part")
                seen.add(i)
                for m in i.names():
                    setattr(self, m, getattr(p, m))



class Tunnel(object):
    # Between POSIX and Python, there are 4 combinations.  Here are two, at least.
    EAGAIN_STYLE = IOError(EAGAIN, "Resource temporarily unavailable")
    EWOULDBLOCK_STYLE = OSError(EWOULDBLOCK, "Operation would block")

    # Oh yea, and then there's the case where maybe we would've read, but
    # someone sent us a signal instead.
    EINTR_STYLE = IOError(EINTR, "Interrupted function call")

    nonBlockingExceptionStyle = EAGAIN_STYLE

    SEND_BUFFER_SIZE = 1024

    def __init__(self, fileMode):
        self.fileMode = fileMode
        self.closeOnExec = False
        self.blocking = True
        self.tunnelMode = None
        self.requestedName = None
        self.name = None
        self.readBuffer = deque()
        self.writeBuffer = deque()
        self.pendingSignals = deque()


    def read(self, limit):
        if self.readBuffer:
            return self.readBuffer.popleft()[:limit]
        elif self.blocking:
            raise OSError(ENOSYS)
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



def privileged(f):
    @wraps(f)
    def g(self, *args, **kwargs):
        if f.func_name not in self.permissions:
            raise IOError(EPERM, "Operation not permitted")
        return f(self, *args, **kwargs)
    return g


class FakeSpecial(object):
    _counter = 8192

    OPERATIONS = [
        'open', 'read', 'write', 'ioctl', 'close', 'setNonBlocking',
        'setCloseOnExec']

    def __init__(self):
        self._tunnels = {}
        self.permissions = set(['open', 'ioctl'])


    def getTunnel(self, port):
        return self._tunnels[port.fileno()]


    @privileged
    def open(self, name, mode):
        if name == b"/dev/net/tun" and mode == os.O_RDWR:
            fd = self._counter
            self._counter += 1
            self._tunnels[fd] = Tunnel(mode)
            return fd
        raise OSError(ENOSYS)


    def read(self, fd, limit):
        try:
            return self._tunnels[fd].read(limit)
        except KeyError:
            raise IOError(EBADF, "Bad file descriptor")


    def write(self, fd, data):
        try:
            return self._tunnels[fd].write(data)
        except KeyError:
            raise IOError(EBADF, "Bad file descriptor")


    def close(self, fd):
        try:
            del self._tunnels[fd]
        except KeyError:
            raise IOError(EBADF, "Bad file descriptor")


    @privileged
    def ioctl(self, fd, request, args):
        try:
            tunnel = self._tunnels[fd]
        except KeyError:
            raise IOError(EBADF, "Bad file descriptor")

        if request != TUNSETIFF:
            raise IOError(EINVAL, "Request or args is not valid.")

        name, mode = struct.unpack('%dsH' % (IFNAMSIZ,), args)
        tunnel.tunnelMode = mode
        tunnel.requestedName = name
        tunnel.name = name[:IFNAMSIZ - 3] + "123"
        return struct.pack('%dsH' % (IFNAMSIZ,), tunnel.name, mode)


    def setNonBlocking(self, fd):
        try:
            tunnel = self._tunnels[fd]
        except KeyError:
            raise IOError(EBADF, "Bad file descriptor")
        tunnel.blocking = False


    def setCloseOnExec(self, fd):
        try:
            tunnel = self._tunnels[fd]
        except KeyError:
            raise IOError(EBADF, "Bad file descriptor")
        tunnel.closeOnExec = True


    def sendUDP(self, datagram, address):
        self._tunnels.values()[0].readBuffer.append(datagram)


    def receiveUDP(self, host, port):
        return _FakePort(self)



class _FakePort(object):
    def __init__(self, device):
        self._device = device


    def recv(self, nbytes):
        return self._device._tunnels.values()[0].writeBuffer.popleft()[:nbytes]



class TunnelDeviceTestsMixin(object):
    def setUp(self):
        self.device = self.device()
        self.fileno = self.device.open(b"/dev/net/tun", os.O_RDWR)
        self.addCleanup(self.device.close, self.fileno)
        self.device.setNonBlocking(self.fileno)
        config = struct.pack(
            "%dsH" % (IFNAMSIZ,), "tap-twistedtest", TunnelType.TAP.value)
        self.device.ioctl(self.fileno, TUNSETIFF, config)


    def test_receive(self):
        key = randrange(2 ** 64)
        message = "hello world:%d" % (key,)

        found = False
        for i in range(100):
            self.device.sendUDP(message, ("10.0.0.2", 12345))
            for j in range(100):
                try:
                    packet = self.device.read(self.fileno, 1024)
                except EnvironmentError as e:
                    if e.errno in (EAGAIN, EWOULDBLOCK):
                        break
                    raise
                else:
                    if message in packet:
                        found = True
                        break
            if found:
                break

        if not found:
            self.fail("Never saw probe UDP packet on tunnel")


    def test_send(self):
        key = randrange(2 ** 64)
        message = "hello world:%d" % (key,)

        port = self.device.receiveUDP('10.0.0.1', 12345)
        def H(n):
            return struct.pack('>H', n)

        ethernetHeader = (
            '\xff\xff\xff\xff\xff\xff' # destination address - broadcast
            '\x00\x00\x00\x00\x00\x00' # source address - null :/
            '\x08\x00'                 # type - IPv4
            )

        ipHeader = (
            '\x45'                     # version and header length, 4 bits each
            '\x00'                     # differentiated services field
            + H(20 + len(message) + 8) # total length
            + '\x00\x01\x00\x00@\x11'
            + H(0)                     # checksum
                                       # source address
            + socket.inet_pton(socket.AF_INET, '10.0.0.2')
                                       # destination address
            + socket.inet_pton(socket.AF_INET, '10.0.0.1'))

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

        udpHeader = (
            H(50000)                 # source port
            + H(12345)               # destination port
            + H(len(message) + 8)    # length
            + H(0))                  # checksum

        packet = (
            # Some extra bytes, not clear what they're for.
            '\x00\x00\x00\x00'
            + ethernetHeader
            + ipHeader
            + udpHeader
            + message)

        self.device.write(self.fileno, packet)

        packet = port.recv(1024)
        # FakeDevice doesn't understand ethernet, ip, or udp.  It just hands us
        # the whole ethernet frame.  Pretty buggy, but we can work around it by
        # just looking at the end.  RealDevice will only hand us the UDP
        # payload, which will also work here.
        self.assertEqual(message, packet[-len(message):])



class FakeDeviceTests(TunnelDeviceTestsMixin, SynchronousTestCase):
    def device(self):
        return FakeSpecial()



class RealSpecial(object):
    open = staticmethod(os.open)
    read = staticmethod(os.read)
    write = staticmethod(os.write)
    close = staticmethod(os.close)
    ioctl = staticmethod(fcntl.ioctl)

    setNonBlocking = staticmethod(setNonBlocking)

    def sendUDP(self, datagram, address):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(('10.0.0.1', 0))
        s.sendto(datagram, address)


    def receiveUDP(self, host, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # s.setblocking(False)
        s.bind((host, port))
        return s



class RealDeviceTests(TunnelDeviceTestsMixin, SynchronousTestCase):
    def device(self):
        # Create a tap-style tunnel device.  Ethernet frames come out of this
        # and ethernet frames must be put into it.  Grant access to it to an
        # otherwise unprivileged user.
        #
        #         ip tuntap add dev tap-twistedtest mode tap user exarkun group exarkun
        #
        # Bring the device up, since otherwise it's not usable for anything.
        #
        #         ip link set up dev tap-twistedtest
        #
        # Give the device an address.  Just like an ethernet device may be given
        # an address, perhaps a statically allocated one.  This will also
        # implicitly create a route for traffic destined for addresses on the
        # same network as the address assigned here to travel via this device.
        #
        #         ip addr add 10.0.0.1/24 dev tap-twistedtest
        #
        # Statically populate the arp cache with some addresses that might exist
        # on that network and thus be accessible via this device.
        #
        #         ip neigh add 10.0.0.2 lladdr de:ad:be:ef:ca:fe dev tap-twistedtest
        #
        # Once all that's done, RealSpecial will satisfy the requirements of the
        # tests inherited by this class.
        #
        # You can undo it all just by getting rid of the tunnel device.
        #
        #         ip tuntap del dev tap-twistedtest mode tap
        #
        return RealSpecial()



class TunnelTestsMixin(object):
    def setUp(self):
        self.name = b"tun0"
        self.device = FakeSpecial()
        self.protocol = self.factory.buildProtocol(None)
        self.clock = Clock()
        self.reactor = CompositeReactor([self.clock, ReactorFDSet()])
        self.port = TuntapPort(self.name, self.protocol, reactor=self.reactor)
        for name in self.device.OPERATIONS:
            setattr(self.port, '_' + name, getattr(self.device, name))


    def test_startListeningOpensDevice(self):
        """
        L{TuntapPort.startListening} opens the tunnel factory character special
        device C{"/dev/net/tun"} and configures it as a I{tun} tunnel.
        """
        self.port.startListening()
        tunnel = self.device.getTunnel(self.port)
        self.assertEqual(os.O_RDWR, tunnel.fileMode)
        self.assertEqual(
            b"tun0" + "\x00" * (IFNAMSIZ - len(b"tun0")), tunnel.requestedName)
        self.assertEqual(tunnel.name, self.port.interface)
        self.assertFalse(tunnel.blocking)
        self.assertTrue(tunnel.closeOnExec)
        self.assertTrue(self.port.connected)


    def test_startListeningConnectsProtocol(self):
        """
        L{TuntapPort.startListening} calls C{makeConnection} on the protocol the
        port was initialized with, passing the port as an argument.
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
        self.device.permissions.remove('open')
        self.assertRaises(CannotListenError, self.port.startListening)


    def test_startListeningHandlesConfigureFailure(self):
        """
        L{TuntapPort.startListening} raises L{CannotListenError} if the C{ioctl}
        call to configure the tunnel device fails.
        """
        self.device.permissions.remove('ioctl')
        self.assertRaises(CannotListenError, self.port.startListening)


    def _stopPort(self, port):
        stopped = port.stopListening()
        self.assertNotIn(port, self.reactor.getReaders())
        # An unfortunate implementation detail
        self.clock.advance(0)
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
        self.assertNotIn(fileno, self.device._tunnels)


    def test_stopListeningStopsProtocol(self):
        """
        L{TuntapPort.stopListening} calls C{doStop} on the protocol the port was
        initialized with.
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
        self.clock.advance(0)
        self.assertIdentical(None, self.successResultOf(first))
        self.assertIdentical(None, self.successResultOf(second))


    def test_loseConnection(self):
        """
        L{TuntapPort.loseConnection} stops the port and is deprecated.
        """
        self.port.startListening()

        self.port.loseConnection()
        # An unfortunate implementation detail
        self.clock.advance(0)

        self.assertFalse(self.port.connected)
        warnings = self.flushWarnings([self.test_loseConnection])
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(
            "TuntapPort.loseConnection is deprecated since Twisted 12.3.  "
            "Use TuntapPort.stopListening instead.",
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
        tunnel = self.device.getTunnel(self.port)
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


    def test_ewouldblockStopsReading(self):
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
        tunnel = self.device.getTunnel(self.port)
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
        tunnel = self.device.getTunnel(self.port)
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
        tunnel = self.device.getTunnel(self.port)
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
        self.device.getTunnel(self.port).readBuffer.append(b"ping")

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
            self.device.getTunnel(self.port).writeBuffer,
            deque([datagram]))


    def test_interruptedWrite(self):
        """
        If the platform write call is interrupted (causing the Python wrapper to
        raise C{IOError} with errno set to C{EINTR}), the write is re-tried.
        """
        self.port.startListening()
        tunnel = self.device.getTunnel(self.port)
        tunnel.pendingSignals.append(SIGCHLD)
        self.port.write(b"hello, world")
        self.assertEqual(deque([b"hello, world"]), tunnel.writeBuffer)


    def test_unhandledWriteError(self):
        """
        Any exception raised by the underlying write call, except for EINTR, is
        propagated to the caller.
        """
        self.port.startListening()
        tunnel = self.device.getTunnel(self.port)
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
            self.device.getTunnel(self.port).writeBuffer,
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
            self.device.getTunnel(self.port).name, address.name)


    def test_listeningString(self):
        """
        The string representation of a L{TuntapPort} instance includes the
        tunnel type and interface and the protocol associated with the port.
        """
        self.port.startListening()
        expected = "<%s listening on %s/%s>" % (
            fullyQualifiedName(self.protocol.__class__),
            self.TUNNEL_TYPE.name,
            self.device.getTunnel(self.port).name)

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
        string C{"TUNTAP"} or the name of the tunnel interface, while triggering
        a deprecation warning.
        """
        address = TunnelAddress(TunnelType.TAP, "tap0")
        self.assertEqual("TUNTAP", address[0])
        self.assertEqual("tap0", address[1])
        warnings = self.flushWarnings([self.test_indexing])
        message = (
            "TunnelAddress.__getitem__ is deprecated since Twisted 12.3.  "
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
