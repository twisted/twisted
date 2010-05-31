# -*- test-case-name: twisted.internet.test.test_endpoints -*-
# Copyright (c) 2007-2010 Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Implementations of L{IStreamServerEndpoint} and L{IStreamClientEndpoint} that
wrap the L{IReactorTCP}, L{IReactorSSL}, and L{IReactorUNIX} interfaces.

@since: 10.1
"""

from zope.interface import implements, directlyProvides

from twisted.internet import interfaces, defer, error
from twisted.internet.protocol import ClientFactory, Protocol



__all__ = ["TCP4ServerEndpoint", "TCP4ClientEndpoint",
           "UNIXServerEndpoint", "UNIXClientEndpoint",
           "SSL4ServerEndpoint", "SSL4ClientEndpoint"]


class _WrappingProtocol(Protocol):
    """
    Wrap another protocol in order to notify my user when a connection has
    been made.

    @ivar _connectedDeferred: The L{Deferred} that will callback
        with the C{wrappedProtocol} when it is connected.

    @ivar _wrappedProtocol: An L{IProtocol} provider that will be
        connected.
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

        if interfaces.IHalfCloseableProtocol.providedBy(
            self._wrappedProtocol):
            directlyProvides(self, interfaces.IHalfCloseableProtocol)

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

    @ivar _wrappedFactory:  A provider of I{IProtocolFactory} whose
        buildProtocol method will be called and whose resulting protocol
        will be wrapped.

    @ivar _onConnection: An L{Deferred} that fires when the protocol is
        connected
    """
    protocol = _WrappingProtocol

    def __init__(self, wrappedFactory, canceller):
        """
        @param wrappedFactory: A provider of I{IProtocolFactory} whose
            buildProtocol method will be called and whose resulting protocol
            will be wrapped.
        @param canceller: An object that will be called to cancel the
            L{self._onConnection} L{Deferred}
        """
        self._wrappedFactory = wrappedFactory
        self._onConnection = defer.Deferred(canceller=canceller)


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
        self._onConnection.errback(reason)



class TCP4ServerEndpoint(object):
    """
    TCP server endpoint with an IPv4 configuration

    @ivar _reactor: An L{IReactorTCP} provider.

    @type _port: int
    @ivar _port: The port number on which to listen for incoming connections.

    @type _backlog: int
    @ivar _backlog: size of the listen queue

    @type _interface: str
    @ivar _interface: the hostname to bind to, defaults to '' (all)
    """
    implements(interfaces.IStreamServerEndpoint)

    def __init__(self, reactor, port, backlog=50, interface=''):
        """
        @param reactor: An L{IReactorTCP} provider.
        @param port: The port number used listening
        @param backlog: size of the listen queue
        @param interface: the hostname to bind to, defaults to '' (all)
        """
        self._reactor = reactor
        self._port = port
        self._listenArgs = dict(backlog=50, interface='')
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



class TCP4ClientEndpoint(object):
    """
    TCP client endpoint with an IPv4 configuration.

    @ivar _reactor: An L{IReactorTCP} provider.

    @type _host: str
    @ivar _host: The hostname to connect to as a C{str}

    @type _port: int
    @ivar _port: The port to connect to as C{int}

    @type _timeout: int
    @ivar _timeout: number of seconds to wait before assuming the
        connection has failed.

    @type _bindAddress: tuple
    @type _bindAddress: a (host, port) tuple of local address to bind
        to, or None.
    """
    implements(interfaces.IStreamClientEndpoint)

    def __init__(self, reactor, host, port, timeout=30, bindAddress=None):
        """
        @param reactor: An L{IReactorTCP} provider
        @param host: A hostname, used when connecting
        @param port: The port number, used when connecting
        @param timeout: number of seconds to wait before assuming the
            connection has failed.
        @param bindAddress: a (host, port tuple of local address to bind to,
            or None.
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
        def _canceller(deferred):
            connector.stopConnecting()
            deferred.errback(
                error.ConnectingCancelledError(connector.getDestination()))

        try:
            wf = _WrappingFactory(protocolFactory, _canceller)
            connector = self._reactor.connectTCP(
                self._host, self._port, wf,
                timeout=self._timeout, bindAddress=self._bindAddress)
            return wf._onConnection
        except:
            return defer.fail()



class SSL4ServerEndpoint(object):
    """
    SSL secured TCP server endpoint with an IPv4 configuration.

    @ivar _reactor: An L{IReactorSSL} provider.

    @type _host: str
    @ivar _host: The hostname to connect to as a C{str}

    @type _port: int
    @ivar _port: The port to connect to as C{int}

    @type _sslContextFactory: L{OpenSSLCertificateOptions}
    @var _sslContextFactory: SSL Configuration information as an
        L{OpenSSLCertificateOptions}

    @type _backlog: int
    @ivar _backlog: size of the listen queue

    @type _interface: str
    @ivar _interface: the hostname to bind to, defaults to '' (all)
    """
    implements(interfaces.IStreamServerEndpoint)

    def __init__(self, reactor, port, sslContextFactory,
                 backlog=50, interface=''):
        """
        @param reactor: An L{IReactorSSL} provider.
        @param port: The port number used listening
        @param sslContextFactory: An instance of
            L{twisted.internet._sslverify.OpenSSLCertificateOptions}.
        @param timeout: number of seconds to wait before assuming the
            connection has failed.
        @param bindAddress: a (host, port tuple of local address to bind to,
            or None.
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



class SSL4ClientEndpoint(object):
    """
    SSL secured TCP client endpoint with an IPv4 configuration

    @ivar _reactor: An L{IReactorSSL} provider.

    @type _host: str
    @ivar _host: The hostname to connect to as a C{str}

    @type _port: int
    @ivar _port: The port to connect to as C{int}

    @type _sslContextFactory: L{OpenSSLCertificateOptions}
    @var _sslContextFactory: SSL Configuration information as an
        L{OpenSSLCertificateOptions}

    @type _timeout: int
    @ivar _timeout: number of seconds to wait before assuming the
        connection has failed.

    @type _bindAddress: tuple
    @ivar _bindAddress: a (host, port) tuple of local address to bind
        to, or None.
    """
    implements(interfaces.IStreamClientEndpoint)

    def __init__(self, reactor, host, port, sslContextFactory,
                 timeout=30, bindAddress=None):
        """
        @param reactor: An L{IReactorSSL} provider.
        @param host: A hostname, used when connecting
        @param port: The port number, used when connecting
        @param sslContextFactory: SSL Configuration information as An instance
            of L{OpenSSLCertificateOptions}.
        @param timeout: number of seconds to wait before assuming the
            connection has failed.
        @param bindAddress: a (host, port tuple of local address to bind to,
            or None.
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
        def _canceller(deferred):
            connector.stopConnecting()
            deferred.errback(
                error.ConnectingCancelledError(connector.getDestination()))

        try:
            wf = _WrappingFactory(protocolFactory, _canceller)
            connector = self._reactor.connectSSL(
                self._host, self._port, wf, self._sslContextFactory,
                timeout=self._timeout, bindAddress=self._bindAddress)
            return wf._onConnection
        except:
            return defer.fail()



class UNIXServerEndpoint(object):
    """
    UnixSocket server endpoint.

    @type path: str
    @ivar path: a path to a unix socket on the filesystem.

    @type _listenArgs: dict
    @ivar _listenArgs: A C{dict} of keyword args that will be passed
        to L{IReactorUNIX.listenUNIX}

    @var _reactor: An L{IReactorTCP} provider.
    """
    implements(interfaces.IStreamServerEndpoint)

    def __init__(self, reactor, address, backlog=50, mode=0666, wantPID=0):
        """
        @param reactor: An L{IReactorUNIX} provider.
        @param address: The path to the Unix socket file, used when listening
        @param listenArgs: An optional dict of keyword args that will be
            passed to L{IReactorUNIX.listenUNIX}
        @param backlog: number of connections to allow in backlog.
        @param mode: mode to set on the unix socket.  This parameter is
            deprecated.  Permissions should be set on the directory which
            contains the UNIX socket.
        @param wantPID: if True, create a pidfile for the socket.
        """
        self._reactor = reactor
        self._address = address
        self._backlog = backlog
        self._mode = mode
        self._wantPID = wantPID


    def listen(self, protocolFactory):
        """
        Implement L{IStreamServerEndpoint.listen} to listen on a UNIX socket.
        """
        return defer.execute(self._reactor.listenUNIX, self._address,
                             protocolFactory,
                             backlog=self._backlog,
                             mode=self._mode,
                             wantPID=self._wantPID)



class UNIXClientEndpoint(object):
    """
    UnixSocket client endpoint.

    @type _path: str
    @ivar _path: a path to a unix socket on the filesystem.

    @type _timeout: int
    @ivar _timeout: number of seconds to wait before assuming the connection
        has failed.

    @type _checkPID: bool
    @ivar _checkPID: if True, check for a pid file to verify that a server
        is listening.

    @var _reactor: An L{IReactorUNIX} provider.
    """
    implements(interfaces.IStreamClientEndpoint)

    def __init__(self, reactor, path, timeout=30, checkPID=0):
        """
        @param reactor: An L{IReactorUNIX} provider.
        @param path: The path to the Unix socket file, used when connecting
        @param timeout: number of seconds to wait before assuming the
            connection has failed.
        @param checkPID: if True, check for a pid file to verify that a server
            is listening.
        """
        self._reactor = reactor
        self._path = path
        self._timeout = timeout
        self._checkPID = checkPID


    def connect(self, protocolFactory):
        """
        Implement L{IStreamClientEndpoint.connect} to connect via a
        UNIX Socket
        """
        def _canceller(deferred):
            connector.stopConnecting()
            deferred.errback(
                error.ConnectingCancelledError(connector.getDestination()))

        try:
            wf = _WrappingFactory(protocolFactory, _canceller)
            connector = self._reactor.connectUNIX(
                self._path, wf,
                timeout=self._timeout,
                checkPID=self._checkPID)
            return wf._onConnection
        except:
            return defer.fail()
