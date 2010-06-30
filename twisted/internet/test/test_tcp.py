# Copyright (c) 2008-2010 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorTCP}.
"""

__metaclass__ = type

import socket

from zope.interface import implements
from zope.interface.verify import verifyObject

from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.internet.error import DNSLookupError
from twisted.internet.interfaces import IResolverSimple, IConnector
from twisted.internet.address import IPv4Address
from twisted.internet.defer import succeed, fail, maybeDeferred
from twisted.internet.protocol import ServerFactory, ClientFactory, Protocol
from twisted.python import log


class Stop(ClientFactory):
    """
    A client factory which stops a reactor when a connection attempt fails.
    """
    def __init__(self, reactor):
        self.reactor = reactor


    def clientConnectionFailed(self, connector, reason):
        self.reactor.stop()



class FakeResolver:
    """
    A resolver implementation based on a C{dict} mapping names to addresses.
    """
    implements(IResolverSimple)

    def __init__(self, names):
        self.names = names


    def getHostByName(self, name, timeout):
        try:
            return succeed(self.names[name])
        except KeyError:
            return fail(DNSLookupError("FakeResolver couldn't find " + name))



class TCPClientTestsBuilder(ReactorBuilder):
    """
    Builder defining tests relating to L{IReactorTCP.connectTCP}.
    """
    def _freePort(self, interface='127.0.0.1'):
        probe = socket.socket()
        try:
            probe.bind((interface, 0))
            return probe.getsockname()
        finally:
            probe.close()

    def test_interface(self):
        """
        L{IReactorTCP.connectTCP} returns an object providing L{IConnector}.
        """
        reactor = self.buildReactor()
        connector = reactor.connectTCP("127.0.0.1", 1234, ClientFactory())
        self.assertTrue(verifyObject(IConnector, connector))


    def test_clientConnectionFailedStopsReactor(self):
        """
        The reactor can be stopped by a client factory's
        C{clientConnectionFailed} method.
        """
        host, port = self._freePort()
        reactor = self.buildReactor()
        reactor.connectTCP(host, port, Stop(reactor))
        reactor.run()


    def test_addresses(self):
        """
        A client's transport's C{getHost} and C{getPeer} return L{IPv4Address}
        instances which give the dotted-quad string form of the local and
        remote endpoints of the connection respectively.
        """
        host, port = self._freePort()
        reactor = self.buildReactor()

        serverFactory = ServerFactory()
        serverFactory.protocol = Protocol
        server = reactor.listenTCP(0, serverFactory, interface=host)
        serverAddress = server.getHost()

        addresses = {'host': None, 'peer': None}
        class CheckAddress(Protocol):
            def makeConnection(self, transport):
                addresses['host'] = transport.getHost()
                addresses['peer'] = transport.getPeer()
                reactor.stop()

        clientFactory = Stop(reactor)
        clientFactory.protocol = CheckAddress
        reactor.connectTCP(
            'localhost', server.getHost().port, clientFactory,
            bindAddress=('127.0.0.1', port))

        reactor.installResolver(FakeResolver({'localhost': '127.0.0.1'}))
        reactor.run() # self.runReactor(reactor)

        self.assertEqual(
            addresses['host'],
            IPv4Address('TCP', '127.0.0.1', port))
        self.assertEqual(
            addresses['peer'],
            IPv4Address('TCP', '127.0.0.1', serverAddress.port))


    def test_connectEvent(self):
        """
        This test checks that we correctly get notifications event for a
        client. This ought to prevent a regression under Windows using the GTK2
        reactor. See #3925.
        """
        reactor = self.buildReactor()

        serverFactory = ServerFactory()
        serverFactory.protocol = Protocol
        server = reactor.listenTCP(0, serverFactory)
        connected = []

        class CheckConnection(Protocol):
            def connectionMade(self):
                connected.append(self)
                reactor.stop()

        clientFactory = Stop(reactor)
        clientFactory.protocol = CheckConnection
        reactor.connectTCP(
            '127.0.0.1', server.getHost().port, clientFactory)

        reactor.run()

        self.assertTrue(connected)



class TCPPortTestsBuilder(ReactorBuilder):
    """
    Tests for L{IReactorRCP.listenTCP}
    """

    def getListeningPort(self, reactor):
        """
        Get a TCP port from a reactor
        """
        return reactor.listenTCP(0, ServerFactory())


    def getExpectedConnectionLostLogMsg(self, port):
        """
        Get the expected connection lost message for a TCP port
        """
        return "(TCP Port %s Closed)" % (port.getHost().port,)


    def test_connectionLostLogMsg(self):
        """
        When a connection is lost, an informative message should be logged
        (see L{getExpectedConnectionLostLogMsg}): an address identifying
        the port and the fact that it was closed.
        """

        loggedMessages = []
        def logConnectionLostMsg(eventDict):
            loggedMessages.append(log.textFromEventDict(eventDict))

        reactor = self.buildReactor()
        p = self.getListeningPort(reactor)
        expectedMessage = self.getExpectedConnectionLostLogMsg(p)
        log.addObserver(logConnectionLostMsg)

        def stopReactor(ignored):
            log.removeObserver(logConnectionLostMsg)
            reactor.stop()

        def doStopListening():
            log.addObserver(logConnectionLostMsg)
            maybeDeferred(p.stopListening).addCallback(stopReactor)

        reactor.callWhenRunning(doStopListening)
        reactor.run()

        self.assertIn(expectedMessage, loggedMessages)



globals().update(TCPClientTestsBuilder.makeTestCaseClasses())
globals().update(TCPPortTestsBuilder.makeTestCaseClasses())
