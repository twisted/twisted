# -*- test-case-name: twisted.test.test_tcp -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Various asynchronous TCP/IP classes.

End users shouldn't use this module directly - use the reactor APIs instead.

Maintainer: Itamar Shtull-Trauring
"""


# System Imports
import os
import types
import socket
import sys
import operator

from zope.interface import implements, classImplements

try:
    from OpenSSL import SSL
except ImportError:
    SSL = None

from twisted.python.runtime import platformType


if platformType == 'win32':
    # no such thing as WSAEPERM or error code 10001 according to winsock.h or MSDN
    EPERM = object()
    from errno import WSAEINVAL as EINVAL
    from errno import WSAEWOULDBLOCK as EWOULDBLOCK
    from errno import WSAEINPROGRESS as EINPROGRESS
    from errno import WSAEALREADY as EALREADY
    from errno import WSAECONNRESET as ECONNRESET
    from errno import WSAEISCONN as EISCONN
    from errno import WSAENOTCONN as ENOTCONN
    from errno import WSAEINTR as EINTR
    from errno import WSAENOBUFS as ENOBUFS
    from errno import WSAEMFILE as EMFILE
    # No such thing as WSAENFILE, either.
    ENFILE = object()
    # Nor ENOMEM
    ENOMEM = object()
    EAGAIN = EWOULDBLOCK
    from errno import WSAECONNRESET as ECONNABORTED

    from twisted.python.win32 import formatError as strerror
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
    from errno import EMFILE
    from errno import ENFILE
    from errno import ENOMEM
    from errno import EAGAIN
    from errno import ECONNABORTED

    from os import strerror

from errno import errorcode

# Twisted Imports
from twisted.internet import base, address, fdesc
from twisted.internet.task import deferLater
from twisted.python import log, failure, reflect
from twisted.python.util import unsignedID
from twisted.internet.error import CannotListenError
from twisted.internet import abstract, main, interfaces, error



class _SocketCloser(object):
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
        if self.disconnected:
            # See the comment in the similar check in doWrite below.
            # Additionally, in order for anything other than returning
            # CONNECTION_DONE here to make sense, it will probably be necessary
            # to implement a way to switch back to TCP from TLS (actually, if
            # we did something other than return CONNECTION_DONE, that would be
            # a big part of implementing that feature).  In other words, the
            # expectation is that doRead will be called when self.disconnected
            # is True only when the connection has been lost.  It's possible
            # that the other end could stop speaking TLS and then send us some
            # non-TLS data.  We'll end up ignoring that data and dropping the
            # connection.  There's no unit tests for this check in the cases
            # where it makes a difference.  The test suite only hits this
            # codepath when it would have otherwise hit the SSL.ZeroReturnError
            # exception handler below, which has exactly the same behavior as
            # this conditional.  Maybe that's the only case that can ever be
            # triggered, I'm not sure.  -exarkun
            return main.CONNECTION_DONE
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
            # This case is triggered when "disconnected" is set to True by a
            # call to _postLoseConnection from FileDescriptor.doWrite (to which
            # we upcall at the end of this overridden version of that API).  It
            # means that while, as far as any protocol connected to this
            # transport is concerned, the connection no longer exists, the
            # connection *does* actually still exist.  Instead of closing the
            # connection in the overridden _postLoseConnection, we probably
            # tried (and failed) to send a TLS close alert.  The TCP connection
            # is still up and we're waiting for the socket to become writeable
            # enough for the TLS close alert to actually be sendable.  Only
            # then will the connection actually be torn down. -exarkun
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
        """
        Gets called after loseConnection(), after buffered data is sent.

        We try to send an SSL shutdown alert, but if it doesn't work, retry
        when the socket is writable.
        """
        # Here, set "disconnected" to True to trick higher levels into thinking
        # the connection is really gone.  It's not, and we're not going to
        # close it yet.  Instead, we'll try to send a TLS close alert to shut
        # down the TLS connection cleanly.  Only after we actually get the
        # close alert into the socket will we disconnect the underlying TCP
        # connection.
        self.disconnected = True
        if hasattr(self.socket, 'set_shutdown'):
            # If possible, mark the state of the TLS connection as having
            # already received a TLS close alert from the peer.  Why do
            # this???
            self.socket.set_shutdown(SSL.RECEIVED_SHUTDOWN)
        return self._sendCloseAlert()


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
            # For some reason, the close alert wasn't sent.  Start writing
            # again so that we'll get another chance to send it.
            self.startWriting()
            # On Linux, select will sometimes not report a closed file
            # descriptor in the write set (in particular, it seems that if a
            # send() fails with EPIPE, the socket will not appear in the write
            # set).  The shutdown call above (which calls down to SSL_shutdown)
            # may have swallowed a write error.  Therefore, also start reading
            # so that if the socket is closed we will notice.  This doesn't
            # seem to be a problem for poll (because poll reports errors
            # separately) or with select on BSD (presumably because, unlike
            # Linux, it doesn't implement select in terms of poll and then map
            # POLLHUP to select's in fd_set).
            self.startReading()
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



class _TLSDelayed(object):
    """
    State tracking record for TLS startup parameters.  Used to remember how
    TLS should be started when starting it is delayed to wait for the output
    buffer to be flushed.

    @ivar bufferedData: A C{list} which contains all the data which was
        written to the transport after an attempt to start TLS was made but
        before the buffers outstanding at that time could be flushed and TLS
        could really be started.  This is appended to by the transport's
        write and writeSequence methods until it is possible to actually
        start TLS, then it is written to the TLS-enabled transport.

    @ivar context: An SSL context factory object to use to start TLS.

    @ivar extra: An extra argument to pass to the transport's C{startTLS}
        method.
    """
    def __init__(self, bufferedData, context, extra):
        self.bufferedData = bufferedData
        self.context = context
        self.extra = extra



def _getTLSClass(klass, _existing={}):
    if klass not in _existing:
        class TLSConnection(_TLSMixin, klass):
            implements(interfaces.ISSLTransport)
        _existing[klass] = TLSConnection
    return _existing[klass]



class Connection(abstract.FileDescriptor, _SocketCloser):
    """
    Superclass of all socket-based FileDescriptors.

    This is an abstract superclass of all objects which represent a TCP/IP
    connection based socket.

    @ivar logstr: prefix used when logging events related to this connection.
    @type logstr: C{str}
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
        _tlsWaiting = None
        def startTLS(self, ctx, extra):
            assert not self.TLS
            if self.dataBuffer or self._tempDataBuffer:
                # pre-TLS bytes are still being written.  Starting TLS now
                # will do the wrong thing.  Instead, mark that we're trying
                # to go into the TLS state.
                self._tlsWaiting = _TLSDelayed([], ctx, extra)
                return False

            self.stopReading()
            self.stopWriting()
            self._startTLS()
            self.socket = SSL.Connection(ctx.getContext(), self.socket)
            self.fileno = self.socket.fileno
            self.startReading()
            return True


        def _startTLS(self):
            self.TLS = 1
            self.__class__ = _getTLSClass(self.__class__)


        def write(self, bytes):
            if self._tlsWaiting is not None:
                self._tlsWaiting.bufferedData.append(bytes)
            else:
                abstract.FileDescriptor.write(self, bytes)


        def writeSequence(self, iovec):
            if self._tlsWaiting is not None:
                self._tlsWaiting.bufferedData.extend(iovec)
            else:
                abstract.FileDescriptor.writeSequence(self, iovec)


        def doWrite(self):
            result = abstract.FileDescriptor.doWrite(self)
            if self._tlsWaiting is not None:
                if not self.dataBuffer and not self._tempDataBuffer:
                    waiting = self._tlsWaiting
                    self._tlsWaiting = None
                    self.startTLS(waiting.context, waiting.extra)
                    self.writeSequence(waiting.bufferedData)
            return result


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
        """
        Write as much as possible of the given data to this TCP connection.

        This sends up to C{self.SEND_LIMIT} bytes from C{data}.  If the
        connection is lost, an exception is returned.  Otherwise, the number
        of bytes successfully written is returned.
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
        if Connection.startTLS(self, ctx, client):
            if client:
                self.socket.set_connect_state()
            else:
                self.socket.set_accept_state()


    def stopConnecting(self):
        """Stop attempt to connect."""
        self.failIfNotConnected(error.UserError())

    def failIfNotConnected(self, err):
        """
        Generic method called when the attemps to connect failed. It basically
        cleans everything it can: call connectionFailed, stop read and write,
        delete socket related members.
        """
        if (self.connected or self.disconnected or
            not hasattr(self, "connector")):
            return

        self.connector.connectionFailed(failure.Failure(err))
        if hasattr(self, "reactor"):
            # this doesn't happen if we failed in __init__
            self.stopReading()
            self.stopWriting()
            del self.connector

        try:
            self._closeSocket()
        except AttributeError:
            pass
        else:
            del self.socket, self.fileno

    def createInternetSocket(self):
        """(internal) Create a non-blocking socket using
        self.addressFamily, self.socketType.
        """
        s = socket.socket(self.addressFamily, self.socketType)
        s.setblocking(0)
        fdesc._setCloseOnExec(s.fileno())
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

        err = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if err:
            self.failIfNotConnected(error.getConnectError((err, strerror(err))))
            return


        # doConnect gets called twice.  The first time we actually need to
        # start the connection attempt.  The second time we don't really
        # want to (SO_ERROR above will have taken care of any errors, and if
        # it reported none, the mere fact that doConnect was called again is
        # sufficient to indicate that the connection has succeeded), but it
        # is not /particularly/ detrimental to do so.  This should get
        # cleaned up some day, though.
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
                self.failIfNotConnected(error.getConnectError((connectResult, strerror(connectResult))))
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
        self.logstr = self.protocol.__class__.__name__ + ",client"
        self.startReading()
        self.protocol.makeConnection(self)

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
        return address.IPv4Address('TCP', *self.socket.getsockname())

    def getPeer(self):
        """Returns an IPv4Address.

        This indicates the address that I am connected to.
        """
        return address.IPv4Address('TCP', *self.realAddress)

    def __repr__(self):
        s = '<%s to %s at %x>' % (self.__class__, self.addr, unsignedID(self))
        return s


class Server(Connection):
    """
    Serverside socket-stream connection class.

    This is a serverside network connection transport; a socket which came from
    an accept() on a server.
    """

    def __init__(self, sock, protocol, client, server, sessionno, reactor):
        """
        Server(sock, protocol, client, server, sessionno)

        Initialize it with a socket, a protocol, a descriptor for my peer (a
        tuple of host, port describing the other end of the connection), an
        instance of Port, and a session number.
        """
        Connection.__init__(self, sock, protocol, reactor)
        self.server = server
        self.client = client
        self.sessionno = sessionno
        self.hostname = client[0]
        self.logstr = "%s,%s,%s" % (self.protocol.__class__.__name__,
                                    sessionno,
                                    self.hostname)
        self.repstr = "<%s #%s on %s>" % (self.protocol.__class__.__name__,
                                          self.sessionno,
                                          self.server._realPortNumber)
        self.startReading()
        self.connected = 1

    def __repr__(self):
        """A string representation of this connection.
        """
        return self.repstr

    def startTLS(self, ctx, server=1):
        if Connection.startTLS(self, ctx, server):
            if server:
                self.socket.set_accept_state()
            else:
                self.socket.set_connect_state()


    def getHost(self):
        """Returns an IPv4Address.

        This indicates the server's address.
        """
        return address.IPv4Address('TCP', *self.socket.getsockname())

    def getPeer(self):
        """Returns an IPv4Address.

        This indicates the client's address.
        """
        return address.IPv4Address('TCP', *self.client)



class Port(base.BasePort, _SocketCloser):
    """
    A TCP server port, listening for connections.

    When a connection is accepted, this will call a factory's buildProtocol
    with the incoming address as an argument, according to the specification
    described in L{twisted.internet.interfaces.IProtocolFactory}.

    If you wish to change the sort of transport that will be used, the
    C{transport} attribute will be called with the signature expected for
    C{Server.__init__}, so it can be replaced.

    @ivar deferred: a deferred created when L{stopListening} is called, and
        that will fire when connection is lost. This is not to be used it
        directly: prefer the deferred returned by L{stopListening} instead.
    @type deferred: L{defer.Deferred}

    @ivar disconnecting: flag indicating that the L{stopListening} method has
        been called and that no connections should be accepted anymore.
    @type disconnecting: C{bool}

    @ivar connected: flag set once the listen has successfully been called on
        the socket.
    @type connected: C{bool}
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
        self.connected = True
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
                        # Netfilter on Linux may have rejected the
                        # connection, but we get told to try to accept()
                        # anyway.
                        continue
                    elif e.args[0] in (EMFILE, ENOBUFS, ENFILE, ENOMEM, ECONNABORTED):

                        # Linux gives EMFILE when a process is not allowed
                        # to allocate any more file descriptors.  *BSD and
                        # Win32 give (WSA)ENOBUFS.  Linux can also give
                        # ENFILE if the system is out of inodes, or ENOMEM
                        # if there is insufficient memory to allocate a new
                        # dentry.  ECONNABORTED is documented as possible on
                        # both Linux and Windows, but it is not clear
                        # whether there are actually any circumstances under
                        # which it can happen (one might expect it to be
                        # possible if a client sends a FIN or RST after the
                        # server sends a SYN|ACK but before application code
                        # calls accept(2), however at least on Linux this
                        # _seems_ to be short-circuited by syncookies.

                        log.msg("Could not accept new connection (%s)" % (
                            errorcode[e.args[0]],))
                        break
                    raise

                fdesc._setCloseOnExec(skt.fileno())
                protocol = self.factory.buildProtocol(self._buildAddr(addr))
                if protocol is None:
                    skt.close()
                    continue
                s = self.sessionno
                self.sessionno = s+1
                transport = self.transport(skt, protocol, addr, self, s, self.reactor)
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
        """
        Stop accepting connections on this port.

        This will shut down the socket and call self.connectionLost().  It
        returns a deferred which will fire successfully when the port is
        actually closed, or with a failure if an error occurs shutting down.
        """
        self.disconnecting = True
        self.stopReading()
        if self.connected:
            self.deferred = deferLater(
                self.reactor, 0, self.connectionLost, connDone)
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

        base.BasePort.connectionLost(self, reason)
        self.connected = False
        self._closeSocket()
        del self.socket
        del self.fileno

        try:
            self.factory.doStop()
        finally:
            self.disconnecting = False


    def logPrefix(self):
        """Returns the name of my class, to prefix log entries with.
        """
        return reflect.qual(self.factory.__class__)

    def getHost(self):
        """Returns an IPv4Address.

        This indicates the server's address.
        """
        return address.IPv4Address('TCP', *self.socket.getsockname())

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
        return address.IPv4Address('TCP', self.host, self.port)
