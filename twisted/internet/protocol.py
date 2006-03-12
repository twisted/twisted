# -*- test-case-name: twisted.test.test_factories -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Standard implementations of Twisted protocol-related interfaces.

Start here if you are looking to write a new protocol implementation for
Twisted.  The Protocol class contains some introductory material.

API Stability: stable, other than ClientCreator.

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

import random
from zope.interface import implements

# Twisted Imports
from twisted.python import log, failure, components
from twisted.internet import interfaces, error, defer


class Factory:
    """This is a factory which produces protocols.

    By default, buildProtocol will create a protocol of the class given in
    self.protocol.
    """

    implements(interfaces.IProtocolFactory)

    # put a subclass of Protocol here:
    protocol = None

    numPorts = 0
    noisy = True

    def doStart(self):
        """Make sure startFactory is called.

        Users should not call this function themselves!
        """
        if not self.numPorts:
            if self.noisy:
                log.msg("Starting factory %r" % self)
            self.startFactory()
        self.numPorts = self.numPorts + 1

    def doStop(self):
        """Make sure stopFactory is called.

        Users should not call this function themselves!
        """
        if self.numPorts == 0:
            # this shouldn't happen, but does sometimes and this is better
            # than blowing up in assert as we did previously.
            return
        self.numPorts = self.numPorts - 1
        if not self.numPorts:
            if self.noisy:
                log.msg("Stopping factory %r" % self)
            self.stopFactory()

    def startFactory(self):
        """This will be called before I begin listening on a Port or Connector.

        It will only be called once, even if the factory is connected
        to multiple ports.

        This can be used to perform 'unserialization' tasks that
        are best put off until things are actually running, such
        as connecting to a database, opening files, etcetera.
        """

    def stopFactory(self):
        """This will be called before I stop listening on all Ports/Connectors.

        This can be overridden to perform 'shutdown' tasks such as disconnecting
        database connections, closing files, etc.

        It will be called, for example, before an application shuts down,
        if it was connected to a port. User code should not call this function
        directly.
        """

    def buildProtocol(self, addr):
        """Create an instance of a subclass of Protocol.

        The returned instance will handle input on an incoming server
        connection, and an attribute \"factory\" pointing to the creating
        factory.

        Override this method to alter how Protocol instances get created.

        @param addr: an object implementing L{twisted.internet.interfaces.IAddress}
        """
        p = self.protocol()
        p.factory = self
        return p


class ClientFactory(Factory):
    """A Protocol factory for clients.

    This can be used together with the various connectXXX methods in
    reactors.
    """

    def startedConnecting(self, connector):
        """Called when a connection has been started.

        You can call connector.stopConnecting() to stop the connection attempt.

        @param connector: a Connector object.
        """

    def clientConnectionFailed(self, connector, reason):
        """Called when a connection has failed to connect.

        It may be useful to call connector.connect() - this will reconnect.

        @type reason: L{twisted.python.failure.Failure}
        """

    def clientConnectionLost(self, connector, reason):
        """Called when an established connection is lost.

        It may be useful to call connector.connect() - this will reconnect.

        @type reason: L{twisted.python.failure.Failure}
        """


class _InstanceFactory(ClientFactory):
    """Factory used by ClientCreator."""

    noisy = False
    
    def __init__(self, reactor, instance, deferred):
        self.reactor = reactor
        self.instance = instance
        self.deferred = deferred

    def __repr__(self):
        return "<ClientCreator factory: %r>" % (self.instance, )
    
    def buildProtocol(self, addr):
        self.reactor.callLater(0, self.deferred.callback, self.instance)
        del self.deferred
        return self.instance

    def clientConnectionFailed(self, connector, reason):
        self.reactor.callLater(0, self.deferred.errback, reason)
        del self.deferred


