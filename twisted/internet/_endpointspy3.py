# -*- test-case-name: twisted.internet.test.test_endpointspy3 -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Implementations of endpoints that have been ported to Python 3.
"""

from __future__ import division, absolute_import

import socket

from zope.interface import implementer, directlyProvides

from twisted.internet import interfaces, defer, error, threads
from twisted.internet.protocol import ClientFactory, Protocol
from twisted.internet.abstract import isIPv6Address

class _WrappingProtocol(Protocol):
    """
    Wrap another protocol in order to notify my user when a connection has
    been made.
    """

    def __init__(self, connectedDeferred, wrappedProtocol):
        """
        @param connectedDeferred: The L{Deferred} that will callback
            with the C{wrappedProtocol} when it is connected.

        @param wrappedProtocol: An L{IProtocol} provider that will be
            connected.
        """
        self._connectedDeferred = connectedDeferred
        self._wrappedProtocol = wrappedProtocol

        for iface in [interfaces.IHalfCloseableProtocol,
                      interfaces.IFileDescriptorReceiver]:
            if iface.providedBy(self._wrappedProtocol):
                directlyProvides(self, iface)


    def logPrefix(self):
        """
        Transparently pass through the wrapped protocol's log prefix.
        """
        if interfaces.ILoggingContext.providedBy(self._wrappedProtocol):
            return self._wrappedProtocol.logPrefix()
        return self._wrappedProtocol.__class__.__name__


    def connectionMade(self):
        """
        Connect the C{self._wrappedProtocol} to our C{self.transport} and
        callback C{self._connectedDeferred} with the C{self._wrappedProtocol}
        """
        self._wrappedProtocol.makeConnection(self.transport)
        self._connectedDeferred.callback(self._wrappedProtocol)


    def dataReceived(self, data):
        """
        Proxy C{dataReceived} calls to our C{self._wrappedProtocol}
        """
        return self._wrappedProtocol.dataReceived(data)


    def fileDescriptorReceived(self, descriptor):
        """
        Proxy C{fileDescriptorReceived} calls to our C{self._wrappedProtocol}
        """
        return self._wrappedProtocol.fileDescriptorReceived(descriptor)


    def connectionLost(self, reason):
        """
        Proxy C{connectionLost} calls to our C{self._wrappedProtocol}
        """
        return self._wrappedProtocol.connectionLost(reason)


    def readConnectionLost(self):
        """
        Proxy L{IHalfCloseableProtocol.readConnectionLost} to our
        C{self._wrappedProtocol}
        """
        self._wrappedProtocol.readConnectionLost()


    def writeConnectionLost(self):
        """
        Proxy L{IHalfCloseableProtocol.writeConnectionLost} to our
        C{self._wrappedProtocol}
        """
        self._wrappedProtocol.writeConnectionLost()



class _WrappingFactory(ClientFactory):
    """
    Wrap a factory in order to wrap the protocols it builds.

    @ivar _wrappedFactory: A provider of I{IProtocolFactory} whose buildProtocol
        method will be called and whose resulting protocol will be wrapped.

    @ivar _onConnection: A L{Deferred} that fires when the protocol is
        connected

    @ivar _connector: A L{connector <twisted.internet.interfaces.IConnector>}
        that is managing the current or previous connection attempt.
    """
    protocol = _WrappingProtocol

    def __init__(self, wrappedFactory):
        """
        @param wrappedFactory: A provider of I{IProtocolFactory} whose
            buildProtocol method will be called and whose resulting protocol
            will be wrapped.
        """
        self._wrappedFactory = wrappedFactory
        self._onConnection = defer.Deferred(canceller=self._canceller)


    def startedConnecting(self, connector):
        """
        A connection attempt was started.  Remember the connector which started
        said attempt, for use later.
        """
        self._connector = connector


    def _canceller(self, deferred):
        """
        The outgoing connection attempt was cancelled.  Fail that L{Deferred}
        with an L{error.ConnectingCancelledError}.

        @param deferred: The L{Deferred <defer.Deferred>} that was cancelled;
            should be the same as C{self._onConnection}.
        @type deferred: L{Deferred <defer.Deferred>}

        @note: This relies on startedConnecting having been called, so it may
            seem as though there's a race condition where C{_connector} may not
            have been set.  However, using public APIs, this condition is
            impossible to catch, because a connection API
            (C{connectTCP}/C{SSL}/C{UNIX}) is always invoked before a
            L{_WrappingFactory}'s L{Deferred <defer.Deferred>} is returned to
            C{connect()}'s caller.

        @return: C{None}
        """
        deferred.errback(
            error.ConnectingCancelledError(
                self._connector.getDestination()))
        self._connector.stopConnecting()


    def doStart(self):
        """
        Start notifications are passed straight through to the wrapped factory.
        """
        self._wrappedFactory.doStart()


    def doStop(self):
        """
        Stop notifications are passed straight through to the wrapped factory.
        """
        self._wrappedFactory.doStop()


    def buildProtocol(self, addr):
        """
        Proxy C{buildProtocol} to our C{self._wrappedFactory} or errback
        the C{self._onConnection} L{Deferred}.

        @return: An instance of L{_WrappingProtocol} or C{None}
        """
        try:
            proto = self._wrappedFactory.buildProtocol(addr)
        except:
            self._onConnection.errback()
        else:
            return self.protocol(self._onConnection, proto)


    def clientConnectionFailed(self, connector, reason):
        """
        Errback the C{self._onConnection} L{Deferred} when the
        client connection fails.
        """
        if not self._onConnection.called:
            self._onConnection.errback(reason)



@implementer(interfaces.IStreamServerEndpoint)
class _TCPServerEndpoint(object):
    """
    A TCP server endpoint interface
    """

    def __init__(self, reactor, port, backlog, interface):
        """
        @param reactor: An L{IReactorTCP} provider.

        @param port: The port number used for listening
        @type port: int

        @param backlog: Size of the listen queue
        @type backlog: int

        @param interface: The hostname to bind to
        @type interface: str
        """
        self._reactor = reactor
        self._port = port
        self._backlog = backlog
        self._interface = interface


    def listen(self, protocolFactory):
        """
        Implement L{IStreamServerEndpoint.listen} to listen on a TCP socket
        """
        return defer.execute(self._reactor.listenTCP,
                             self._port,
                             protocolFactory,
                             backlog=self._backlog,
                             interface=self._interface)



class TCP4ServerEndpoint(_TCPServerEndpoint):
    """
    Implements TCP server endpoint with an IPv4 configuration
    """
    def __init__(self, reactor, port, backlog=50, interface=''):
        """
        @param reactor: An L{IReactorTCP} provider.

        @param port: The port number used for listening
        @type port: int

        @param backlog: Size of the listen queue
        @type backlog: int

        @param interface: The hostname to bind to, defaults to '' (all)
        @type interface: str
        """
        _TCPServerEndpoint.__init__(self, reactor, port, backlog, interface)



class TCP6ServerEndpoint(_TCPServerEndpoint):
    """
    Implements TCP server endpoint with an IPv6 configuration
    """
    def __init__(self, reactor, port, backlog=50, interface='::'):
        """
        @param reactor: An L{IReactorTCP} provider.

        @param port: The port number used for listening
        @type port: int

        @param backlog: Size of the listen queue
        @type backlog: int

        @param interface: The hostname to bind to, defaults to '' (all)
        @type interface: str
        """
        _TCPServerEndpoint.__init__(self, reactor, port, backlog, interface)



@implementer(interfaces.IStreamClientEndpoint)
class TCP4ClientEndpoint(object):
    """
    TCP client endpoint with an IPv4 configuration.
    """

    def __init__(self, reactor, host, port, timeout=30, bindAddress=None):
        """
        @param reactor: An L{IReactorTCP} provider

        @param host: A hostname, used when connecting
        @type host: str

        @param port: The port number, used when connecting
        @type port: int

        @param timeout: The number of seconds to wait before assuming the
            connection has failed.
        @type timeout: int

        @param bindAddress: A (host, port) tuple of local address to bind to,
            or None.
        @type bindAddress: tuple
        """
        self._reactor = reactor
        self._host = host
        self._port = port
        self._timeout = timeout
        self._bindAddress = bindAddress


    def connect(self, protocolFactory):
        """
        Implement L{IStreamClientEndpoint.connect} to connect via TCP.
        """
        try:
            wf = _WrappingFactory(protocolFactory)
            self._reactor.connectTCP(
                self._host, self._port, wf,
                timeout=self._timeout, bindAddress=self._bindAddress)
            return wf._onConnection
        except:
            return defer.fail()



@implementer(interfaces.IStreamClientEndpoint)
class TCP6ClientEndpoint(object):
    """
    TCP client endpoint with an IPv6 configuration.

    @ivar _getaddrinfo: A hook used for testing name resolution.

    @ivar _deferToThread: A hook used for testing deferToThread.

    @ivar _GAI_ADDRESS: Index of the address portion in result of
        getaddrinfo to be used.

    @ivar _GAI_ADDRESS_HOST: Index of the actual host-address in the
        5-tuple L{_GAI_ADDRESS}.
    """

    _getaddrinfo = socket.getaddrinfo
    _deferToThread = threads.deferToThread
    _GAI_ADDRESS = 4
    _GAI_ADDRESS_HOST = 0

    def __init__(self, reactor, host, port, timeout=30, bindAddress=None):
        """
        @param host: An IPv6 address literal or a hostname with an
            IPv6 address

        @see: L{twisted.internet.interfaces.IReactorTCP.connectTCP}
        """
        self._reactor = reactor
        self._host = host
        self._port = port
        self._timeout = timeout
        self._bindAddress = bindAddress


    def connect(self, protocolFactory):
        """
        Implement L{IStreamClientEndpoint.connect} to connect via TCP,
        once the hostname resolution is done.
        """
        if isIPv6Address(self._host):
            d = self._resolvedHostConnect(self._host, protocolFactory)
        else:
            d = self._nameResolution(self._host)
            d.addCallback(lambda result: result[0][self._GAI_ADDRESS]
                          [self._GAI_ADDRESS_HOST])
            d.addCallback(self._resolvedHostConnect, protocolFactory)
        return d


    def _nameResolution(self, host):
        """
        Resolve the hostname string into a tuple containig the host
        IPv6 address.
        """
        return self._deferToThread(
            self._getaddrinfo, host, 0, socket.AF_INET6)


    def _resolvedHostConnect(self, resolvedHost, protocolFactory):
        """
        Connect to the server using the resolved hostname.
        """
        try:
            wf = _WrappingFactory(protocolFactory)
            self._reactor.connectTCP(resolvedHost, self._port, wf,
                timeout=self._timeout, bindAddress=self._bindAddress)
            return wf._onConnection
        except:
            return defer.fail()



@implementer(interfaces.IStreamServerEndpoint)
class SSL4ServerEndpoint(object):
    """
    SSL secured TCP server endpoint with an IPv4 configuration.
    """

    def __init__(self, reactor, port, sslContextFactory,
                 backlog=50, interface=''):
        """
        @param reactor: An L{IReactorSSL} provider.

        @param port: The port number used for listening
        @type port: int

        @param sslContextFactory: An instance of
            L{twisted.internet.ssl.ContextFactory}.

        @param backlog: Size of the listen queue
        @type backlog: int

        @param interface: The hostname to bind to, defaults to '' (all)
        @type interface: str
        """
        self._reactor = reactor
        self._port = port
        self._sslContextFactory = sslContextFactory
        self._backlog = backlog
        self._interface = interface


    def listen(self, protocolFactory):
        """
        Implement L{IStreamServerEndpoint.listen} to listen for SSL on a
        TCP socket.
        """
        return defer.execute(self._reactor.listenSSL, self._port,
                             protocolFactory,
                             contextFactory=self._sslContextFactory,
                             backlog=self._backlog,
                             interface=self._interface)



@implementer(interfaces.IStreamClientEndpoint)
class SSL4ClientEndpoint(object):
    """
    SSL secured TCP client endpoint with an IPv4 configuration
    """

    def __init__(self, reactor, host, port, sslContextFactory,
                 timeout=30, bindAddress=None):
        """
        @param reactor: An L{IReactorSSL} provider.

        @param host: A hostname, used when connecting
        @type host: str

        @param port: The port number, used when connecting
        @type port: int

        @param sslContextFactory: SSL Configuration information as an instance
            of L{twisted.internet.ssl.ContextFactory}.

        @param timeout: Number of seconds to wait before assuming the
            connection has failed.
        @type timeout: int

        @param bindAddress: A (host, port) tuple of local address to bind to,
            or None.
        @type bindAddress: tuple
        """
        self._reactor = reactor
        self._host = host
        self._port = port
        self._sslContextFactory = sslContextFactory
        self._timeout = timeout
        self._bindAddress = bindAddress


    def connect(self, protocolFactory):
        """
        Implement L{IStreamClientEndpoint.connect} to connect with SSL over
        TCP.
        """
        try:
            wf = _WrappingFactory(protocolFactory)
            self._reactor.connectSSL(
                self._host, self._port, wf, self._sslContextFactory,
                timeout=self._timeout, bindAddress=self._bindAddress)
            return wf._onConnection
        except:
            return defer.fail()
