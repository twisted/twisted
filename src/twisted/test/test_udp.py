# -*- test-case-name: twisted.test.test_udp -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorUDP} and L{IReactorMulticast}.
"""

from __future__ import annotations

import os
from socket import (
    AF_INET,
    AF_INET6,
    IP_ADD_MEMBERSHIP,
    IPPROTO_IP,
    IPPROTO_IPV6,
    IPV6_JOIN_GROUP,
    SOCK_DGRAM,
    AddressFamily,
    if_nameindex,
    inet_pton,
    socket,
)
from unittest import skipIf

from twisted.internet import defer, error, interfaces, protocol, reactor, udp
from twisted.internet.address import IPv4Address, IPv6Address
from twisted.internet.defer import Deferred, gatherResults, maybeDeferred
from twisted.internet.error import MulticastJoinError
from twisted.internet.interfaces import (
    IMulticastTransport,
    IReactorMulticast,
    IReactorTime,
)
from twisted.internet.task import deferLater
from twisted.python import runtime
from twisted.test.testutils import skipWithoutIPv6
from twisted.trial.unittest import SkipTest, TestCase


class Mixin:
    started = 0
    stopped = 0

    startedDeferred = None

    def __init__(self):
        self.packets = []

    def startProtocol(self):
        self.started = 1
        if self.startedDeferred is not None:
            d, self.startedDeferred = self.startedDeferred, None
            d.callback(None)

    def stopProtocol(self):
        self.stopped = 1


class Server(Mixin, protocol.DatagramProtocol):
    packetReceived: Deferred[None] | None = None
    refused = 0
    transport: IMulticastTransport

    def datagramReceived(self, data, addr):
        self.packets.append((data, addr))
        if self.packetReceived is not None:
            d, self.packetReceived = self.packetReceived, None
            d.callback(None)


class Client(Mixin, protocol.ConnectedDatagramProtocol):
    packetReceived = None
    refused = 0

    def datagramReceived(self, data):
        self.packets.append(data)
        if self.packetReceived is not None:
            d, self.packetReceived = self.packetReceived, None
            d.callback(None)

    def connectionFailed(self, failure):
        if self.startedDeferred is not None:
            d, self.startedDeferred = self.startedDeferred, None
            d.errback(failure)
        self.failure = failure

    def connectionRefused(self):
        if self.startedDeferred is not None:
            d, self.startedDeferred = self.startedDeferred, None
            d.errback(error.ConnectionRefusedError("yup"))
        self.refused = 1


class GoodClient(Server):
    def connectionRefused(self):
        if self.startedDeferred is not None:
            d, self.startedDeferred = self.startedDeferred, None
            d.errback(error.ConnectionRefusedError("yup"))
        self.refused = 1


class BadClientError(Exception):
    """
    Raised by BadClient at the end of every datagramReceived call to try and
    screw stuff up.
    """


class BadClient(protocol.DatagramProtocol):
    """
    A DatagramProtocol which always raises an exception from datagramReceived.
    Used to test error handling behavior in the reactor for that method.
    """

    d = None

    def setDeferred(self, d):
        """
        Set the Deferred which will be called back when datagramReceived is
        called.
        """
        self.d = d

    def datagramReceived(self, bytes, addr):
        if self.d is not None:
            d, self.d = self.d, None
            d.callback(bytes)
        raise BadClientError("Application code is very buggy!")


@skipIf(not interfaces.IReactorUDP(reactor, None), "This reactor does not support UDP")
class UDPTests(TestCase):
    def test_oldAddress(self):
        """
        The C{type} of the host address of a listening L{DatagramProtocol}'s
        transport is C{"UDP"}.
        """
        server = Server()
        d = server.startedDeferred = defer.Deferred()
        p = reactor.listenUDP(0, server, interface="127.0.0.1")

        def cbStarted(ignored):
            addr = p.getHost()
            self.assertEqual(addr.type, "UDP")
            return p.stopListening()

        return d.addCallback(cbStarted)

    def test_startStop(self):
        """
        The L{DatagramProtocol}'s C{startProtocol} and C{stopProtocol}
        methods are called when its transports starts and stops listening,
        respectively.
        """
        server = Server()
        d = server.startedDeferred = defer.Deferred()
        port1 = reactor.listenUDP(0, server, interface="127.0.0.1")

        def cbStarted(ignored):
            self.assertEqual(server.started, 1)
            self.assertEqual(server.stopped, 0)
            return port1.stopListening()

        def cbStopped(ignored):
            self.assertEqual(server.stopped, 1)

        return d.addCallback(cbStarted).addCallback(cbStopped)

    def test_rebind(self):
        """
        Re-listening with the same L{DatagramProtocol} re-invokes the
        C{startProtocol} callback.
        """
        server = Server()
        d = server.startedDeferred = defer.Deferred()
        p = reactor.listenUDP(0, server, interface="127.0.0.1")

        def cbStarted(ignored, port):
            return port.stopListening()

        def cbStopped(ignored):
            d = server.startedDeferred = defer.Deferred()
            p = reactor.listenUDP(0, server, interface="127.0.0.1")
            return d.addCallback(cbStarted, p)

        return d.addCallback(cbStarted, p)

    def test_bindError(self):
        """
        A L{CannotListenError} exception is raised when attempting to bind a
        second protocol instance to an already bound port
        """
        server = Server()
        d = server.startedDeferred = defer.Deferred()
        port = reactor.listenUDP(0, server, interface="127.0.0.1")

        def cbStarted(ignored):
            self.assertEqual(port.getHost(), server.transport.getHost())
            server2 = Server()
            self.assertRaises(
                error.CannotListenError,
                reactor.listenUDP,
                port.getHost().port,
                server2,
                interface="127.0.0.1",
            )

        d.addCallback(cbStarted)

        def cbFinished(ignored):
            return port.stopListening()

        d.addCallback(cbFinished)
        return d

    def test_sendPackets(self):
        """
        Datagrams can be sent with the transport's C{write} method and
        received via the C{datagramReceived} callback method.
        """
        server = Server()
        serverStarted = server.startedDeferred = defer.Deferred()
        port1 = reactor.listenUDP(0, server, interface="127.0.0.1")

        client = GoodClient()
        clientStarted = client.startedDeferred = defer.Deferred()

        def cbServerStarted(ignored):
            self.port2 = reactor.listenUDP(0, client, interface="127.0.0.1")
            return clientStarted

        d = serverStarted.addCallback(cbServerStarted)

        def cbClientStarted(ignored):
            client.transport.connect("127.0.0.1", server.transport.getHost().port)
            cAddr = client.transport.getHost()
            sAddr = server.transport.getHost()

            serverSend = client.packetReceived = defer.Deferred()
            server.transport.write(b"hello", (cAddr.host, cAddr.port))

            clientWrites = [(b"a",), (b"b", None), (b"c", (sAddr.host, sAddr.port))]

            def cbClientSend(ignored):
                if clientWrites:
                    nextClientWrite = server.packetReceived = defer.Deferred()
                    nextClientWrite.addCallback(cbClientSend)
                    client.transport.write(*clientWrites.pop(0))
                    return nextClientWrite

            # No one will ever call .errback on either of these Deferreds,
            # but there is a non-trivial amount of test code which might
            # cause them to fail somehow.  So fireOnOneErrback=True.
            return defer.DeferredList(
                [cbClientSend(None), serverSend], fireOnOneErrback=True
            )

        d.addCallback(cbClientStarted)

        def cbSendsFinished(ignored):
            cAddr = client.transport.getHost()
            sAddr = server.transport.getHost()
            self.assertEqual(client.packets, [(b"hello", (sAddr.host, sAddr.port))])
            clientAddr = (cAddr.host, cAddr.port)
            self.assertEqual(
                server.packets,
                [(b"a", clientAddr), (b"b", clientAddr), (b"c", clientAddr)],
            )

        d.addCallback(cbSendsFinished)

        def cbFinished(ignored):
            return defer.DeferredList(
                [
                    defer.maybeDeferred(port1.stopListening),
                    defer.maybeDeferred(self.port2.stopListening),
                ],
                fireOnOneErrback=True,
            )

        d.addCallback(cbFinished)
        return d

    @skipIf(
        os.environ.get("INFRASTRUCTURE") == "AZUREPIPELINES",
        "Hangs on Pipelines due to firewall",
    )
    def test_connectionRefused(self):
        """
        A L{ConnectionRefusedError} exception is raised when a connection
        attempt is actively refused by the other end.

        Note: This test assumes no one is listening on port 80 UDP.
        """
        client = GoodClient()
        clientStarted = client.startedDeferred = defer.Deferred()
        port = reactor.listenUDP(0, client, interface="127.0.0.1")

        server = Server()
        serverStarted = server.startedDeferred = defer.Deferred()
        port2 = reactor.listenUDP(0, server, interface="127.0.0.1")

        d = defer.DeferredList([clientStarted, serverStarted], fireOnOneErrback=True)

        def cbStarted(ignored):
            connectionRefused = client.startedDeferred = defer.Deferred()
            client.transport.connect("127.0.0.1", 80)

            for i in range(10):
                client.transport.write(b"%d" % (i,))
                server.transport.write(b"%d" % (i,), ("127.0.0.1", 80))

            return self.assertFailure(connectionRefused, error.ConnectionRefusedError)

        d.addCallback(cbStarted)

        def cbFinished(ignored):
            return defer.DeferredList(
                [
                    defer.maybeDeferred(port.stopListening),
                    defer.maybeDeferred(port2.stopListening),
                ],
                fireOnOneErrback=True,
            )

        d.addCallback(cbFinished)
        return d

    def test_serverReadFailure(self):
        """
        When a server fails to successfully read a packet the server should
        still be able to process future packets.
        The IOCP reactor had a historical problem where a failure to read caused
        the reactor to ignore any future reads. This test should prevent a regression.

        Note: This test assumes no one is listening on port 80 UDP.
        """
        client = GoodClient()
        clientStarted = client.startedDeferred = defer.Deferred()
        clientPort = reactor.listenUDP(0, client, interface="127.0.0.1")
        test_data_to_send = b"Sending test packet to server"

        server = Server()
        serverStarted = server.startedDeferred = defer.Deferred()
        serverGotData = server.packetReceived = defer.Deferred()
        serverPort = reactor.listenUDP(0, server, interface="127.0.0.1")

        server_client_started_d = defer.DeferredList(
            [clientStarted, serverStarted], fireOnOneErrback=True
        )

        def cbClientAndServerStarted(ignored):
            # Server has started. Now the server can send a
            # packet to a random port no one is listening on. On windows, for example, this
            # will cause an ICMP message to come back on the port telling us no one is listening.
            # We need to be able to gracefully handle this situation and continue processing
            # requests.
            server.transport.write(
                b"write to port no one is listening to", ("127.0.0.1", 80)
            )
            client.transport.write(
                test_data_to_send, ("127.0.0.1", serverPort._realPortNumber)
            )

        server_client_started_d.addCallback(cbClientAndServerStarted)

        all_data_sent = defer.DeferredList(
            [server_client_started_d, serverGotData], fireOnOneErrback=True
        )

        def verify_server_got_data(ignored):
            self.assertEqual(server.packets[0][0], test_data_to_send)

        all_data_sent.addCallback(verify_server_got_data)

        def cleanup(ignored):
            return defer.DeferredList(
                [
                    defer.maybeDeferred(clientPort.stopListening),
                    defer.maybeDeferred(serverPort.stopListening),
                ],
                fireOnOneErrback=True,
            )

        all_data_sent.addCallback(cleanup)

        return all_data_sent

    def test_badConnect(self):
        """
        A call to the transport's connect method fails with an
        L{InvalidAddressError} when a non-IP address is passed as the host
        value.

        A call to a transport's connect method fails with a L{RuntimeError}
        when the transport is already connected.
        """
        client = GoodClient()
        port = reactor.listenUDP(0, client, interface="127.0.0.1")
        self.assertRaises(
            error.InvalidAddressError, client.transport.connect, "localhost", 80
        )
        client.transport.connect("127.0.0.1", 80)
        self.assertRaises(RuntimeError, client.transport.connect, "127.0.0.1", 80)
        return port.stopListening()

    def test_datagramReceivedError(self):
        """
        When datagramReceived raises an exception it is logged but the port
        is not disconnected.
        """
        finalDeferred = defer.Deferred()

        def cbCompleted(ign):
            """
            Flush the exceptions which the reactor should have logged and make
            sure they're actually there.
            """
            errs = self.flushLoggedErrors(BadClientError)
            self.assertEqual(
                len(errs), 2, "Incorrectly found %d errors, expected 2" % (len(errs),)
            )

        finalDeferred.addCallback(cbCompleted)

        client = BadClient()
        port = reactor.listenUDP(0, client, interface="127.0.0.1")

        def cbCleanup(result):
            """
            Disconnect the port we started and pass on whatever was given to us
            in case it was a Failure.
            """
            return defer.maybeDeferred(port.stopListening).addBoth(lambda ign: result)

        finalDeferred.addBoth(cbCleanup)

        addr = port.getHost()

        # UDP is not reliable.  Try to send as many as 60 packets before giving
        # up.  Conceivably, all sixty could be lost, but they probably won't be
        # unless all UDP traffic is being dropped, and then the rest of these
        # UDP tests will likely fail as well.  Ideally, this test (and probably
        # others) wouldn't even use actual UDP traffic: instead, they would
        # stub out the socket with a fake one which could be made to behave in
        # whatever way the test desires.  Unfortunately, this is hard because
        # of differences in various reactor implementations.
        attempts = list(range(60))
        succeededAttempts = []

        def makeAttempt():
            """
            Send one packet to the listening BadClient.  Set up a 0.1 second
            timeout to do re-transmits in case the packet is dropped.  When two
            packets have been received by the BadClient, stop sending and let
            the finalDeferred's callbacks do some assertions.
            """
            if not attempts:
                try:
                    self.fail("Not enough packets received")
                except Exception:
                    finalDeferred.errback()

            self.failIfIdentical(
                client.transport, None, "UDP Protocol lost its transport"
            )

            packet = b"%d" % (attempts.pop(0),)
            packetDeferred = defer.Deferred()
            client.setDeferred(packetDeferred)
            client.transport.write(packet, (addr.host, addr.port))

            def cbPacketReceived(packet):
                """
                A packet arrived.  Cancel the timeout for it, record it, and
                maybe finish the test.
                """
                timeoutCall.cancel()
                succeededAttempts.append(packet)
                if len(succeededAttempts) == 2:
                    # The second error has not yet been logged, since the
                    # exception which causes it hasn't even been raised yet.
                    # Give the datagramReceived call a chance to finish, then
                    # let the test finish asserting things.
                    reactor.callLater(0, finalDeferred.callback, None)
                else:
                    makeAttempt()

            def ebPacketTimeout(err):
                """
                The packet wasn't received quickly enough.  Try sending another
                one.  It doesn't matter if the packet for which this was the
                timeout eventually arrives: makeAttempt throws away the
                Deferred on which this function is the errback, so when
                datagramReceived callbacks, so it won't be on this Deferred, so
                it won't raise an AlreadyCalledError.
                """
                makeAttempt()

            packetDeferred.addCallbacks(cbPacketReceived, ebPacketTimeout)
            packetDeferred.addErrback(finalDeferred.errback)

            timeoutCall = reactor.callLater(
                0.1,
                packetDeferred.errback,
                error.TimeoutError("Timed out in testDatagramReceivedError"),
            )

        makeAttempt()
        return finalDeferred

    def test_NoWarningOnBroadcast(self):
        """
        C{'<broadcast>'} is an alternative way to say C{'255.255.255.255'}
        ({socket.gethostbyname("<broadcast>")} returns C{'255.255.255.255'}),
        so because it becomes a valid IP address, no deprecation warning about
        passing hostnames to L{twisted.internet.udp.Port.write} needs to be
        emitted by C{write()} in this case.
        """

        class fakeSocket:
            def sendto(self, foo, bar):
                pass

        p = udp.Port(0, Server())
        p.socket = fakeSocket()
        p.write(b"test", ("<broadcast>", 1234))

        warnings = self.flushWarnings([self.test_NoWarningOnBroadcast])
        self.assertEqual(len(warnings), 0)


@skipIf(not interfaces.IReactorUDP(reactor, None), "This reactor does not support UDP")
class ReactorShutdownInteractionTests(TestCase):
    """Test reactor shutdown interaction"""

    if not interfaces.IReactorUDP(reactor, None):
        skip = "This reactor does not support UDP"

    def setUp(self):
        """Start a UDP port"""
        self.server = Server()
        self.port = reactor.listenUDP(0, self.server, interface="127.0.0.1")

    def tearDown(self):
        """Stop the UDP port"""
        return self.port.stopListening()

    def testShutdownFromDatagramReceived(self):
        """Test reactor shutdown while in a recvfrom() loop"""

        # udp.Port's doRead calls recvfrom() in a loop, as an optimization.
        # It is important this loop terminate under various conditions.
        # Previously, if datagramReceived synchronously invoked
        # reactor.stop(), under certain reactors, the Port's socket would
        # synchronously disappear, causing an AttributeError inside that
        # loop.  This was mishandled, causing the loop to spin forever.
        # This test is primarily to ensure that the loop never spins
        # forever.

        finished = defer.Deferred()
        pr = self.server.packetReceived = defer.Deferred()

        def pktRece(ignored):
            # Simulate reactor.stop() behavior :(
            self.server.transport.connectionLost()
            # Then delay this Deferred chain until the protocol has been
            # disconnected, as the reactor should do in an error condition
            # such as we are inducing.  This is very much a whitebox test.
            reactor.callLater(0, finished.callback, None)

        pr.addCallback(pktRece)

        def flushErrors(ignored):
            # We are breaking abstraction and calling private APIs, any
            # number of horrible errors might occur.  As long as the reactor
            # doesn't hang, this test is satisfied.  (There may be room for
            # another, stricter test.)
            self.flushLoggedErrors()

        finished.addCallback(flushErrors)
        self.server.transport.write(
            b"\0" * 64, ("127.0.0.1", self.server.transport.getHost().port)
        )
        return finished


def checkMulticastAvailability(
    af: AddressFamily, ipproto: int, join: int, group: str, bindto: str
) -> bool:
    """
    Bind a socket to the given network interface and attempt to join a
    multicast group with the given address family.  This is used to determine
    whether the local networking stack configuration allows for multicast
    within the given address family.
    """
    s = socket(af, SOCK_DGRAM)
    s.bind((bindto, 0))
    packgroup = inet_pton(af, group)
    packif = inet_pton(af, bindto)
    try:
        s.setsockopt(ipproto, join, packgroup + packif)
    except OSError:
        return False
    else:
        return True
    finally:
        s.close()


@skipIf(
    not interfaces.IReactorMulticast(reactor, None),
    "This reactor does not support multicast",
)
@skipIf(
    not checkMulticastAvailability(
        AF_INET, IPPROTO_IP, IP_ADD_MEMBERSHIP, "225.0.0.250", "0.0.0.0"
    ),
    "The local networking stack does not enable IPv4 multicast.",
)
class MulticastTests(TestCase):
    """
    Tests for sending and receiving multicast datagrams.  (This suite supports
    IPv4, see below for IPv6.)
    """

    # Define test addresses as class attributes so they may be parameterized
    # for IPv6 below.
    interface: str = "0.0.0.0"
    expectedInterface: str | int = "0.0.0.0"
    clientAddress: str = "127.0.0.1"
    multicastGroup: str = "225.0.0.250"
    alternateInterface: str | int = "127.0.0.1"
    interfaceSynonym: str | int = "localhost"
    invalidGroup: str = "127.0.0.1"
    wrongAddressFamily: str = "::1"

    def setUp(self):
        self.server = Server()
        self.client = Client()
        # multicast won't work if we listen over loopback, apparently
        self.port1 = reactor.listenMulticast(0, self.server, self.interface)
        self.port2 = reactor.listenMulticast(0, self.client, self.interface)
        self.client.transport.connect(
            self.clientAddress,
            self.server.transport.getHost().port,
        )

    def tearDown(self):
        return gatherResults(
            [
                maybeDeferred(self.port1.stopListening),
                maybeDeferred(self.port2.stopListening),
            ]
        )

    def testTTL(self) -> None:
        if self.server.transport.addressFamily != AF_INET:
            raise SkipTest("only IPv4 multicast has TTLs, IPv6 has hops")

        def checkttl(o: Server | Client) -> None:
            assert IMulticastTransport.providedBy(o.transport)
            self.assertEqual(o.transport.getTTL(), 1)
            o.transport.setTTL(2)
            self.assertEqual(o.transport.getTTL(), 2)

        checkttl(self.client)
        checkttl(self.server)

    async def test_loopback(self) -> None:
        """
        Test that after loopback mode has been set, multicast packets are
        delivered to their sender.
        """
        group = self.multicastGroup
        self.assertEqual(self.server.transport.getLoopbackMode(), 1)
        addr = self.server.transport.getHost()

        await self.server.transport.joinGroup(group)
        self.server.packetReceived = Deferred()
        self.server.transport.write(b"hello", (group, addr.port))
        await self.server.packetReceived

        self.assertEqual(len(self.server.packets), 1)
        self.server.transport.setLoopbackMode(0)
        self.assertEqual(self.server.transport.getLoopbackMode(), 0)
        self.server.transport.write(b"hello", (group, addr.port))

        # This is a recipe for a flaky test, but we need to let the reactor
        # spin a bit to let the packet through.
        await deferLater(IReactorTime(reactor), 0)
        self.assertEqual(len(self.server.packets), 1)

    async def test_wrongFamilyInterfaceJoin(self) -> None:
        """
        A sensible error will be reported when using the wrong address family
        literal for the 'interface' argument to 'joinGroup'.
        """
        with self.assertRaises(MulticastJoinError):
            await self.server.transport.joinGroup(
                self.multicastGroup, interface=self.wrongAddressFamily
            )

    async def test_interface(self) -> None:
        """
        Test C{getOutgoingInterface} and C{setOutgoingInterface}.
        """
        self.assertEqual(
            self.client.transport.getOutgoingInterface(), self.expectedInterface
        )
        self.assertEqual(
            self.server.transport.getOutgoingInterface(), self.expectedInterface
        )

        await self.server.transport.setOutgoingInterface(self.alternateInterface)
        await self.client.transport.setOutgoingInterface(self.interfaceSynonym)

        self.assertEqual(
            self.client.transport.getOutgoingInterface(),
            self.alternateInterface,
        )
        self.assertEqual(
            self.server.transport.getOutgoingInterface(),
            self.alternateInterface,
        )

    async def test_joinLeave(self) -> None:
        """
        Test that multicast a group can be joined and left.
        """
        await self.client.transport.joinGroup(self.multicastGroup)
        await self.client.transport.leaveGroup(self.multicastGroup)
        await self.server.transport.joinGroup(self.multicastGroup)
        await self.server.transport.leaveGroup(self.multicastGroup)

    # FIXME: https://twistedmatrix.com/trac/ticket/7780
    @skipIf(
        runtime.platform.isWindows() and not runtime.platform.isVista(),
        "Windows' UDP multicast is not yet fully supported.",
    )
    def test_joinFailure(self):
        """
        Test that an attempt to join an address which is not a multicast
        address fails with L{error.MulticastJoinError}.
        """
        # 127.0.0.1 is not a multicast address, so joining it should fail.
        return self.assertFailure(
            self.client.transport.joinGroup(self.invalidGroup), error.MulticastJoinError
        )

    def test_multicast(self):
        """
        Test that a multicast group can be joined and messages sent to and
        received from it.
        """
        c = Server()
        p = reactor.listenMulticast(0, c, self.interface)
        addr = self.server.transport.getHost()

        joined = self.server.transport.joinGroup(self.multicastGroup)

        def cbJoined(ignored):
            d = self.server.packetReceived = Deferred()
            c.transport.write(b"hello world", (self.multicastGroup, addr.port))
            return d

        joined.addCallback(cbJoined)

        def cbPacket(ignored):
            self.assertEqual(self.server.packets[0][0], b"hello world")

        joined.addCallback(cbPacket)

        def cleanup(passthrough):
            result = maybeDeferred(p.stopListening)
            result.addCallback(lambda ign: passthrough)
            return result

        joined.addCallback(cleanup)

        return joined

    @skipIf(
        runtime.platform.isWindows(),
        "on non-linux platforms it appears multiple "
        "processes can listen, but not multiple sockets "
        "in same process?",
    )
    async def test_multiListen(self) -> None:
        """
        Test that multiple sockets can listen on the same multicast port and
        that they both receive multicast messages directed to that address.
        """
        firstClient = Server()
        mreactor = IReactorMulticast(reactor)
        firstPort = mreactor.listenMulticast(
            0, firstClient, listenMultiple=True, interface=self.interface
        )
        fpAddr = firstPort.getHost()
        assert isinstance(fpAddr, (IPv4Address, IPv6Address))
        portno = fpAddr.port

        secondClient = Server()
        secondPort = mreactor.listenMulticast(
            portno,
            secondClient,
            listenMultiple=True,
            interface=self.interface,
        )

        await gatherResults(
            [
                self.server.transport.joinGroup(self.multicastGroup),
                firstPort.joinGroup(self.multicastGroup),
                secondPort.joinGroup(self.multicastGroup),
            ]
        )

        d1: Deferred[None]
        d1 = firstClient.packetReceived = Deferred()
        d2: Deferred[None]
        d2 = secondClient.packetReceived = Deferred()

        firstClient.transport.write(b"hello world", (self.multicastGroup, portno))
        await gatherResults([d1, d2])

        self.assertEqual(firstClient.packets[0][0], b"hello world")
        self.assertEqual(secondClient.packets[0][0], b"hello world")

        await gatherResults(
            [
                maybeDeferred(firstPort.stopListening),
                maybeDeferred(secondPort.stopListening),
            ]
        )


@skipIf(
    not interfaces.IReactorMulticast(reactor, None),
    "This reactor does not support multicast",
)
@skipWithoutIPv6
@skipIf(
    not checkMulticastAvailability(
        AF_INET6, IPPROTO_IPV6, IPV6_JOIN_GROUP, "ff03::1", "::"
    ),
    "The local stack does not enable IPv6 multicast.",
)
class MulticastTestsIPv6(MulticastTests):
    """
    Tests for sending and receiving IPv6 multicast datagrams.
    """

    # Specifiy relevant IPv6 literals and values to override the IPv4 values in
    # the superclass; all of these attributes are defined above.
    interface: str = "::"
    clientAddress: str = "::1"
    multicastGroup: str = "ff03::1"
    alternateInterface: str | int = next(
        (idxnm[0] for idxnm in if_nameindex() if idxnm[1].startswith("lo"))
    )
    interfaceSynonym: str | int = alternateInterface
    invalidGroup: str = "::1"
    expectedInterface: str | int = 0
    wrongAddressFamily: str = "127.0.0.1"