class ClientCreator:
    """Client connections that do not require a factory.

    The various connect* methods create a protocol instance using the given
    protocol class and arguments, and connect it, returning a Deferred of the
    resulting protocol instance.
    
    Useful for cases when we don't really need a factory.  Mainly this
    is when there is no shared state between protocol instances, and no need
    to reconnect.
    """

    def __init__(self, reactor, protocolClass, *args, **kwargs):
        self.reactor = reactor
        self.protocolClass = protocolClass
        self.args = args
        self.kwargs = kwargs

    def connectTCP(self, host, port, timeout=30, bindAddress=None):
        """Connect to remote host, return Deferred of resulting protocol instance."""
        d = defer.Deferred()
        f = _InstanceFactory(self.reactor, self.protocolClass(*self.args, **self.kwargs), d)
        self.reactor.connectTCP(host, port, f, timeout=timeout, bindAddress=bindAddress)
        return d

    def connectUNIX(self, address, timeout = 30, checkPID=0):
        """Connect to Unix socket, return Deferred of resulting protocol instance."""
        d = defer.Deferred()
        f = _InstanceFactory(self.reactor, self.protocolClass(*self.args, **self.kwargs), d)
        self.reactor.connectUNIX(address, f, timeout = timeout, checkPID=checkPID)
        return d
    
    def connectSSL(self, host, port, contextFactory, timeout=30, bindAddress=None):
        """Connect to SSL server, return Deferred of resulting protocol instance."""
        d = defer.Deferred()
        f = _InstanceFactory(self.reactor, self.protocolClass(*self.args, **self.kwargs), d)
        self.reactor.connectSSL(host, port, f, contextFactory, timeout=timeout, bindAddress=bindAddress)
        return d


class ReconnectingClientFactory(ClientFactory):
    """My clients auto-reconnect with an exponential back-off.

    Note that clients should call my resetDelay method after they have
    connected successfully.

    @ivar maxDelay: Maximum number of seconds between connection attempts.
    @ivar initialDelay: Delay for the first reconnection attempt.
    @ivar factor: a multiplicitive factor by which the delay grows
    @ivar jitter: percentage of randomness to introduce into the delay length
        to prevent stampeding.
    """
    maxDelay = 3600
    initialDelay = 1.0
    # Note: These highly sensitive factors have been precisely measured by
    # the National Institute of Science and Technology.  Take extreme care
    # in altering them, or you may damage your Internet!
    factor = 2.7182818284590451 # (math.e)
    # Phi = 1.6180339887498948 # (Phi is acceptable for use as a
    # factor if e is too large for your application.)
    jitter = 0.11962656492 # molar Planck constant times c, Jule meter/mole

    delay = initialDelay
    retries = 0
    maxRetries = None
    _callID = None
    connector = None

    continueTrying = 1

    def clientConnectionFailed(self, connector, reason):
        if self.continueTrying:
            self.connector = connector
            self.retry()

    def clientConnectionLost(self, connector, unused_reason):
        if self.continueTrying:
            self.connector = connector
            self.retry()

    def retry(self, connector=None):
        """Have this connector connect again, after a suitable delay.
        """
        if not self.continueTrying:
            if self.noisy:
                log.msg("Abandoning %s on explicit request" % (connector,))
            return

        if connector is None:
            if self.connector is None:
                raise ValueError("no connector to retry")
            else:
                connector = self.connector

        self.retries += 1
        if self.maxRetries is not None and (self.retries > self.maxRetries):
            if self.noisy:
                log.msg("Abandoning %s after %d retries." %
                        (connector, self.retries))
            return

        self.delay = min(self.delay * self.factor, self.maxDelay)
        if self.jitter:
            self.delay = random.normalvariate(self.delay,
                                              self.delay * self.jitter)

        if self.noisy:
            log.msg("%s will retry in %d seconds" % (connector, self.delay,))
        from twisted.internet import reactor

        def reconnector():
            self._callID = None
            connector.connect()
        self._callID = reactor.callLater(self.delay, reconnector)

    def stopTrying(self):
        """I put a stop to any attempt to reconnect in progress.
        """
        # ??? Is this function really stopFactory?
        if self._callID:
            self._callID.cancel()
            self._callID = None
        if self.connector:
            # Hopefully this doesn't just make clientConnectionFailed
            # retry again.
            try:
                self.connector.stopConnecting()
            except error.NotConnectingError:
                pass
        self.continueTrying = 0

    def resetDelay(self):
        """Call me after a successful connection to reset.

        I reset the delay and the retry counter.
        """
        self.delay = self.initialDelay
        self.retries = 0
        self._callID = None
        self.continueTrying = 1


