# -*- test-case-name: twisted.test.test_tcp -*-
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA


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

try:
    from OpenSSL import SSL
except ImportError:
    SSL = None

if os.name == 'nt':
    # we hardcode these since windows actually wants e.g.
    # WSAEALREADY rather than EALREADY. Possibly we should
    # just be doing "from errno import WSAEALREADY as EALREADY".
    EPERM       = 10001
    EINVAL      = 10022
    EWOULDBLOCK = 10035
    EINPROGRESS = 10036
    EALREADY    = 10037
    ECONNRESET  = 10054
    EISCONN     = 10056
    ENOTCONN    = 10057
    EINTR       = 10004
elif os.name != 'java':
    from errno import EPERM
    from errno import EINVAL
    from errno import EWOULDBLOCK
    from errno import EINPROGRESS
    from errno import EALREADY
    from errno import ECONNRESET
    from errno import EISCONN
    from errno import ENOTCONN
    from errno import EINTR
from errno import EAGAIN

# Twisted Imports
from twisted.internet import protocol, defer, base, address
from twisted.persisted import styles
from twisted.python import log, failure, reflect
from twisted.python.runtime import platform, platformType
from twisted.internet.error import CannotListenError

# Sibling Imports
import abstract
import main
import interfaces
import error

class _TLSMixin:
    writeBlockedOnRead = 0
    readBlockedOnWrite = 0
    sslShutdown = 0

    def getPeerCertificate(self):
        return self.socket.get_peer_certificate()

    def doRead(self):
        if self.writeBlockedOnRead:
            self.writeBlockedOnRead = 0
            self.startWriting()
        try:
            return Connection.doRead(self)
        except SSL.ZeroReturnError:
            # close SSL layer, since other side has done so, if we haven't
            if not self.sslShutdown:
                try:
                    self.socket.shutdown()
                    self.sslShutdown = 1
                except SSL.Error:
                    pass
            return main.CONNECTION_DONE
        except SSL.WantReadError:
            return
        except SSL.WantWriteError:
            self.readBlockedOnWrite = 1
            self.startWriting()
            return
        except SSL.Error:
            log.err()
            return main.CONNECTION_LOST

    def loseConnection(self):
        Connection.loseConnection(self)
        if self.connected:
            self.startReading()

    def doWrite(self):
        if self.writeBlockedOnRead:
            self.stopWriting()
            return
        if self.readBlockedOnWrite:
            self.readBlockedOnWrite = 0
            # XXX - This is touching internal guts bad bad bad
            if not self.dataBuffer:
                self.stopWriting()
            return self.doRead()
        return Connection.doWrite(self)

    def writeSomeData(self, data):
        try:
            return Connection.writeSomeData(self, data)
        except SSL.WantWriteError:
            return 0
        except SSL.WantReadError:
            self.writeBlockedOnRead = 1
            return 0
        except SSL.SysCallError, e:
            if e[0] == -1 and data == "":
                # errors when writing empty strings are expected
                # and can be ignored
                return 0
            else:
                return main.CONNECTION_LOST
        except SSL.Error:
            log.err()
            return main.CONNECTION_LOST

    def _closeSocket(self):
        try:
            self.socket.sock_shutdown(2)
        except:
            pass
        try:
            self.socket.close()
        except:
            pass

    def _postLoseConnection(self):
        """Gets called after loseConnection(), after buffered data is sent.

        We close the SSL transport layer, and if the other side hasn't
        closed it yet we start reading, waiting for a ZeroReturnError
        which will indicate the SSL shutdown has completed.
        """
        try:
            done = self.socket.shutdown()
            self.sslShutdown = 1
        except SSL.Error:
            log.err()
            return main.CONNECTION_LOST
        if done:
            return main.CONNECTION_DONE
        else:
            # we wait for other side to close SSL connection -
            # this will be signaled by SSL.ZeroReturnError when reading
            # from the socket
            self.stopWriting()
            self.startReading()

            # don't close socket just yet
            return None

