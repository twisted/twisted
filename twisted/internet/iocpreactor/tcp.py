# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
TCP support for IOCP reactor
"""

import socket, operator, errno, struct

from zope.interface import implements, directlyProvides

from twisted.internet import interfaces, error, address, main, defer
from twisted.internet.abstract import isIPAddress
from twisted.internet.tcp import _SocketCloser, Connector as TCPConnector
from twisted.python import log, failure, reflect, util

from twisted.internet.iocpreactor import iocpsupport as _iocp, abstract
from twisted.internet.iocpreactor.interfaces import IReadWriteHandle
from twisted.internet.iocpreactor.const import ERROR_IO_PENDING
from twisted.internet.iocpreactor.const import SO_UPDATE_CONNECT_CONTEXT
from twisted.internet.iocpreactor.const import SO_UPDATE_ACCEPT_CONTEXT
from twisted.internet.iocpreactor.const import ERROR_CONNECTION_REFUSED
from twisted.internet.iocpreactor.const import ERROR_NETWORK_UNREACHABLE

try:
    from twisted.protocols.tls import TLSMemoryBIOFactory, TLSMemoryBIOProtocol
except ImportError:
    TLSMemoryBIOProtocol = TLSMemoryBIOFactory = None
    _extraInterfaces = ()
else:
    _extraInterfaces = (interfaces.ITLSTransport,)

# ConnectEx returns these. XXX: find out what it does for timeout
connectExErrors = {
        ERROR_CONNECTION_REFUSED: errno.WSAECONNREFUSED,
        ERROR_NETWORK_UNREACHABLE: errno.WSAENETUNREACH,
        }


class _BypassTLS(object):
    """
    L{_BypassTLS} is used as the transport object for the TLS protocol object
    used to implement C{startTLS}.  Its methods skip any TLS logic which
    C{startTLS} enables.

    @ivar _connection: A L{Connection} which TLS has been started on which will
        be proxied to by this object.  Any method which has its behavior
        altered after C{startTLS} will be skipped in favor of the base class's
        implementation.  This allows the TLS protocol object to have direct
        access to the transport, necessary to actually implement TLS.
    """
    def __init__(self, connection):
        self._connection = connection


    def __getattr__(self, name):
        return getattr(self._connection, name)


    def write(self, data):
        return abstract.FileHandle.write(self._connection, data)


    def writeSequence(self, iovec):
        return abstract.FileHandle.writeSequence(self._connection, iovec)


    def loseConnection(self, reason=None):
        return abstract.FileHandle.loseConnection(self._connection, reason)



class Connection(abstract.FileHandle, _SocketCloser):
    """
    @ivar _tls: C{False} to indicate the connection is in normal TCP mode,
        C{True} to indicate that TLS has been started and that operations must
        be routed through the L{TLSMemoryBIOProtocol} instance.

    @ivar _tlsClientDefault: A flag which must be set by a subclass.  If set to
        C{True}, L{startTLS} will default to initiating SSL as a client.  If
        set to C{False}, L{startTLS} will default to initiating SSL as a
        server.
    """
    implements(IReadWriteHandle, interfaces.ITCPTransport,
               interfaces.ISystemHandle, *_extraInterfaces)

    _tls = False

    def __init__(self, sock, proto, reactor=None):
        abstract.FileHandle.__init__(self, reactor)
        self.socket = sock
        self.getFileHandle = sock.fileno
        self.protocol = proto


    def getHandle(self):
        return self.socket


    def dataReceived(self, rbuffer):
        # XXX: some day, we'll have protocols that can handle raw buffers
        self.protocol.dataReceived(str(rbuffer))


    def readFromHandle(self, bufflist, evt):
        return _iocp.recv(self.getFileHandle(), bufflist, evt)


    def writeToHandle(self, buff, evt):
        return _iocp.send(self.getFileHandle(), buff, evt)


    def _closeWriteConnection(self):
        try:
            getattr(self.socket, self._socketShutdownMethod)(1)
        except socket.error:
            pass
        p = interfaces.IHalfCloseableProtocol(self.protocol, None)
        if p:
            try:
                p.writeConnectionLost()
            except:
                f = failure.Failure()
                log.err()
                self.connectionLost(f)


    def readConnectionLost(self, reason):
        p = interfaces.IHalfCloseableProtocol(self.protocol, None)
        if p:
            try:
                p.readConnectionLost()
            except:
                log.err()
                self.connectionLost(failure.Failure())
        else:
            self.connectionLost(reason)


    def connectionLost(self, reason):
        abstract.FileHandle.connectionLost(self, reason)
        self._closeSocket()
        protocol = self.protocol
        del self.protocol
        del self.socket
        del self.getFileHandle
        protocol.connectionLost(reason)


    def logPrefix(self):
        """
        Return the prefix to log with when I own the logging thread.
        """
        return self.logstr


    def getTcpNoDelay(self):
        return operator.truth(self.socket.getsockopt(socket.IPPROTO_TCP,
                                                     socket.TCP_NODELAY))


    def setTcpNoDelay(self, enabled):
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, enabled)


    def getTcpKeepAlive(self):
        return operator.truth(self.socket.getsockopt(socket.SOL_SOCKET,
                                                     socket.SO_KEEPALIVE))


    def setTcpKeepAlive(self, enabled):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, enabled)


    if TLSMemoryBIOFactory is not None:
        def startTLS(self, contextFactory, normal=True):
            """
            @see: L{ITLSTransport.startTLS}
            """
            # Figure out which direction the SSL goes in.  If normal is True,
            # we'll go in the direction indicated by the subclass.  Otherwise,
            # we'll go the other way (client = not normal ^ _tlsClientDefault,
            # in other words).
            if normal:
                client = self._tlsClientDefault
            else:
                client = not self._tlsClientDefault

            tlsFactory = TLSMemoryBIOFactory(contextFactory, client, None)
            tlsProtocol = TLSMemoryBIOProtocol(tlsFactory, self.protocol, False)
            self.protocol = tlsProtocol

            self.getHandle = tlsProtocol.getHandle
            self.getPeerCertificate = tlsProtocol.getPeerCertificate

            # Mark the transport as secure.
            directlyProvides(self, interfaces.ISSLTransport)

            # Remember we did this so that write and writeSequence can send the
            # data to the right place.
            self._tls = True

            # Hook it up
            self.protocol.makeConnection(_BypassTLS(self))


    def write(self, data):
        """
        Write some data, either directly to the underlying handle or, if TLS
        has been started, to the L{TLSMemoryBIOProtocol} for it to encrypt and
        send.

        @see: L{ITCPTransport.write}
        """
        if self._tls:
            self.protocol.write(data)
        else:
            abstract.FileHandle.write(self, data)


    def writeSequence(self, iovec):
        """
        Write some data, either directly to the underlying handle or, if TLS
        has been started, to the L{TLSMemoryBIOProtocol} for it to encrypt and
        send.

        @see: L{ITCPTransport.writeSequence}
        """
        if self._tls:
            self.protocol.writeSequence(iovec)
        else:
            abstract.FileHandle.writeSequence(self, iovec)


    def loseConnection(self, reason=None):
        """
        Close the underlying handle or, if TLS has been started, first shut it
        down.

        @see: L{ITCPTransport.loseConnection}
        """
        if self._tls:
            if self.connected and not self.disconnecting:
                self.protocol.loseConnection()
        else:
            abstract.FileHandle.loseConnection(self, reason)



class Client(Connection):
    addressFamily = socket.AF_INET
    socketType = socket.SOCK_STREAM

    _tlsClientDefault = True

    def __init__(self, host, port, bindAddress, connector, reactor):
        self.connector = connector
        self.addr = (host, port)
        self.reactor = reactor
        # ConnectEx documentation says socket _has_ to be bound
        if bindAddress is None:
            bindAddress = ('', 0)

        try:
            try:
                skt = reactor.createSocket(self.addressFamily, self.socketType)
            except socket.error, se:
                raise error.ConnectBindError(se[0], se[1])
            else:
                try:
                    skt.bind(bindAddress)
                except socket.error, se:
                    raise error.ConnectBindError(se[0], se[1])
                self.socket = skt
                Connection.__init__(self, skt, None, reactor)
                reactor.callLater(0, self.resolveAddress)
        except error.ConnectBindError, err:
            reactor.callLater(0, self.failIfNotConnected, err)


    def resolveAddress(self):
        if isIPAddress(self.addr[0]):
            self._setRealAddress(self.addr[0])
        else:
            d = self.reactor.resolve(self.addr[0])
            d.addCallbacks(self._setRealAddress, self.failIfNotConnected)


    def _setRealAddress(self, address):
        self.realAddress = (address, self.addr[1])
        self.doConnect()


    def failIfNotConnected(self, err):
        if (self.connected or self.disconnected or
            not hasattr(self, "connector")):
            return

        try:
            self._closeSocket()
        except AttributeError:
            pass
        else:
            del self.socket, self.getFileHandle
        self.reactor.removeActiveHandle(self)

        self.connector.connectionFailed(failure.Failure(err))
        del self.connector


    def stopConnecting(self):
        """
        Stop attempt to connect.
        """
        self.failIfNotConnected(error.UserError())


    def cbConnect(self, rc, bytes, evt):
        if rc:
            rc = connectExErrors.get(rc, rc)
            self.failIfNotConnected(error.getConnectError((rc,
                                    errno.errorcode.get(rc, 'Unknown error'))))
        else:
            self.socket.setsockopt(socket.SOL_SOCKET,
                                   SO_UPDATE_CONNECT_CONTEXT,
                                   struct.pack('I', self.socket.fileno()))
            self.protocol = self.connector.buildProtocol(self.getPeer())
            self.connected = True
            self.logstr = self.protocol.__class__.__name__+",client"
            self.protocol.makeConnection(self)
            self.startReading()


    def doConnect(self):
        if not hasattr(self, "connector"):
            # this happens if we connector.stopConnecting in
            # factory.startedConnecting
            return
        assert _iocp.have_connectex
        self.reactor.addActiveHandle(self)
        evt = _iocp.Event(self.cbConnect, self)

        rc = _iocp.connect(self.socket.fileno(), self.realAddress, evt)
        if rc == ERROR_IO_PENDING:
            return
        else:
            evt.ignore = True
            self.cbConnect(rc, 0, 0, evt)


    def getHost(self):
        """
        Returns an IPv4Address.

        This indicates the address from which I am connecting.
        """
        return address.IPv4Address('TCP', *(self.socket.getsockname() +
                                            ('INET',)))


    def getPeer(self):
        """
        Returns an IPv4Address.

        This indicates the address that I am connected to.
        """
        return address.IPv4Address('TCP', *(self.realAddress + ('INET',)))


    def __repr__(self):
        s = ('<%s to %s at %x>' %
                (self.__class__, self.addr, util.unsignedID(self)))
        return s


    def connectionLost(self, reason):
        if not self.connected:
            self.failIfNotConnected(error.ConnectError(string=reason))
        else:
            Connection.connectionLost(self, reason)
            self.connector.connectionLost(reason)



class Server(Connection):
    """
    Serverside socket-stream connection class.

    I am a serverside network connection transport; a socket which came from an
    accept() on a server.
    """

    _tlsClientDefault = False


    def __init__(self, sock, protocol, clientAddr, serverAddr, sessionno, reactor):
        """
        Server(sock, protocol, client, server, sessionno)

        Initialize me with a socket, a protocol, a descriptor for my peer (a
        tuple of host, port describing the other end of the connection), an
        instance of Port, and a session number.
        """
        Connection.__init__(self, sock, protocol, reactor)
        self.serverAddr = serverAddr
        self.clientAddr = clientAddr
        self.sessionno = sessionno
        self.logstr = "%s,%s,%s" % (self.protocol.__class__.__name__,
                                    sessionno, self.clientAddr.host)
        self.repstr = "<%s #%s on %s>" % (self.protocol.__class__.__name__,
                                          self.sessionno, self.serverAddr.port)
        self.connected = True
        self.startReading()


    def __repr__(self):
        """
        A string representation of this connection.
        """
        return self.repstr


    def getHost(self):
        """
        Returns an IPv4Address.

        This indicates the server's address.
        """
        return self.serverAddr


    def getPeer(self):
        """
        Returns an IPv4Address.

        This indicates the client's address.
        """
        return self.clientAddr



class Connector(TCPConnector):
    def _makeTransport(self):
        return Client(self.host, self.port, self.bindAddress, self,
                      self.reactor)



class Port(_SocketCloser):
    implements(interfaces.IListeningPort)

    connected = False
    disconnected = False
    disconnecting = False
    addressFamily = socket.AF_INET
    socketType = socket.SOCK_STREAM

    sessionno = 0

    maxAccepts = 100

    # Actual port number being listened on, only set to a non-None
    # value when we are actually listening.
    _realPortNumber = None


    def __init__(self, port, factory, backlog=50, interface='', reactor=None):
        self.port = port
        self.factory = factory
        self.backlog = backlog
        self.interface = interface
        self.reactor = reactor


    def __repr__(self):
        if self._realPortNumber is not None:
            return "<%s of %s on %s>" % (self.__class__,
                                         self.factory.__class__,
                                         self._realPortNumber)
        else:
            return "<%s of %s (not listening)>" % (self.__class__,
                                                   self.factory.__class__)


    def startListening(self):
        try:
            skt = self.reactor.createSocket(self.addressFamily,
                                            self.socketType)
            # TODO: resolve self.interface if necessary
            skt.bind((self.interface, self.port))
        except socket.error, le:
            raise error.CannotListenError, (self.interface, self.port, le)

        self.addrLen = _iocp.maxAddrLen(skt.fileno())

        # Make sure that if we listened on port 0, we update that to
        # reflect what the OS actually assigned us.
        self._realPortNumber = skt.getsockname()[1]

        log.msg("%s starting on %s" % (self.factory.__class__,
                                       self._realPortNumber))

        self.factory.doStart()
        skt.listen(self.backlog)
        self.connected = True
        self.disconnected = False
        self.reactor.addActiveHandle(self)
        self.socket = skt
        self.getFileHandle = self.socket.fileno
        self.doAccept()


    def loseConnection(self, connDone=failure.Failure(main.CONNECTION_DONE)):
        """
        Stop accepting connections on this port.

        This will shut down my socket and call self.connectionLost().
        It returns a deferred which will fire successfully when the
        port is actually closed.
        """
        self.disconnecting = True
        if self.connected:
            self.deferred = defer.Deferred()
            self.reactor.callLater(0, self.connectionLost, connDone)
            return self.deferred

    stopListening = loseConnection


    def _logConnectionLostMsg(self):
        """
        Log message for closing port
        """
        log.msg('(TCP Port %s Closed)' % (self._realPortNumber,))


    def connectionLost(self, reason):
        """
        Cleans up the socket.
        """
        self._logConnectionLostMsg()
        self._realPortNumber = None
        d = None
        if hasattr(self, "deferred"):
            d = self.deferred
            del self.deferred

        self.disconnected = True
        self.reactor.removeActiveHandle(self)
        self.connected = False
        self._closeSocket()
        del self.socket
        del self.getFileHandle

        try:
            self.factory.doStop()
        except:
            self.disconnecting = False
            if d is not None:
                d.errback(failure.Failure())
            else:
                raise
        else:
            self.disconnecting = False
            if d is not None:
                d.callback(None)


    def logPrefix(self):
        """
        Returns the name of my class, to prefix log entries with.
        """
        return reflect.qual(self.factory.__class__)


    def getHost(self):
        """
        Returns an IPv4Address.

        This indicates the server's address.
        """
        return address.IPv4Address('TCP', *(self.socket.getsockname() +
                                            ('INET',)))


    def cbAccept(self, rc, bytes, evt):
        self.handleAccept(rc, evt)
        if not (self.disconnecting or self.disconnected):
            self.doAccept()


    def handleAccept(self, rc, evt):
        if self.disconnecting or self.disconnected:
            return False

        # possible errors:
        # (WSAEMFILE, WSAENOBUFS, WSAENFILE, WSAENOMEM, WSAECONNABORTED)
        if rc:
            log.msg("Could not accept new connection -- %s (%s)" %
                    (errno.errorcode.get(rc, 'unknown error'), rc))
            return False
        else:
            evt.newskt.setsockopt(socket.SOL_SOCKET, SO_UPDATE_ACCEPT_CONTEXT,
                                  struct.pack('I', self.socket.fileno()))
            family, lAddr, rAddr = _iocp.get_accept_addrs(evt.newskt.fileno(),
                                                          evt.buff)
            assert family == self.addressFamily

            protocol = self.factory.buildProtocol(
                address._ServerFactoryIPv4Address('TCP', rAddr[0], rAddr[1]))
            if protocol is None:
                evt.newskt.close()
            else:
                s = self.sessionno
                self.sessionno = s+1
                transport = Server(evt.newskt, protocol,
                        address.IPv4Address('TCP', rAddr[0], rAddr[1], 'INET'),
                        address.IPv4Address('TCP', lAddr[0], lAddr[1], 'INET'),
                        s, self.reactor)
                protocol.makeConnection(transport)
            return True


    def doAccept(self):
        numAccepts = 0
        while 1:
            evt = _iocp.Event(self.cbAccept, self)

            # see AcceptEx documentation
            evt.buff = buff = _iocp.AllocateReadBuffer(2 * (self.addrLen + 16))

            evt.newskt = newskt = self.reactor.createSocket(self.addressFamily,
                                                            self.socketType)
            rc = _iocp.accept(self.socket.fileno(), newskt.fileno(), buff, evt)

            if (rc == ERROR_IO_PENDING
                or (not rc and numAccepts >= self.maxAccepts)):
                break
            else:
                evt.ignore = True
                if not self.handleAccept(rc, evt):
                    break
            numAccepts += 1