class ServerFactory(Factory):
    """Subclass this to indicate that your protocol.Factory is only usable for servers.
    """


class BaseProtocol:
    """This is the abstract superclass of all protocols.

    If you are going to write a new protocol for Twisted, start here.  The
    docstrings of this class explain how you can get started.  Any protocol
    implementation, either client or server, should be a subclass of me.

    My API is quite simple.  Implement dataReceived(data) to handle both
    event-based and synchronous input; output can be sent through the
    'transport' attribute, which is to be an instance that implements
    L{twisted.internet.interfaces.ITransport}.

    Some subclasses exist already to help you write common types of protocols:
    see the L{twisted.protocols.basic} module for a few of them.
    """

    connected = 0
    transport = None

    def makeConnection(self, transport):
        """Make a connection to a transport and a server.

        This sets the 'transport' attribute of this Protocol, and calls the
        connectionMade() callback.
        """
        self.connected = 1
        self.transport = transport
        self.connectionMade()

    def connectionMade(self):
        """Called when a connection is made.

        This may be considered the initializer of the protocol, because
        it is called when the connection is completed.  For clients,
        this is called once the connection to the server has been
        established; for servers, this is called after an accept() call
        stops blocking and a socket has been received.  If you need to
        send any greeting or initial message, do it here.
        """

connectionDone=failure.Failure(error.ConnectionDone())
connectionDone.cleanFailure()


class Protocol(BaseProtocol):

    implements(interfaces.IProtocol)

    def dataReceived(self, data):
        """Called whenever data is received.

        Use this method to translate to a higher-level message.  Usually, some
        callback will be made upon the receipt of each complete protocol
        message.

        @param data: a string of indeterminate length.  Please keep in mind
            that you will probably need to buffer some data, as partial
            (or multiple) protocol messages may be received!  I recommend
            that unit tests for protocols call through to this method with
            differing chunk sizes, down to one byte at a time.
        """

    def connectionLost(self, reason=connectionDone):
        """Called when the connection is shut down.

        Clear any circular references here, and any external references
        to this Protocol.  The connection has been closed.

        @type reason: L{twisted.python.failure.Failure}
        """


class ProtocolToConsumerAdapter(components.Adapter):
    """
    This class is unstable.
    """
    implements(interfaces.IConsumer)

    def write(self, data):
        self.original.dataReceived(data)

    def registerProducer(self, producer, streaming):
        pass

    def unregisterProducer(self):
        pass

components.registerAdapter(ProtocolToConsumerAdapter, interfaces.IProtocol,
                           interfaces.IConsumer)

class ConsumerToProtocolAdapter(components.Adapter):
    """
    This class is unstable.
    """
    implements(interfaces.IProtocol)

    def dataReceived(self, data):
        self.original.write(data)

    def connectionLost(self, reason):
        pass

    def makeConnection(self, transport):
        pass

    def connectionMade(self):
        pass

components.registerAdapter(ConsumerToProtocolAdapter, interfaces.IConsumer,
                           interfaces.IProtocol)

class ProcessProtocol(BaseProtocol):
    """Processes have some additional methods besides receiving data.
    """

    def childDataReceived(self, childFD, data):
        if childFD == 1:
            self.outReceived(data)
        elif childFD == 2:
            self.errReceived(data)

    def outReceived(self, data):
        """Some data was received from stdout."""
    def errReceived(self, data):
        """Some data was received from stderr."""

    def childConnectionLost(self, childFD):
        if childFD == 0:
            self.inConnectionLost()
        elif childFD == 1:
            self.outConnectionLost()
        elif childFD == 2:
            self.errConnectionLost()

    def inConnectionLost(self):
        """This will be called when stdin is closed."""
    def outConnectionLost(self):
        """This will be called when stdout is closed."""
    def errConnectionLost(self):
        """This will be called when stderr is closed."""

    def processEnded(self, reason):
        """This will be called when the subprocess is finished.

        @type reason: L{twisted.python.failure.Failure}
        """


