# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorUDP}.
"""

__metaclass__ = type

from zope.interface.verify import verifyObject

from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.internet.interfaces import IListeningPort
from twisted.internet.protocol import DatagramProtocol

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

globals().update(UDPServerTestsBuilder.makeTestCaseClasses())
