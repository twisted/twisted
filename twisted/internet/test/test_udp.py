# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorUDP}.
"""

__metaclass__ = type

from zope.interface.verify import verifyObject

from twisted.test.testutils import DictSubsetMixin
from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.internet.interfaces import IListeningPort
from twisted.internet.protocol import DatagramProtocol
from twisted.python import log


class UDPServerTestsBuilder(ReactorBuilder, DictSubsetMixin):
    """
    Builder defining tests relating to L{IReactorUDP.listenUDP}.
    """
    def setUp(self):
        """
        Add a log observer to collect log events emitted by the listening port.
        """
        ReactorBuilder.setUp(self)
        self.protocol = DatagramProtocol()
        self.events = []
        log.addObserver(self.events.append)
        self.addCleanup(log.removeObserver, self.events.append)


    def test_interface(self):
        """
        L{IReactorUDP.listenUDP} returns an object providing L{IListeningPort}.
        """
        reactor = self.buildReactor()
        port = reactor.listenUDP(0, DatagramProtocol())
        self.assertTrue(verifyObject(IListeningPort, port))


    def getListeningPort(self, reactor):
        """
        Get a TCP port from a reactor
        """
        return reactor.listenUDP(0, self.protocol)


    def getExpectedConnectionPortNumber(self, port):
        """
        Get the expected port number for the TCP port that experienced
        the connection event.
        """
        return port.getHost().port


    def test_portStartStopLogMessage(self):
        """
        When a UDP port starts or stops listening, a log event is emitted with
        the keys C{"eventSource"}, C{"eventType"}, C{"portNumber"}, and
        C{"protocol"}.
        """
        reactor = self.buildReactor()
        p = self.getListeningPort(reactor)
        listenPort = self.getExpectedConnectionPortNumber(p)
        reactor.callWhenRunning(reactor.stop)
        self.runReactor(reactor)

        expected = {
            "eventSource": p, "portNumber": listenPort,
            "protocol": self.protocol}

        for event in self.events:
            if event.get("eventType") == "start":
                self.assertDictSubset(event, expected)
                break
        else:
            self.fail(
                "Port startup message not found in events: %r" % (self.events,))

        for event in self.events:
            if event.get("eventType") == "stop":
                self.assertDictSubset(event, expected)
                break
        else:
            self.fail(
                "Port shutdown message not found in events: %r" % (
                    self.events,))

globals().update(UDPServerTestsBuilder.makeTestCaseClasses())
