# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorUDP}.
"""

__metaclass__ = type

from socket import SOCK_DGRAM

from zope.interface.verify import verifyObject

from twisted.python import context
from twisted.python.log import ILogContext, err
from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.internet.defer import Deferred
from twisted.internet.interfaces import IListeningPort
from twisted.internet.address import IPv4Address
from twisted.internet.protocol import DatagramProtocol

from twisted.internet.test.test_tcp import findFreePort


class UDPServerTestsBuilder(ReactorBuilder):
    """
    Builder defining tests relating to L{IReactorUDP.listenUDP}.
    """
    def test_interface(self):
        """
        L{IReactorUDP.listenUDP} returns an object providing L{IListeningPort}.
        """
        reactor = self.buildReactor()
        port = reactor.listenUDP(0, DatagramProtocol())
        self.assertTrue(verifyObject(IListeningPort, port))


    def test_getHost(self):
        """
        L{IListeningPort.getHost} returns an L{IPv4Address} giving a
        dotted-quad of the IPv4 address the port is listening on as well as
        the port number.
        """
        host, portNumber = findFreePort(type=SOCK_DGRAM)
        reactor = self.buildReactor()
        port = reactor.listenUDP(
            portNumber, DatagramProtocol(), interface=host)
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
        port = reactor.listenUDP(0, protocol)
        address = port.getHost()

        def gotSystem(system):
            self.assertEqual("Custom Datagrams (UDP)", system)
        d.addCallback(gotSystem)
        d.addErrback(err)
        d.addCallback(lambda ignored: reactor.stop())

        port.write("some bytes", ('127.0.0.1', address.port))
        self.runReactor(reactor)


globals().update(UDPServerTestsBuilder.makeTestCaseClasses())