class Connection(abstract.FileDescriptor):
    """I am the superclass of all socket-based FileDescriptors.

    This is an abstract superclass of all objects which represent a TCP/IP
    connection based socket.
    """

    __implements__ = abstract.FileDescriptor.__implements__, interfaces.ITCPTransport, interfaces.ISystemHandle

    TLS = 0

    def __init__(self, skt, protocol, reactor=None):
        abstract.FileDescriptor.__init__(self, reactor=reactor)
        self.socket = skt
        self.socket.setblocking(0)
        self.fileno = skt.fileno
        self.protocol = protocol

    if SSL:
        __implements__ = __implements__ + (interfaces.ITLSTransport,)

        def startTLS(self, ctx):
            assert not self.TLS
            self.stopReading()
            self.stopWriting()
            self._startTLS()
            self.socket = SSL.Connection(ctx.getContext(), self.socket)
            self.fileno = self.socket.fileno
            self.startReading()

        def _startTLS(self):
            self.TLS = 1
            klass = self.__class__
            class TLSConnection(_TLSMixin, klass):
                __implements__ = interfaces.ISSLTransport, klass.__implements__
            self.__class__ = TLSConnection

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
        except SSL.SysCallError, (retval, desc):
            # Yes, SSL might be None, but self.socket.recv() can *only*
            # raise socket.error, if anything else is raised, it must be an
            # SSL socket, and so SSL can't be None. (That's my story, I'm
            # stickin' to it)
            if retval == -1 and desc == 'Unexpected EOF':
                return main.CONNECTION_DONE
            raise
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
            return self.socket.send(data)
        except socket.error, se:
            if se.args[0] == EINTR:
                return self.writeSomeData(data)
            elif se.args[0] == EWOULDBLOCK:
                return 0
            else:
                return main.CONNECTION_LOST

    def _closeSocket(self):
        """Called to close our socket."""
        # This used to close() the socket, but that doesn't *really* close if
        # there's another reference to it in the TCP/IP stack, e.g. if it was
        # was inherited by a subprocess. And we really do want to close the
        # connection. So we use shutdown() instead.
        try:
            self.socket.shutdown(2)
        except socket.error:
            pass

    def connectionLost(self, reason):
        """See abstract.FileDescriptor.connectionLost().
        """
        abstract.FileDescriptor.connectionLost(self, reason)
        self._closeSocket()
        protocol = self.protocol
        del self.protocol
        del self.socket
        del self.fileno
        try:
            protocol.connectionLost(reason)
        except TypeError, e:
            # while this may break, it will only break on deprecated code
            # as opposed to other approaches that might've broken on
            # code that uses the new API (e.g. inspect).
            if e.args and e.args[0] == "connectionLost() takes exactly 1 argument (2 given)":
                warnings.warn("Protocol %s's connectionLost should accept a reason argument" % protocol,
                              category=DeprecationWarning, stacklevel=2)
                protocol.connectionLost()
            else:
                raise

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
        if (self.connected or
            self.disconnected or
            not (hasattr(self, "connector"))):
            return
        self.connector.connectionFailed(failure.Failure(err))
        if hasattr(self, "reactor"):
            # this doesn't happens if we failed in __init__
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
        if platformType == "win32":
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
        s = '<%s to %s at %x>' % (self.__class__, self.addr, id(self))
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

class Port(base.BasePort):
    """I am a TCP server port, listening for connections.

    When a connection is accepted, I will call my factory's buildProtocol with
    the incoming connection as an argument, according to the specification
    described in twisted.internet.interfaces.IProtocolFactory.

    If you wish to change the sort of transport that will be used, my
    `transport' attribute will be called with the signature expected for
    Server.__init__, so it can be replaced.
    """
    addressFamily = socket.AF_INET
    socketType = socket.SOCK_STREAM

    transport = Server
    sessionno = 0
    interface = ''
    backlog = 5

    def __init__(self, port, factory, backlog=5, interface='', reactor=None):
        """Initialize with a numeric port to listen on.
        """
        base.BasePort.__init__(self, reactor=reactor)
        self.port = port
        self.factory = factory
        self.backlog = backlog
        self.interface = interface

    def __repr__(self):
        return "<%s on %s>" % (self.factory.__class__, self.port)

    def createInternetSocket(self):
        s = base.BasePort.createInternetSocket(self)
        if platformType == "posix":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s

    def startListening(self):
        """Create and bind my socket, and begin listening on it.

        This is called on unserialization, and must be called after creating a
        server to begin listening on the specified port.
        """
        log.msg("%s starting on %s"%(self.factory.__class__, self.port))
        try:
            skt = self.createInternetSocket()
            skt.bind((self.interface, self.port))
        except socket.error, le:
            raise CannotListenError, (self.interface, self.port, le)
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
        log.msg('(Port %r Closed)' % self.port)
        base.BasePort.connectionLost(self, reason)
        self.connected = 0
        self.socket.close()
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
                raise error.ServiceNameUnknownError(string=str(e))
        self.port = port
        self.bindAddress = bindAddress
        base.BaseConnector.__init__(self, factory, timeout, reactor)

    def _makeTransport(self):
        return Client(self.host, self.port, self.bindAddress, self, self.reactor)

    def getDestination(self):
        return address.IPv4Address('TCP', self.host, self.port, 'INET')