class AbstractDatagramProtocol:
    """Abstract protocol for datagram-oriented transports, e.g. IP, ICMP, ARP, UDP."""

    transport = None
    numPorts = 0
    noisy = True

    def __getstate__(self):
        d = self.__dict__.copy()
        d['transport'] = None
        return d

    def doStart(self):
        """Make sure startProtocol is called.

        This will be called by makeConnection(), users should not call it.
        """
        if not self.numPorts:
            if self.noisy:
                log.msg("Starting protocol %s" % self)
            self.startProtocol()
        self.numPorts = self.numPorts + 1

    def doStop(self):
        """Make sure stopProtocol is called.

        This will be called by the port, users should not call it.
        """
        assert self.numPorts > 0
        self.numPorts = self.numPorts - 1
        self.transport = None
        if not self.numPorts:
            if self.noisy:
                log.msg("Stopping protocol %s" % self)
            self.stopProtocol()

    def startProtocol(self):
        """Called when a transport is connected to this protocol.

        Will only be called once, even if multiple ports are connected.
        """

    def stopProtocol(self):
        """Called when the transport is disconnected.

        Will only be called once, after all ports are disconnected.
        """

    def makeConnection(self, transport):
        """Make a connection to a transport and a server.

        This sets the 'transport' attribute of this DatagramProtocol, and calls the
        doStart() callback.
        """
        assert self.transport == None
        self.transport = transport
        self.doStart()

    def datagramReceived(self, datagram, addr):
        """Called when a datagram is received.

        @param datagram: the string received from the transport.
        @param addr: tuple of source of datagram.
        """


class DatagramProtocol(AbstractDatagramProtocol):
    """Protocol for datagram-oriented transport, e.g. UDP."""

    def connectionRefused(self):
        """Called due to error from write in connected mode.

        Note this is a result of ICMP message generated by *previous*
        write.
        """


class ConnectedDatagramProtocol(DatagramProtocol):
    """Protocol for connected datagram-oriented transport.

    No longer necessary for UDP.
    """

    def datagramReceived(self, datagram):
        """Called when a datagram is received.

        @param datagram: the string received from the transport.
        """

    def connectionFailed(self, failure):
        """Called if connecting failed.

        Usually this will be due to a DNS lookup failure.
        """



class FileWrapper:
    """A wrapper around a file-like object to make it behave as a Transport.

    This doesn't actually stream the file to the attached protocol,
    and is thus useful mainly as a utility for debugging protocols.
    """

    implements(interfaces.ITransport)

    closed = 0
    disconnecting = 0
    producer = None
    streamingProducer = 0

    def __init__(self, file):
        self.file = file

    def write(self, data):
        try:
            self.file.write(data)
        except:
            self.handleException()
        # self._checkProducer()

    def _checkProducer(self):
        # Cheating; this is called at "idle" times to allow producers to be
        # found and dealt with
        if self.producer:
            self.producer.resumeProducing()

    def registerProducer(self, producer, streaming):
        """From abstract.FileDescriptor
        """
        self.producer = producer
        self.streamingProducer = streaming
        if not streaming:
            producer.resumeProducing()

    def unregisterProducer(self):
        self.producer = None

    def stopConsuming(self):
        self.unregisterProducer()
        self.loseConnection()

    def writeSequence(self, iovec):
        self.write("".join(iovec))

    def loseConnection(self):
        self.closed = 1
        try:
            self.file.close()
        except (IOError, OSError):
            self.handleException()

    def getPeer(self):
        # XXX: According to ITransport, this should return an IAddress!
        return 'file', 'file'

    def getHost(self):
        # XXX: According to ITransport, this should return an IAddress!
        return 'file'

    def handleException(self):
        pass

    def resumeProducing(self):
        # Never sends data anyways
        pass

    def pauseProducing(self):
        # Never sends data anyways
        pass
    
    def stopProducing(self):
        self.loseConnection()
        

__all__ = ["Factory", "ClientFactory", "ReconnectingClientFactory", "connectionDone", 
           "Protocol", "ProcessProtocol", "FileWrapper", "ServerFactory",
           "AbstractDatagramProtocol", "DatagramProtocol", "ConnectedDatagramProtocol",
           "ClientCreator"]
