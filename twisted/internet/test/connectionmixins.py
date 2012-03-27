# -*- test-case-name: twisted.internet.test.test_tcp -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Various helpers for tests for connection-oriented transports.
"""

import socket

from gc import collect
from weakref import ref

from zope.interface import implements
from zope.interface.verify import verifyObject

from twisted.python import context, log
from twisted.python.failure import Failure
from twisted.python.reflect import fullyQualifiedName
from twisted.python.runtime import platform
from twisted.python.log import ILogContext, msg, err
from twisted.internet.defer import Deferred, gatherResults, succeed, fail
from twisted.internet.interfaces import (
    IConnector, IResolverSimple, IReactorFDSet)
from twisted.internet.protocol import ClientFactory, Protocol, ServerFactory
from twisted.test.test_tcp import ClosingProtocol
from twisted.trial.unittest import SkipTest
from twisted.internet.error import DNSLookupError
from twisted.internet.interfaces import ITLSTransport

def needsRunningReactor(reactor, thunk):
    """
    Various functions within these tests need an already-running reactor at
    some point.  They need to stop the reactor when the test has completed, and
    that means calling reactor.stop().  However, reactor.stop() raises an
    exception if the reactor isn't already running, so if the L{Deferred} that
    a particular API under test returns fires synchronously (as especially an
    endpoint's C{connect()} method may do, if the connect is to a local
    interface address) then the test won't be able to stop the reactor being
    tested and finish.  So this calls C{thunk} only once C{reactor} is running.

    (This is just an alias for
    L{twisted.internet.interfaces.IReactorCore.callWhenRunning} on the given
    reactor parameter, in order to centrally reference the above paragraph and
    repeating it everywhere as a comment.)

    @param reactor: the L{twisted.internet.interfaces.IReactorCore} under test

    @param thunk: a 0-argument callable, which eventually finishes the test in
        question, probably in a L{Deferred} callback.
    """
    reactor.callWhenRunning(thunk)



def serverFactoryFor(protocol):
    """
    Helper function which returns a L{ServerFactory} which will build instances
    of C{protocol}.

    @param protocol: A callable which returns an L{IProtocol} provider to be
        used to handle connections to the port the returned factory listens on.
    """
    factory = ServerFactory()
    factory.protocol = protocol
    return factory

# ServerFactory is good enough for client endpoints, too.
factoryFor = serverFactoryFor



def findFreePort(interface='127.0.0.1', family=socket.AF_INET,
                 type=socket.SOCK_STREAM):
    """
    Ask the platform to allocate a free port on the specified interface, then
    release the socket and return the address which was allocated.

    @param interface: The local address to try to bind the port on.
    @type interface: C{str}

    @param type: The socket type which will use the resulting port.

    @return: A two-tuple of address and port, like that returned by
        L{socket.getsockname}.
    """
    addr = socket.getaddrinfo(interface, 0)[0][4]
    probe = socket.socket(family, type)
    try:
        probe.bind(addr)
        return probe.getsockname()
    finally:
        probe.close()



def _getWriters(reactor):
    """
    Like L{IReactorFDSet.getWriters}, but with support for IOCP reactor as
    well.
    """
    if IReactorFDSet.providedBy(reactor):
        return reactor.getWriters()
    elif 'IOCP' in reactor.__class__.__name__:
        return reactor.handles
    else:
        # Cannot tell what is going on.
        raise Exception("Cannot find writers on %r" % (reactor,))



class _AcceptOneClient(ServerFactory):
    """
    This factory fires a L{Deferred} with a protocol instance shortly after it
    is constructed (hopefully long enough afterwards so that it has been
    connected to a transport).

    @ivar reactor: The reactor used to schedule the I{shortly}.

    @ivar result: A L{Deferred} which will be fired with the protocol instance.
    """
    def __init__(self, reactor, result):
        self.reactor = reactor
        self.result = result


    def buildProtocol(self, addr):
        protocol = ServerFactory.buildProtocol(self, addr)
        self.reactor.callLater(0, self.result.callback, protocol)
        return protocol



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



class Stop(ClientFactory):
    """
    A client factory which stops a reactor when a connection attempt fails.
    """
    failReason = None

    def __init__(self, reactor):
        self.reactor = reactor


    def clientConnectionFailed(self, connector, reason):
        self.failReason = reason
        msg("Stop(CF) cCFailed: %s" % (reason.getErrorMessage(),))
        self.reactor.stop()



class FakeResolver(object):
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



class ClosingLaterProtocol(Protocol):
    """
    ClosingLaterProtocol exchanges one byte with its peer and then disconnects
    itself.  This is mostly a work-around for the fact that connectionMade is
    called before the SSL handshake has completed.
    """
    def __init__(self, onConnectionLost):
        self.lostConnectionReason = None
        self.onConnectionLost = onConnectionLost


    def connectionMade(self):
        msg("ClosingLaterProtocol.connectionMade")


    def dataReceived(self, bytes):
        msg("ClosingLaterProtocol.dataReceived %r" % (bytes,))
        self.transport.loseConnection()


    def connectionLost(self, reason):
        msg("ClosingLaterProtocol.connectionLost")
        self.lostConnectionReason = reason
        self.onConnectionLost.callback(self)



class ConnectionTestsMixin(object):
    """
    This mixin defines test methods which should apply to most L{ITransport}
    implementations.
    """

    def serverEndpoint(self, reactor):
        """
        Return an object providing L{IStreamServerEndpoint} for use in creating
        a server to use to establish the connection type to be tested.
        """
        raise NotImplementedError("%s.serverEndpoint() not implemented" %
                                  (fullyQualifiedName(self.__class__),))


    def clientEndpoint(self, reactor, serverAddress):
        """
        Return an object providing L{IStreamClientEndpoint} for use in creating
        a client to use to establish the connection type to be tested.
        """
        raise NotImplementedError("%s.clientEndpoint() not implemented" %
                                  (fullyQualifiedName(self.__class__),))


    def loopback(self, reactor, clientProtocol, serverProtocol):
        """
        Create a loopback connection of the type to be tested, using
        C{clientProtocol} and C{serverProtocol} to handle each end of the
        connection.

        @return: A L{Deferred} which fires when the connection is established.
            The result is a two-tuple of the client protocol instance and
            server protocol instance.
        """
        accepted = Deferred()
        factory = _AcceptOneClient(reactor, accepted)
        factory.protocol = serverProtocol
        server = self.serverEndpoint(reactor)
        listening = server.listen(factory)
        def startedListening(port):
            address = port.getHost()
            client = self.clientEndpoint(reactor, address)
            return gatherResults([client.connect(factoryFor(clientProtocol)),
                                  accepted])
        listening.addCallback(startedListening)
        return listening


    def test_logPrefix(self):
        """
        Client and server transports implement L{ILoggingContext.logPrefix} to
        return a message reflecting the protocol they are running.
        """
        class CustomLogPrefixProtocol(Protocol):
            def __init__(self, prefix):
                self._prefix = prefix
                self.system = Deferred()

            def logPrefix(self):
                return self._prefix

            def dataReceived(self, bytes):
                self.system.callback(context.get(ILogContext)["system"])

        reactor = self.buildReactor()
        d = self.loopback(
            reactor,
            lambda: CustomLogPrefixProtocol("Custom Client"),
            lambda: CustomLogPrefixProtocol("Custom Server"))
        def connected((client, server)):
            client.transport.write("foo")
            server.transport.write("bar")
            return gatherResults([client.system, server.system])

        def gotSystem((client, server)):
            self.assertIn("Custom Client", client)
            self.assertIn("Custom Server", server)

        def withLoopback():
            d.addCallback(connected)
            d.addCallback(gotSystem)
            d.addErrback(err)
            d.addBoth(lambda ignored: reactor.stop())
        needsRunningReactor(reactor, withLoopback)

        self.runReactor(reactor)


    def test_writeAfterDisconnect(self):
        """
        After a connection is disconnected, L{ITransport.write} and
        L{ITransport.writeSequence} are no-ops.
        """
        reactor = self.buildReactor()

        finished = []

        serverConnectionLostDeferred = Deferred()
        protocol = lambda: ClosingLaterProtocol(serverConnectionLostDeferred)
        portDeferred = self.serverEndpoint(reactor).listen(
            serverFactoryFor(protocol))
        def listening(port):
            msg("Listening on %r" % (port.getHost(),))
            endpoint = self.clientEndpoint(reactor, port.getHost())

            lostConnectionDeferred = Deferred()
            protocol = lambda: ClosingLaterProtocol(lostConnectionDeferred)
            client = endpoint.connect(factoryFor(protocol))
            def write(proto):
                msg("About to write to %r" % (proto,))
                proto.transport.write('x')
            client.addCallbacks(write, lostConnectionDeferred.errback)

            def disconnected(proto):
                msg("%r disconnected" % (proto,))
                proto.transport.write("some bytes to get lost")
                proto.transport.writeSequence(["some", "more"])
                finished.append(True)

            lostConnectionDeferred.addCallback(disconnected)
            serverConnectionLostDeferred.addCallback(disconnected)
            return gatherResults([
                    lostConnectionDeferred,
                    serverConnectionLostDeferred])

        def onListen():
            portDeferred.addCallback(listening)
            portDeferred.addErrback(err)
            portDeferred.addCallback(lambda ignored: reactor.stop())
        needsRunningReactor(reactor, onListen)

        self.runReactor(reactor)
        self.assertEqual(finished, [True, True])


    def test_protocolGarbageAfterLostConnection(self):
        """
        After the connection a protocol is being used for is closed, the
        reactor discards all of its references to the protocol.
        """
        lostConnectionDeferred = Deferred()
        clientProtocol = ClosingLaterProtocol(lostConnectionDeferred)
        clientRef = ref(clientProtocol)

        reactor = self.buildReactor()
        portDeferred = self.serverEndpoint(reactor).listen(
            serverFactoryFor(Protocol))
        def listening(port):
            msg("Listening on %r" % (port.getHost(),))
            endpoint = self.clientEndpoint(reactor, port.getHost())

            client = endpoint.connect(factoryFor(lambda: clientProtocol))
            def disconnect(proto):
                msg("About to disconnect %r" % (proto,))
                proto.transport.loseConnection()
            client.addCallback(disconnect)
            client.addErrback(lostConnectionDeferred.errback)
            return lostConnectionDeferred

        def onListening():
            portDeferred.addCallback(listening)
            portDeferred.addErrback(err)
            portDeferred.addBoth(lambda ignored: reactor.stop())
        needsRunningReactor(reactor, onListening)

        self.runReactor(reactor)

        # Drop the reference and get the garbage collector to tell us if there
        # are no references to the protocol instance left in the reactor.
        clientProtocol = None
        collect()
        self.assertIdentical(None, clientRef())



class LogObserverMixin(object):
    """
    Mixin for L{TestCase} subclasses which want to observe log events.
    """
    def observe(self):
        loggedMessages = []
        log.addObserver(loggedMessages.append)
        self.addCleanup(log.removeObserver, loggedMessages.append)
        return loggedMessages



class BrokenContextFactory(object):
    """
    A context factory with a broken C{getContext} method, for exercising the
    error handling for such a case.
    """
    message = "Some path was wrong maybe"

    def getContext(self):
        raise ValueError(self.message)



class TCPClientTestsMixin(object):
    """
    This mixin defines tests applicable to TCP client implementations.  Classes
    which mix this in must provide all of the documented instance variables in
    order to specify how the test works.  These are documented as instance
    variables rather than declared as methods due to some peculiar inheritance
    ordering concerns, but they are effectively abstract methods.

    This must be mixed in to a L{ReactorBuilder
    <twisted.internet.test.reactormixins.ReactorBuilder>} subclass, as it
    depends on several of its methods.

    @ivar interface: An IP address literal to locally bind a socket to as well
        as to connect to.  This can be any valid interface for the local host.
    @type interface: C{str}

    @ivar port: An unused local listening port to listen on and connect to.
        This will be used in conjunction with the C{interface}.  (Depending on
        what they're testing, some tests will locate their own port with
        L{findFreePort} instead.)
    @type port: C{int}

    @ivar family: an address family constant, such as L{socket.AF_INET},
        L{socket.AF_INET6}, or L{socket.AF_UNIX}, which indicates the address
        family of the transport type under test.
    @type family: C{int}

    @ivar addressClass: the L{twisted.internet.interfaces.IAddress} implementor
        associated with the transport type under test.  Must also be a
        3-argument callable which produces an instance of same.
    @type addressClass: C{type}

    @ivar fakeDomainName: A fake domain name to use, to simulate hostname
        resolution and to distinguish between hostnames and IP addresses where
        necessary.
    @type fakeDomainName: C{str}
    """

    def test_interface(self):
        """
        L{IReactorTCP.connectTCP} returns an object providing L{IConnector}.
        """
        reactor = self.buildReactor()
        connector = reactor.connectTCP(self.interface, self.port,
                                       ClientFactory())
        self.assertTrue(verifyObject(IConnector, connector))


    def test_clientConnectionFailedStopsReactor(self):
        """
        The reactor can be stopped by a client factory's
        C{clientConnectionFailed} method.
        """
        host, port = findFreePort(self.interface, self.family)[:2]
        reactor = self.buildReactor()
        needsRunningReactor(
            reactor, lambda: reactor.connectTCP(host, port, Stop(reactor)))
        self.runReactor(reactor)


    def test_addresses(self):
        """
        A client's transport's C{getHost} and C{getPeer} return L{IPv4Address}
        instances which have the dotted-quad string form of the resolved
        adddress of the local and remote endpoints of the connection
        respectively as their C{host} attribute, not the hostname originally
        passed in to L{connectTCP
        <twisted.internet.interfaces.IReactorTCP.connectTCP>}, if a hostname
        was used.
        """
        host, port = findFreePort(self.interface, self.family)[:2]
        reactor = self.buildReactor()
        fakeDomain = self.fakeDomainName
        reactor.installResolver(FakeResolver({fakeDomain: self.interface}))

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

        def connectMe():
            reactor.connectTCP(
                fakeDomain, server.getHost().port, clientFactory,
                bindAddress=(self.interface, port))
        needsRunningReactor(reactor, connectMe)

        self.runReactor(reactor)

        if clientFactory.failReason:
            self.fail(clientFactory.failReason.getTraceback())

        self.assertEqual(
            addresses['host'],
            self.addressClass('TCP', self.interface, port))
        self.assertEqual(
            addresses['peer'],
            self.addressClass('TCP', self.interface, serverAddress.port))


    def test_connectEvent(self):
        """
        This test checks that we correctly get notifications event for a
        client.  This ought to prevent a regression under Windows using the
        GTK2 reactor.  See #3925.
        """
        reactor = self.buildReactor()

        server = reactor.listenTCP(0, serverFactoryFor(Protocol),
                                   interface=self.interface)
        connected = []

        class CheckConnection(Protocol):
            def connectionMade(self):
                connected.append(self)
                reactor.stop()

        clientFactory = Stop(reactor)
        clientFactory.protocol = CheckConnection

        needsRunningReactor(reactor, lambda: reactor.connectTCP(
            self.interface, server.getHost().port, clientFactory))

        reactor.run()

        self.assertTrue(connected)


    def test_unregisterProducerAfterDisconnect(self):
        """
        If a producer is unregistered from a L{ITCPTransport} provider after
        the transport has been disconnected (by the peer) and after
        L{ITCPTransport.loseConnection} has been called, the transport is not
        re-added to the reactor as a writer as would be necessary if the
        transport were still connected.
        """
        reactor = self.buildReactor()
        port = reactor.listenTCP(0, serverFactoryFor(ClosingProtocol),
                                 interface=self.interface)

        finished = Deferred()
        finished.addErrback(log.err)
        finished.addCallback(lambda ign: reactor.stop())

        writing = []

        class ClientProtocol(Protocol):
            """
            Protocol to connect, register a producer, try to lose the
            connection, wait for the server to disconnect from us, and then
            unregister the producer.
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
        reactor.connectTCP(self.interface, port.getHost().port, clientFactory)
        self.runReactor(reactor)
        self.assertFalse(writing[0],
                         "Transport was writing after unregisterProducer.")


    def test_disconnectWhileProducing(self):
        """
        If L{ITCPTransport.loseConnection} is called while a producer is
        registered with the transport, the connection is closed after the
        producer is unregistered.
        """
        reactor = self.buildReactor()

        # For some reason, pyobject/pygtk will not deliver the close
        # notification that should happen after the unregisterProducer call in
        # this test.  The selectable is in the write notification set, but no
        # notification ever arrives.  Probably for the same reason #5233 led
        # win32eventreactor to be broken.
        skippedReactors = ["Glib2Reactor", "Gtk2Reactor"]
        reactorClassName = reactor.__class__.__name__
        if reactorClassName in skippedReactors and platform.isWindows():
            raise SkipTest(
                "A pygobject/pygtk bug disables this functionality on Windows.")

        class Producer:
            def resumeProducing(self):
                log.msg("Producer.resumeProducing")

        port = reactor.listenTCP(0, serverFactoryFor(Protocol),
            interface=self.interface)

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
        reactor.connectTCP(self.interface, port.getHost().port, clientFactory)
        self.runReactor(reactor)
        # If the test failed, we logged an error already and trial
        # will catch it.


    def test_badContext(self):
        """
        If the context factory passed to L{ITCPTransport.startTLS} raises an
        exception from its C{getContext} method, that exception is raised by
        L{ITCPTransport.startTLS}.
        """
        reactor = self.buildReactor()

        brokenFactory = BrokenContextFactory()
        results = []

        serverFactory = ServerFactory()
        serverFactory.protocol = Protocol

        port = reactor.listenTCP(0, serverFactory, interface=self.interface)
        endpoint = self.clientEndpoint(reactor, port.getHost())

        clientFactory = ClientFactory()
        clientFactory.protocol = Protocol
        connectDeferred = endpoint.connect(clientFactory)

        def connected(protocol):
            if not ITLSTransport.providedBy(protocol.transport):
                results.append("skip")
            else:
                results.append(self.assertRaises(ValueError,
                                                 protocol.transport.startTLS,
                                                 brokenFactory))

        def connectFailed(failure):
            results.append(failure)

        def whenRun():
            connectDeferred.addCallback(connected)
            connectDeferred.addErrback(connectFailed)
            connectDeferred.addBoth(lambda ign: reactor.stop())
        needsRunningReactor(reactor, whenRun)

        self.runReactor(reactor)

        self.assertEqual(len(results), 1,
                         "more than one callback result: %s" % (results,))

        if isinstance(results[0], Failure):
            # self.fail(Failure)
            results[0].raiseException()
        if results[0] == "skip":
            raise SkipTest("Reactor does not support ITLSTransport")
        self.assertEqual(BrokenContextFactory.message, str(results[0]))
