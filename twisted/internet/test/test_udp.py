# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorUDP}.
"""

__metaclass__ = type

from socket import SOCK_DGRAM

from zope.interface.verify import verifyObject

from twisted.internet.test.reactormixins import ReactorBuilder
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
        self.assertEquals(
            port.getHost(), IPv4Address('UDP', host, portNumber))


globals().update(UDPServerTestsBuilder.makeTestCaseClasses())
