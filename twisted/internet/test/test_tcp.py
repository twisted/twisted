# Copyright (c) Twisted Matrix Laboratories.
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
from twisted.internet.interfaces import (
    IResolverSimple, IConnector, IReactorFDSet)
from twisted.internet.address import IPv4Address
from twisted.internet.defer import Deferred, succeed, fail, maybeDeferred
from twisted.internet.protocol import ServerFactory, ClientFactory, Protocol
from twisted.python.runtime import platform
from twisted.python.failure import Failure
from twisted.python import log
from twisted.trial.unittest import SkipTest

from twisted.test.test_tcp import ClosingProtocol
from twisted.internet.test.test_core import ObjectModelIntegrationMixin


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



class _SimplePullProducer(object):
    """
    A pull producer which writes one byte whenever it is resumed.  For use by
    L{test_unregisterProducerAfterDisconnect}.
    """
    def __init__(self, consumer):
        self.consumer = consumer


    def stopProducing(self):
        pass


    def resumeProducing(self):
        log.msg("Producer.resumeProducing")
        self.consumer.write('x')



def _getWriters(reactor):
    """
    Like L{IReactorFDSet.getWriters}, but with support for IOCP reactor as well.
    """
    if IReactorFDSet.providedBy(reactor):
        return reactor.getWriters()
    elif 'IOCP' in reactor.__class__.__name__:
        return reactor.handles
    else:
        # Cannot tell what is going on.
        raise Exception("Cannot find writers on %r" % (reactor,))



def serverFactoryFor(protocol):
    """
    Helper function which provides the signature L{ServerFactory} should
    provide.
    """
    factory = ServerFactory()
    factory.protocol = protocol
    return factory



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

        server = reactor.listenTCP(
            0, serverFactoryFor(Protocol), interface=host)
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

        server = reactor.listenTCP(0, serverFactoryFor(Protocol))
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


    def test_unregisterProducerAfterDisconnect(self):
        """
        If a producer is unregistered from a L{ITCPTransport} provider after the
        transport has been disconnected (by the peer) and after
        L{ITCPTransport.loseConnection} has been called, the transport is not
        re-added to the reactor as a writer as would be necessary if the
        transport were still connected.
        """
        reactor = self.buildReactor()
        port = reactor.listenTCP(0, serverFactoryFor(ClosingProtocol))

        finished = Deferred()
        finished.addErrback(log.err)
        finished.addCallback(lambda ign: reactor.stop())

        writing = []

        class ClientProtocol(Protocol):
            """
            Protocol to connect, register a producer, try to lose the
            connection, wait for the server to disconnect from us, and
            then unregister the producer.
            """
            def connectionMade(self):
                log.msg("ClientProtocol.connectionMade")
                self.transport.registerProducer(
                    _SimplePullProducer(self.transport), False)
                self.transport.loseConnection()

            def connectionLost(self, reason):
                log.msg("ClientProtocol.connectionLost")
                self.unregister()
                writing.append(self.transport in _getWriters(reactor))
                finished.callback(None)

            def unregister(self):
                log.msg("ClientProtocol unregister")
                self.transport.unregisterProducer()

        clientFactory = ClientFactory()
        clientFactory.protocol = ClientProtocol
        reactor.connectTCP('127.0.0.1', port.getHost().port, clientFactory)
        self.runReactor(reactor)
        self.assertFalse(
            writing[0], "Transport was writing after unregisterProducer.")


    def test_disconnectWhileProducing(self):
        """
        If L{ITCPTransport.loseConnection} is called while a producer
        is registered with the transport, the connection is closed
        after the producer is unregistered.
        """
        reactor = self.buildReactor()

        # XXX For some reason, pyobject/pygtk will not deliver the close
        # notification that should happen after the unregisterProducer call in
        # this test.  The selectable is in the write notification set, but no
        # notification ever arrives.
        skippedReactors = ["Glib2Reactor", "Gtk2Reactor"]
        reactorClassName = reactor.__class__.__name__
        if reactorClassName in skippedReactors and platform.isWindows():
            raise SkipTest(
                "A pygobject/pygtk bug disables this functionality on Windows.")

        class Producer:
            def resumeProducing(self):
                log.msg("Producer.resumeProducing")

        port = reactor.listenTCP(0, serverFactoryFor(Protocol))

        finished = Deferred()
        finished.addErrback(log.err)
        finished.addCallback(lambda ign: reactor.stop())

        class ClientProtocol(Protocol):
            """
            Protocol to connect, register a producer, try to lose the
            connection, unregister the producer, and wait for the connection to
            actually be lost.
            """
            def connectionMade(self):
                log.msg("ClientProtocol.connectionMade")
                self.transport.registerProducer(Producer(), False)
                self.transport.loseConnection()
                # Let the reactor tick over, in case synchronously calling
                # loseConnection and then unregisterProducer is the same as
                # synchronously calling unregisterProducer and then
                # loseConnection (as it is in several reactors).
                reactor.callLater(0, reactor.callLater, 0, self.unregister)

            def unregister(self):
                log.msg("ClientProtocol unregister")
                self.transport.unregisterProducer()
                # This should all be pretty quick.  Fail the test
                # if we don't get a connectionLost event really
                # soon.
                reactor.callLater(
                    1.0, finished.errback,
                    Failure(Exception("Connection was not lost")))

            def connectionLost(self, reason):
                log.msg("ClientProtocol.connectionLost")
                finished.callback(None)

        clientFactory = ClientFactory()
        clientFactory.protocol = ClientProtocol
        reactor.connectTCP('127.0.0.1', port.getHost().port, clientFactory)
        self.runReactor(reactor)
        # If the test failed, we logged an error already and trial
        # will catch it.



class TCPPortTestsBuilder(ReactorBuilder, ObjectModelIntegrationMixin):
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


    def test_allNewStyle(self):
        """
        The L{IListeningPort} object is an instance of a class with no
        classic classes in its hierarchy.
        """
        reactor = self.buildReactor()
        port = self.getListeningPort(reactor)
        self.assertFullyNewStyle(port)



globals().update(TCPClientTestsBuilder.makeTestCaseClasses())
globals().update(TCPPortTestsBuilder.makeTestCaseClasses())
