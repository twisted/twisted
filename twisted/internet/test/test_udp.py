# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorUDP}.
"""

__metaclass__ = type

from socket import SOCK_DGRAM

from zope.interface import implements
from zope.interface.verify import verifyObject

from twisted.python import context
from twisted.python.log import ILogContext, err
from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.internet.defer import Deferred, maybeDeferred
from twisted.internet.interfaces import ILoggingContext, IListeningPort
from twisted.internet.address import IPv4Address
from twisted.internet.protocol import DatagramProtocol

from twisted.internet.test.test_tcp import findFreePort
from twisted.internet.test.connectionmixins import LogObserverMixin


class UDPPortMixin(object):
    def getListeningPort(self, reactor, protocol):
        """
        Get a UDP port from a reactor.
        """
        return reactor.listenUDP(0, protocol)


    def getExpectedStartListeningLogMessage(self, port, protocol):
        """
        Get the message expected to be logged when a UDP port starts listening.
        """
        return "%s starting on %d" % (protocol, port.getHost().port)


    def getExpectedConnectionLostLogMessage(self, port):
        """
        Get the expected connection lost message for a UDP port.
        """
        return "(UDP Port %s Closed)" % (port.getHost().port,)



class DatagramTransportTestsMixin(LogObserverMixin):
    """
    Mixin defining tests which apply to any port/datagram based transport.
    """
    def test_startedListeningLogMessage(self):
        """
        When a port starts, a message including a description of the associated
        protocol is logged.
        """
        loggedMessages = self.observe()
        reactor = self.buildReactor()
        class SomeProtocol(DatagramProtocol):
            implements(ILoggingContext)
            def logPrefix(self):
                return "Crazy Protocol"
        protocol = SomeProtocol()
        p = self.getListeningPort(reactor, protocol)
        expectedMessage = self.getExpectedStartListeningLogMessage(
            p, "Crazy Protocol")
        self.assertEqual((expectedMessage,), loggedMessages[0]['message'])


    def test_connectionLostLogMessage(self):
        """
        When a connection is lost, an informative message should be logged (see
        L{getExpectedConnectionLostLogMessage}): an address identifying the port
        and the fact that it was closed.
        """
        loggedMessages = self.observe()
        reactor = self.buildReactor()
        p = self.getListeningPort(reactor, DatagramProtocol())
        expectedMessage = self.getExpectedConnectionLostLogMessage(p)

        def stopReactor(ignored):
            reactor.stop()

        def doStopListening():
            del loggedMessages[:]
            maybeDeferred(p.stopListening).addCallback(stopReactor)

        reactor.callWhenRunning(doStopListening)
        self.runReactor(reactor)

        self.assertEqual((expectedMessage,), loggedMessages[0]['message'])


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



class UDPServerTestsBuilder(ReactorBuilder, UDPPortMixin,
                            DatagramTransportTestsMixin):
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
