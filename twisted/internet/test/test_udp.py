# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorUDP} and the UDP parts of
L{IReactorSocket}.
"""

from __future__ import division, absolute_import

__metaclass__ = type

import socket

from zope.interface.verify import verifyObject

from twisted.python import context
from twisted.python.log import ILogContext, err
from twisted.internet.test.reactormixins import (
    DatagramPortLoggingTestsMixin, ReactorBuilder)
from twisted.internet.defer import Deferred
from twisted.internet.interfaces import (
    IListeningPort, IReactorUDP, IReactorSocket)
from twisted.internet.address import IPv4Address
from twisted.internet.protocol import DatagramProtocol
from twisted.internet import udp
from twisted.internet.test.connectionmixins import (LogObserverMixin,
                                                    findFreePort)
from twisted.trial.unittest import SkipTest, SynchronousTestCase



class DatagramTransportTestsMixin(LogObserverMixin):
    """
    Mixin defining tests which apply to any port/datagram based transport.
    """
    def test_stopProtocolScheduling(self):
        """
        L{DatagramProtocol.stopProtocol} is called asynchronously (ie, not
        re-entrantly) when C{stopListening} is used to stop the the datagram
        transport.
        """
        class DisconnectingProtocol(DatagramProtocol):

            started = False
            stopped = False
            inStartProtocol = False
            stoppedInStart = False

            def startProtocol(self):
                self.started = True
                self.inStartProtocol = True
                self.transport.stopListening()
                self.inStartProtocol = False

            def stopProtocol(self):
                self.stopped = True
                self.stoppedInStart = self.inStartProtocol
                reactor.stop()

        reactor = self.buildReactor()
        protocol = DisconnectingProtocol()
        self.getListeningPort(reactor, protocol)
        self.runReactor(reactor)

        self.assertTrue(protocol.started)
        self.assertTrue(protocol.stopped)
        self.assertFalse(protocol.stoppedInStart)



class UDPPortTestsMixin(object):
    """
    Tests for L{IReactorUDP.listenUDP} and
    L{IReactorSocket.adoptDatagramPort}.
    """
    def test_interface(self):
        """
        L{IReactorUDP.listenUDP} returns an object providing L{IListeningPort}.
        """
        reactor = self.buildReactor()
        port = self.getListeningPort(reactor, DatagramProtocol())
        self.assertTrue(verifyObject(IListeningPort, port))


    def test_getHost(self):
        """
        L{IListeningPort.getHost} returns an L{IPv4Address} giving a
        dotted-quad of the IPv4 address the port is listening on as well as
        the port number.
        """
        host, portNumber = findFreePort(type=socket.SOCK_DGRAM)
        reactor = self.buildReactor()
        port = self.getListeningPort(
            reactor, DatagramProtocol(), port=portNumber, interface=host)
        self.assertEqual(
            port.getHost(), IPv4Address('UDP', host, portNumber))


    def test_logPrefix(self):
        """
        Datagram transports implement L{ILoggingContext.logPrefix} to return a
        message reflecting the protocol they are running.
        """
        class CustomLogPrefixDatagramProtocol(DatagramProtocol):
            def __init__(self, prefix):
                self._prefix = prefix
                self.system = Deferred()

            def logPrefix(self):
                return self._prefix

            def datagramReceived(self, bytes, addr):
                if self.system is not None:
                    system = self.system
                    self.system = None
                    system.callback(context.get(ILogContext)["system"])

        reactor = self.buildReactor()
        protocol = CustomLogPrefixDatagramProtocol("Custom Datagrams")
        d = protocol.system
        port = self.getListeningPort(reactor, protocol)
        address = port.getHost()

        def gotSystem(system):
            self.assertEqual("Custom Datagrams (UDP)", system)
        d.addCallback(gotSystem)
        d.addErrback(err)
        d.addCallback(lambda ignored: reactor.stop())

        port.write(b"some bytes", ('127.0.0.1', address.port))
        self.runReactor(reactor)


    def test_str(self):
        """
        C{str()} on the listening port object includes the port number.
        """
        reactor = self.buildReactor()
        port = self.getListeningPort(reactor, DatagramProtocol())
        self.assertIn(str(port.getHost().port), str(port))


    def test_repr(self):
        """
        C{repr()} on the listening port object includes the port number.
        """
        reactor = self.buildReactor()
        port = self.getListeningPort(reactor, DatagramProtocol())
        self.assertIn(repr(port.getHost().port), str(port))



class UDPServerTestsBuilder(ReactorBuilder,
                            UDPPortTestsMixin, DatagramTransportTestsMixin):
    """
    Run L{UDPPortTestsMixin} tests using newly created UDP
    sockets.
    """
    requiredInterfaces = (IReactorUDP,)

    def getListeningPort(self, reactor, protocol, port=0, interface='',
                         maxPacketSize=8192):
        """
        Get a UDP port from a reactor.

        @param reactor: A reactor used to build the returned
            L{IListeningPort} provider.
        @type reactor: L{twisted.internet.interfaces.IReactorUDP}

        @see: L{twisted.internet.IReactorUDP.listenUDP} for other
            argument and return types.
        """
        return reactor.listenUDP(port, protocol, interface=interface,
                                 maxPacketSize=maxPacketSize)



class UDPFDServerTestsBuilder(ReactorBuilder,
                              UDPPortTestsMixin, DatagramTransportTestsMixin):
    """
    Run L{UDPPortTestsMixin} tests using adopted UDP sockets.
    """
    requiredInterfaces = (IReactorSocket,)

    def getListeningPort(self, reactor, protocol, port=0, interface='',
                         maxPacketSize=8192):
        """
        Get a UDP port from a reactor, wrapping an already-initialized file
        descriptor.

        @param reactor: A reactor used to build the returned
            L{IListeningPort} provider.
        @type reactor: L{twisted.internet.interfaces.IReactorSocket}

        @param port: A port number to which the adopted socket will be
            bound.
        @type port: C{int}

        @param interface: The local IPv4 or IPv6 address to which the
            adopted socket will be bound.  defaults to '', ie all IPv4
            addresses.
        @type interface: C{str}

        @see: L{twisted.internet.IReactorSocket.adoptDatagramPort} for other
            argument and return types.
        """
        if IReactorSocket.providedBy(reactor):
            if ':' in interface:
                domain = socket.AF_INET6
                address = socket.getaddrinfo(interface, port)[0][4]
            else:
                domain = socket.AF_INET
                address = (interface, port)
            portSock = socket.socket(domain, socket.SOCK_DGRAM)
            portSock.bind(address)
            portSock.setblocking(False)
            try:
                return reactor.adoptDatagramPort(
                    portSock.fileno(), portSock.family, protocol,
                    maxPacketSize)
            finally:
                # The socket should still be open; fileno will raise if it is
                # not.
                portSock.fileno()
                # Now clean it up, because the rest of the test does not need
                # it.
                portSock.close()
        else:
            raise SkipTest("Reactor does not provide IReactorSocket")



globals().update(UDPServerTestsBuilder.makeTestCaseClasses())
globals().update(UDPFDServerTestsBuilder.makeTestCaseClasses())



class PortLoggingTests(DatagramPortLoggingTestsMixin, SynchronousTestCase):
    """
    Tests for the log events produced by the posix L{udp.Port} implementation.
    """
    def portFactory(self, **kwargs):
        """
        Build and return the L{udp.Port} which will listen on an ephemeral port.

        @param kwargs: Keyword arguments for the port.

        @return: A L{udp.Port}
        """
        return udp.Port(port=0, **kwargs)
