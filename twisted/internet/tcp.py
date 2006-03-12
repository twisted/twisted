# -*- test-case-name: twisted.test.test_tcp -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.



"""Various asynchronous TCP/IP classes.

End users shouldn't use this module directly - use the reactor APIs instead.

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""


# System Imports
import os
import stat
import types
import exceptions
import socket
import sys
import select
import operator
import warnings
try:
    import fcntl
except ImportError:
    fcntl = None
from zope.interface import implements, classImplements

try:
    from OpenSSL import SSL
except ImportError:
    SSL = None

from twisted.python.runtime import platform, platformType

if platformType == 'win32':
     # no such thing as WSAEPERM or error code 10001 according to winsock.h or MSDN
    EPERM=object()
    from errno import WSAEINVAL as EINVAL
    from errno import WSAEWOULDBLOCK as EWOULDBLOCK
    from errno import WSAEINPROGRESS as EINPROGRESS
    from errno import WSAEALREADY as EALREADY
    from errno import WSAECONNRESET as ECONNRESET
    from errno import WSAEISCONN as EISCONN
    from errno import WSAENOTCONN as ENOTCONN
    from errno import WSAEINTR as EINTR
    from errno import WSAENOBUFS as ENOBUFS
    EAGAIN=EWOULDBLOCK
else:
    from errno import EPERM
    from errno import EINVAL
    from errno import EWOULDBLOCK
    from errno import EINPROGRESS
    from errno import EALREADY
    from errno import ECONNRESET
    from errno import EISCONN
    from errno import ENOTCONN
    from errno import EINTR
    from errno import ENOBUFS
    from errno import EAGAIN

# Twisted Imports
from twisted.internet import protocol, defer, base, address
from twisted.persisted import styles
from twisted.python import log, failure, reflect, components
from twisted.python.util import unsignedID
from twisted.internet.error import CannotListenError

# Sibling Imports
import abstract
import main
import interfaces
import error

class _SocketCloser:
    _socketShutdownMethod = 'shutdown'

    def _closeSocket(self):
        # socket.close() doesn't *really* close if there's another reference
        # to it in the TCP/IP stack, e.g. if it was was inherited by a
        # subprocess. And we really do want to close the connection. So we
        # use shutdown() instead, and then close() in order to release the
        # filedescriptor.
        skt = self.socket
        try:
            getattr(skt, self._socketShutdownMethod)(2)
        except socket.error:
            pass
        try:
            skt.close()
        except socket.error:
            pass

class _TLSMixin:
    _socketShutdownMethod = 'sock_shutdown'

    writeBlockedOnRead = 0
    readBlockedOnWrite = 0
    _userWantRead = _userWantWrite = True
    
    def getPeerCertificate(self):
        return self.socket.get_peer_certificate()

    def doRead(self):
        if self.writeBlockedOnRead:
            self.writeBlockedOnRead = 0
            self._resetReadWrite()
        try:
            return Connection.doRead(self)
        except SSL.ZeroReturnError:
            return main.CONNECTION_DONE
        except SSL.WantReadError:
            return
        except SSL.WantWriteError:
            self.readBlockedOnWrite = 1
            Connection.startWriting(self)
            Connection.stopReading(self)
            return
        except SSL.SysCallError, (retval, desc):
            if ((retval == -1 and desc == 'Unexpected EOF')
                or retval > 0):
                return main.CONNECTION_LOST
            log.err()
            return main.CONNECTION_LOST
        except SSL.Error, e:
            return e

    def doWrite(self):
        # Retry disconnecting
        if self.disconnected:
            return self._postLoseConnection()
        if self._writeDisconnected:
            return self._closeWriteConnection()
        
        if self.readBlockedOnWrite:
            self.readBlockedOnWrite = 0
            self._resetReadWrite()
        return Connection.doWrite(self)

    def writeSomeData(self, data):
        try:
            return Connection.writeSomeData(self, data)
        except SSL.WantWriteError:
            return 0
        except SSL.WantReadError:
            self.writeBlockedOnRead = 1
            Connection.stopWriting(self)
            Connection.startReading(self)
            return 0
        except SSL.ZeroReturnError:
            return main.CONNECTION_LOST
        except SSL.SysCallError, e:
            if e[0] == -1 and data == "":
                # errors when writing empty strings are expected
                # and can be ignored
                return 0
            else:
                return main.CONNECTION_LOST
        except SSL.Error, e:
            return e

    def _postLoseConnection(self):
        """Gets called after loseConnection(), after buffered data is sent.

        We try to send an SSL shutdown alert, but if it doesn't work, retry
        when the socket is writable.
        """
        self.disconnected=1
        if hasattr(self.socket, 'set_shutdown'):
            self.socket.set_shutdown(SSL.RECEIVED_SHUTDOWN)
        return self._sendCloseAlert()

    _first=False
    def _sendCloseAlert(self):
        # Okay, *THIS* is a bit complicated.
        
        # Basically, the issue is, OpenSSL seems to not actually return
        # errors from SSL_shutdown. Therefore, the only way to
        # determine if the close notification has been sent is by 
        # SSL_shutdown returning "done". However, it will not claim it's
        # done until it's both sent *and* received a shutdown notification.

        # I don't actually want to wait for a received shutdown
        # notification, though, so, I have to set RECEIVED_SHUTDOWN
        # before calling shutdown. Then, it'll return True once it's
        # *SENT* the shutdown.

        # However, RECEIVED_SHUTDOWN can't be left set, because then
        # reads will fail, breaking half close.

        # Also, since shutdown doesn't report errors, an empty write call is
        # done first, to try to detect if the connection has gone away.
        # (*NOT* an SSL_write call, because that fails once you've called
        # shutdown)
        try:
            os.write(self.socket.fileno(), '')
        except OSError, se:
            if se.args[0] in (EINTR, EWOULDBLOCK, ENOBUFS):
                return 0
            # Write error, socket gone
            return main.CONNECTION_LOST

        try:
            if hasattr(self.socket, 'set_shutdown'):
                laststate = self.socket.get_shutdown()
                self.socket.set_shutdown(laststate | SSL.RECEIVED_SHUTDOWN)
                done = self.socket.shutdown()
                if not (laststate & SSL.RECEIVED_SHUTDOWN):
                    self.socket.set_shutdown(SSL.SENT_SHUTDOWN)
            else:
                #warnings.warn("SSL connection shutdown possibly unreliable, "
                #              "please upgrade to ver 0.XX", category=UserWarning)
                self.socket.shutdown()
                done = True
        except SSL.Error, e:
            return e

        if done:
            self.stopWriting()
            # Note that this is tested for by identity below.
            return main.CONNECTION_DONE
        else:
            self.startWriting()
            return None

    def _closeWriteConnection(self):
        result = self._sendCloseAlert()
        
        if result is main.CONNECTION_DONE:
            return Connection._closeWriteConnection(self)
        
        return result

    def startReading(self):
        self._userWantRead = True
        if not self.readBlockedOnWrite:
            return Connection.startReading(self)

    def stopReading(self):
        self._userWantRead = False
        if not self.writeBlockedOnRead:
            return Connection.stopReading(self)

    def startWriting(self):
        self._userWantWrite = True
        if not self.writeBlockedOnRead:
            return Connection.startWriting(self)

    def stopWriting(self):
        self._userWantWrite = False
        if not self.readBlockedOnWrite:
            return Connection.stopWriting(self)

    def _resetReadWrite(self):
        # After changing readBlockedOnWrite or writeBlockedOnRead,
        # call this to reset the state to what the user requested.
        if self._userWantWrite:
            self.startWriting()
        else:
            self.stopWriting()
        
        if self._userWantRead:
            self.startReading()
        else:
            self.stopReading()

def _getTLSClass(klass, _existing={}):
    if klass not in _existing:
        class TLSConnection(_TLSMixin, klass):
            implements(interfaces.ISSLTransport)
        _existing[klass] = TLSConnection
    return _existing[klass]

class Connection(abstract.FileDescriptor, _SocketCloser):
    """I am the superclass of all socket-based FileDescriptors.

    This is an abstract superclass of all objects which represent a TCP/IP
    connection based socket.
    """

    implements(interfaces.ITCPTransport, interfaces.ISystemHandle)

    TLS = 0

    def __init__(self, skt, protocol, reactor=None):
        abstract.FileDescriptor.__init__(self, reactor=reactor)
        self.socket = skt
        self.socket.setblocking(0)
        self.fileno = skt.fileno
        self.protocol = protocol

    if SSL:

        def startTLS(self, ctx):
            assert not self.TLS
            error=False
            if self.dataBuffer or self._tempDataBuffer:
                self.dataBuffer += "".join(self._tempDataBuffer)
                self._tempDataBuffer = []
                self._tempDataLen = 0
                written = self.writeSomeData(buffer(self.dataBuffer, self.offset))
                offset = self.offset
                dataLen = len(self.dataBuffer)
                self.offset = 0
                self.dataBuffer = ""
                if isinstance(written, Exception) or (offset + written != dataLen):
                    error=True


            self.stopReading()
            self.stopWriting()
            self._startTLS()
            self.socket = SSL.Connection(ctx.getContext(), self.socket)
            self.fileno = self.socket.fileno
            self.startReading()
            if error:
                warnings.warn("startTLS with unwritten buffered data currently doesn't work right. See issue #686. Closing connection.", category=RuntimeWarning, stacklevel=2)
                self.loseConnection()
                return

        def _startTLS(self):
            self.TLS = 1
            self.__class__ = _getTLSClass(self.__class__)

    def getHandle(self):
        """Return the socket for this connection."""
        return self.socket
    
    def doRead(self):
        """Calls self.protocol.dataReceived with all available data.

        This reads up to self.bufferSize bytes of data from its socket, then
        calls self.dataReceived(data) to process it.  If the connection is not
        lost through an error in the physical recv(), this function will return
        the result of the dataReceived call.
        """
        try:
            data = self.socket.recv(self.bufferSize)
        except socket.error, se:
            if se.args[0] == EWOULDBLOCK:
                return
            else:
                return main.CONNECTION_LOST
        if not data:
            return main.CONNECTION_DONE
        return self.protocol.dataReceived(data)

    def writeSomeData(self, data):
        """Connection.writeSomeData(data) -> #of bytes written | CONNECTION_LOST
        This writes as much data as possible to the socket and returns either
        the number of bytes read (which is positive) or a connection error code
        (which is negative)
        """
        try:
            # Limit length of buffer to try to send, because some OSes are too
            # stupid to do so themselves (ahem windows)
            return self.socket.send(buffer(data, 0, self.SEND_LIMIT))
        except socket.error, se:
            if se.args[0] == EINTR:
                return self.writeSomeData(data)
            elif se.args[0] in (EWOULDBLOCK, ENOBUFS):
                return 0
            else:
                return main.CONNECTION_LOST

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
        """See abstract.FileDescriptor.connectionLost().
        """
        abstract.FileDescriptor.connectionLost(self, reason)
        self._closeSocket()
        protocol = self.protocol
        del self.protocol
        del self.socket
        del self.fileno
        protocol.connectionLost(reason)

    logstr = "Uninitialized"

    def logPrefix(self):
        """Return the prefix to log with when I own the logging thread.
        """
        return self.logstr

    def getTcpNoDelay(self):
        return operator.truth(self.socket.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY))

    def setTcpNoDelay(self, enabled):
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, enabled)

    def getTcpKeepAlive(self):
        return operator.truth(self.socket.getsockopt(socket.SOL_SOCKET,
                                                     socket.SO_KEEPALIVE))

    def setTcpKeepAlive(self, enabled):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, enabled)

if SSL:
    classImplements(Connection, interfaces.ITLSTransport)

class BaseClient(Connection):
    """A base class for client TCP (and similiar) sockets.
    """
    addressFamily = socket.AF_INET
    socketType = socket.SOCK_STREAM

    def _finishInit(self, whenDone, skt, error, reactor):
        """Called by base classes to continue to next stage of initialization."""
        if whenDone:
            Connection.__init__(self, skt, None, reactor)
            self.doWrite = self.doConnect
            self.doRead = self.doConnect
            reactor.callLater(0, whenDone)
        else:
            reactor.callLater(0, self.failIfNotConnected, error)

    def startTLS(self, ctx, client=1):
        holder = Connection.startTLS(self, ctx)
        if client:
            self.socket.set_connect_state()
        else:
            self.socket.set_accept_state()
        return holder

    def stopConnecting(self):
        """Stop attempt to connect."""
        self.failIfNotConnected(error.UserError())

    def failIfNotConnected(self, err):
        if (self.connected or self.disconnected or 
            not hasattr(self, "connector")):
            return
        
        try:
            self._closeSocket()
        except AttributeError:
            pass
        else:
            del self.socket, self.fileno

        self.connector.connectionFailed(failure.Failure(err))
        if hasattr(self, "reactor"):
            # this doesn't happen if we failed in __init__
            self.stopReading()
            self.stopWriting()
            del self.connector

    def createInternetSocket(self):
        """(internal) Create a non-blocking socket using
        self.addressFamily, self.socketType.
        """
        s = socket.socket(self.addressFamily, self.socketType)
        s.setblocking(0)
        if fcntl and hasattr(fcntl, 'FD_CLOEXEC'):
            old = fcntl.fcntl(s.fileno(), fcntl.F_GETFD)
            fcntl.fcntl(s.fileno(), fcntl.F_SETFD, old | fcntl.FD_CLOEXEC)
        return s


    def resolveAddress(self):
        if abstract.isIPAddress(self.addr[0]):
            self._setRealAddress(self.addr[0])
        else:
            d = self.reactor.resolve(self.addr[0])
            d.addCallbacks(self._setRealAddress, self.failIfNotConnected)

    def _setRealAddress(self, address):
        self.realAddress = (address, self.addr[1])
        self.doConnect()

    def doConnect(self):
        """I connect the socket.

        Then, call the protocol's makeConnection, and start waiting for data.
        """
        if not hasattr(self, "connector"):
            # this happens when connection failed but doConnect
            # was scheduled via a callLater in self._finishInit
            return

        # on windows failed connects are reported on exception
        # list, not write or read list.
        if platformType == "win32" or sys.platform == "cygwin":
            r, w, e = select.select([], [], [self.fileno()], 0.0)
            if e:
                err = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                self.failIfNotConnected(error.getConnectError((err, os.strerror(err))))
                return

        try:
            connectResult = self.socket.connect_ex(self.realAddress)
        except socket.error, se:
            connectResult = se.args[0]
        if connectResult:
            if connectResult == EISCONN:
                pass
            # on Windows EINVAL means sometimes that we should keep trying:
            # http://msdn.microsoft.com/library/default.asp?url=/library/en-us/winsock/winsock/connect_2.asp
            elif ((connectResult in (EWOULDBLOCK, EINPROGRESS, EALREADY)) or
                  (connectResult == EINVAL and platformType == "win32")):
                self.startReading()
                self.startWriting()
                return
            else:
                self.failIfNotConnected(error.getConnectError((connectResult, os.strerror(connectResult))))
                return

        # If I have reached this point without raising or returning, that means
        # that the socket is connected.
        del self.doWrite
        del self.doRead
        # we first stop and then start, to reset any references to the old doRead
        self.stopReading()
        self.stopWriting()
        self._connectDone()

    def _connectDone(self):
        self.protocol = self.connector.buildProtocol(self.getPeer())
        self.connected = 1
        self.protocol.makeConnection(self)
        self.logstr = self.protocol.__class__.__name__+",client"
        self.startReading()

    def connectionLost(self, reason):
        if not self.connected:
            self.failIfNotConnected(error.ConnectError(string=reason))
        else:
            Connection.connectionLost(self, reason)
            self.connector.connectionLost(reason)


class Client(BaseClient):
    """A TCP client."""

    def __init__(self, host, port, bindAddress, connector, reactor=None):
        # BaseClient.__init__ is invoked later
        self.connector = connector
        self.addr = (host, port)

        whenDone = self.resolveAddress
        err = None
        skt = None

        try:
            skt = self.createInternetSocket()
        except socket.error, se:
            err = error.ConnectBindError(se[0], se[1])
            whenDone = None
        if whenDone and bindAddress is not None:
            try:
                skt.bind(bindAddress)
            except socket.error, se:
                err = error.ConnectBindError(se[0], se[1])
                whenDone = None
        self._finishInit(whenDone, skt, err, reactor)

    def getHost(self):
        """Returns an IPv4Address.

        This indicates the address from which I am connecting.
        """
        return address.IPv4Address('TCP', *(self.socket.getsockname() + ('INET',)))

    def getPeer(self):
        """Returns an IPv4Address.

        This indicates the address that I am connected to.
        """
        return address.IPv4Address('TCP', *(self.addr + ('INET',)))

    def __repr__(self):
        s = '<%s to %s at %x>' % (self.__class__, self.addr, unsignedID(self))
        return s


class Server(Connection):
    """Serverside socket-stream connection class.

    I am a serverside network connection transport; a socket which came from an
    accept() on a server.
    """

    def __init__(self, sock, protocol, client, server, sessionno):
        """Server(sock, protocol, client, server, sessionno)

        Initialize me with a socket, a protocol, a descriptor for my peer (a
        tuple of host, port describing the other end of the connection), an
        instance of Port, and a session number.
        """
        Connection.__init__(self, sock, protocol)
        self.server = server
        self.client = client
        self.sessionno = sessionno
        self.hostname = client[0]
        self.logstr = "%s,%s,%s" % (self.protocol.__class__.__name__, sessionno, self.hostname)
        self.repstr = "<%s #%s on %s>" % (self.protocol.__class__.__name__, self.sessionno, self.server.port)
        self.startReading()
        self.connected = 1

    def __repr__(self):
        """A string representation of this connection.
        """
        return self.repstr

    def startTLS(self, ctx, server=1):
        holder = Connection.startTLS(self, ctx)
        if server:
            self.socket.set_accept_state()
        else:
            self.socket.set_connect_state()
        return holder

    def getHost(self):
        """Returns an IPv4Address.

        This indicates the server's address.
        """
        return address.IPv4Address('TCP', *(self.socket.getsockname() + ('INET',)))

    def getPeer(self):
        """Returns an IPv4Address.

        This indicates the client's address.
        """
        return address.IPv4Address('TCP', *(self.client + ('INET',)))

class Port(base.BasePort, _SocketCloser):
    """I am a TCP server port, listening for connections.

    When a connection is accepted, I will call my factory's buildProtocol with
    the incoming connection as an argument, according to the specification
    described in twisted.internet.interfaces.IProtocolFactory.

    If you wish to change the sort of transport that will be used, my
    `transport' attribute will be called with the signature expected for
    Server.__init__, so it can be replaced.
    """

    implements(interfaces.IListeningPort)

    addressFamily = socket.AF_INET
    socketType = socket.SOCK_STREAM

    transport = Server
    sessionno = 0
    interface = ''
    backlog = 50

    # Actual port number being listened on, only set to a non-None
    # value when we are actually listening.
    _realPortNumber = None

    def __init__(self, port, factory, backlog=50, interface='', reactor=None):
        """Initialize with a numeric port to listen on.
        """
        base.BasePort.__init__(self, reactor=reactor)
        self.port = port
        self.factory = factory
        self.backlog = backlog
        self.interface = interface

    def __repr__(self):
        if self._realPortNumber is not None:
            return "<%s of %s on %s>" % (self.__class__, self.factory.__class__,
                                         self._realPortNumber)
        else:
            return "<%s of %s (not listening)>" % (self.__class__, self.factory.__class__)

    def createInternetSocket(self):
        s = base.BasePort.createInternetSocket(self)
        if platformType == "posix" and sys.platform != "cygwin":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s

    def startListening(self):
        """Create and bind my socket, and begin listening on it.

        This is called on unserialization, and must be called after creating a
        server to begin listening on the specified port.
        """
        try:
            skt = self.createInternetSocket()
            skt.bind((self.interface, self.port))
        except socket.error, le:
            raise CannotListenError, (self.interface, self.port, le)

        # Make sure that if we listened on port 0, we update that to
        # reflect what the OS actually assigned us.
        self._realPortNumber = skt.getsockname()[1]

        log.msg("%s starting on %s" % (self.factory.__class__, self._realPortNumber))

        # The order of the next 6 lines is kind of bizarre.  If no one
        # can explain it, perhaps we should re-arrange them.
        self.factory.doStart()
        skt.listen(self.backlog)
        self.connected = 1
        self.socket = skt
        self.fileno = self.socket.fileno
        self.numberAccepts = 100

        self.startReading()

    def _buildAddr(self, (host, port)):
        return address._ServerFactoryIPv4Address('TCP', host, port)

    def doRead(self):
        """Called when my socket is ready for reading.

        This accepts a connection and calls self.protocol() to handle the
        wire-level protocol.
        """
        try:
            if platformType == "posix":
                numAccepts = self.numberAccepts
            else:
                # win32 event loop breaks if we do more than one accept()
                # in an iteration of the event loop.
                numAccepts = 1
            for i in range(numAccepts):
                # we need this so we can deal with a factory's buildProtocol
                # calling our loseConnection
                if self.disconnecting:
                    return
                try:
                    skt, addr = self.socket.accept()
                except socket.error, e:
                    if e.args[0] in (EWOULDBLOCK, EAGAIN):
                        self.numberAccepts = i
                        break
                    elif e.args[0] == EPERM:
                        continue
                    raise

                protocol = self.factory.buildProtocol(self._buildAddr(addr))
                if protocol is None:
                    skt.close()
                    continue
                s = self.sessionno
                self.sessionno = s+1
                transport = self.transport(skt, protocol, addr, self, s)
                transport = self._preMakeConnection(transport)
                protocol.makeConnection(transport)
            else:
                self.numberAccepts = self.numberAccepts+20
        except:
            # Note that in TLS mode, this will possibly catch SSL.Errors
            # raised by self.socket.accept()
            #
            # There is no "except SSL.Error:" above because SSL may be
            # None if there is no SSL support.  In any case, all the
            # "except SSL.Error:" suite would probably do is log.deferr()
            # and return, so handling it here works just as well.
            log.deferr()

    def _preMakeConnection(self, transport):
        return transport

    def loseConnection(self, connDone=failure.Failure(main.CONNECTION_DONE)):
        """Stop accepting connections on this port.

        This will shut down my socket and call self.connectionLost().
        It returns a deferred which will fire successfully when the
        port is actually closed.
        """
        self.disconnecting = 1
        self.stopReading()
        if self.connected:
            self.deferred = defer.Deferred()
            self.reactor.callLater(0, self.connectionLost, connDone)
            return self.deferred

    stopListening = loseConnection

    def connectionLost(self, reason):
        """Cleans up my socket.
        """
        log.msg('(Port %s Closed)' % self._realPortNumber)
        self._realPortNumber = None
        base.BasePort.connectionLost(self, reason)
        self.connected = 0
        self._closeSocket()
        del self.socket
        del self.fileno
        self.factory.doStop()
        if hasattr(self, "deferred"):
            self.deferred.callback(None)
            del self.deferred

    def logPrefix(self):
        """Returns the name of my class, to prefix log entries with.
        """
        return reflect.qual(self.factory.__class__)

    def getHost(self):
        """Returns an IPv4Address.

        This indicates the server's address.
        """
        return address.IPv4Address('TCP', *(self.socket.getsockname() + ('INET',)))

class Connector(base.BaseConnector):
    def __init__(self, host, port, factory, timeout, bindAddress, reactor=None):
        self.host = host
        if isinstance(port, types.StringTypes):
            try:
                port = socket.getservbyname(port, 'tcp')
            except socket.error, e:
                raise error.ServiceNameUnknownError(string="%s (%r)" % (e, port))
        self.port = port
        self.bindAddress = bindAddress
        base.BaseConnector.__init__(self, factory, timeout, reactor)

    def _makeTransport(self):
        return Client(self.host, self.port, self.bindAddress, self, self.reactor)

    def getDestination(self):
        return address.IPv4Address('TCP', self.host, self.port, 'INET')
