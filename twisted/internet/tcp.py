
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

if os.name == 'nt':
    EINVAL      = 10022
    EWOULDBLOCK = 10035
    EINPROGRESS = 10036
    EALREADY    = 10037
    ECONNRESET  = 10054
    EISCONN     = 10056
    ENOTCONN    = 10057
elif os.name != 'java':
    from errno import EINVAL
    from errno import EWOULDBLOCK
    from errno import EINPROGRESS
    from errno import EALREADY
    from errno import ECONNRESET
    from errno import EISCONN
    from errno import ENOTCONN

# Twisted Imports
from twisted.internet import protocol
from twisted.persisted import styles
from twisted.python import log, failure, reflect
from twisted.python.runtime import platform
from twisted.internet.error import CannotListenError
from twisted.internet.interfaces import IConnector
from twisted.internet import defer

# Sibling Imports
import abstract
import main
import interfaces
import error


class Connection(abstract.FileDescriptor, styles.Ephemeral):
    """I am the superclass of all socket-based FileDescriptors.

    This is an abstract superclass of all objects which represent a TCP/IP
    connection based socket.
    """

    __implements__ = abstract.FileDescriptor.__implements__, interfaces.ITCPTransport

    def __init__(self, skt, protocol, reactor=None):
        abstract.FileDescriptor.__init__(self, reactor=reactor)
        self.socket = skt
        self.socket.setblocking(0)
        self.fileno = skt.fileno
        self.protocol = protocol

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
            return main.CONNECTION_LOST
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
            if se.args[0] == EWOULDBLOCK:
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


class BaseClient(Connection):
    """A base class for client TCP (and similiar) sockets.
    """

    def _finishInit(self, whenDone, skt, error, reactor):
        """Called by base classes to continue to next stage of initialization."""
        if whenDone:
            Connection.__init__(self, skt, None, reactor)
            self.doWrite = self.doConnect
            self.doRead = self.doConnect
            reactor.callLater(0, whenDone)
        else:
            reactor.callLater(0, self.failIfNotConnected, error)

    def stopConnecting(self):
        """Stop attempt to connect."""
        self.failIfNotConnected(error.UserError())

    def failIfNotConnected(self, err):
        if (self.connected or
            self.disconnected or
            not (hasattr(self, "connector"))):
            return
        # XXX workaround for sillines in reactor.resolve()
        if err == "address not found":
            err = error.UnknownHostError()
        self.connector.connectionFailed(failure.Failure(err))
        if hasattr(self, "reactor"):
            # this doesn't happens if we failed in __init__
            self.stopReading()
            self.stopWriting()
            del self.connector

    def createInternetSocket(self):
        """(internal) Create an AF_INET socket.
        """
        # factored out so as to minimise the code necessary for SecureClient
        return socket.socket(socket.AF_INET,socket.SOCK_STREAM)

    def resolveAddress(self):
        if abstract.isIPAddress(self.addr[0]):
            self._setRealAddress(self.addr[0])
        else:
            self.reactor.resolve(self.addr[0]
                            ).addCallbacks(
                self._setRealAddress, self.failIfNotConnected
                )

    def _setRealAddress(self, address):
        self.realAddress = (address, self.addr[1])
        self.doConnect()

    def doConnect(self):
        """I connect the socket.

        Then, call the protocol's makeConnection, and start waiting for data.
        """
        if platform.getType() == "win32":
            r, w, e = select.select([], [], [self.fileno()], 0.0)
            if e:
                self.failIfNotConnected(error.getConnectError(e))
                return

        try:
            self.socket.connect(self.realAddress)
        except socket.error, se:
            if se.args[0] == EISCONN:
                pass
            elif se.args[0] in (EWOULDBLOCK, EINVAL, EINPROGRESS, EALREADY):
                self.startReading()
                self.startWriting()
                return
            else:
                self.failIfNotConnected(error.getConnectError(se))
                return
        # If I have reached this point without raising or returning, that means
        # that the socket is connected.
        del self.doWrite
        del self.doRead
        self.connected = 1
        # we first stop and then start, to reset any references to the old doRead
        self.stopReading()
        self.stopWriting()
        self.startReading()
        self.protocol = self.connector.buildProtocol(self.getPeer())
        self.protocol.makeConnection(self)
        self.logstr = self.protocol.__class__.__name__+",client"

    def connectionLost(self, reason):
        if not self.connected:
            self.failIfNotConnected(error.ConnectError())
        else:
            Connection.connectionLost(self, reason)
            self.connector.connectionLost(reason)

    def getHost(self):
        """Returns a tuple of ('INET', hostname, port).

        This indicates the address from which I am connecting.
        """
        return ('INET',)+self.socket.getsockname()

    def getPeer(self):
        """Returns a tuple of ('INET', hostname, port).

        This indicates the address that I am connected to.  I implement
        twisted.protocols.protocol.Transport.
        """
        return ('INET',)+self.addr

    def __repr__(self):
        s = '<%s to %s at %x>' % (self.__class__, self.addr, id(self))
        return s


class UNIXClient(BaseClient):
    """A client for Unix sockets."""

    def __init__(self, filename, connector, reactor=None):
        self.connector = connector
        err = None
        whenDone = None
        skt = None

        try:
            mode = os.stat(filename)[0]
        except OSError, ose:
            # no such file or directory
            whenDone = None
            err = error.BadFileError(string="No such file or directory")
        else:
            if not (mode & (stat.S_IFSOCK |  # that's not a socket
                            stat.S_IROTH  |  # that's not readable
                            stat.S_IWOTH )): # that's not writable
                whenDone = None
                err = error.BadFileError(string="File is not socket or unreadable/unwritable")
            else:
                # success.
                self.realAddress = self.addr = filename
                # we are using unix sockets
                skt = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                whenDone = self.doConnect

        self._finishInit(whenDone, skt, err, reactor)

    def getPeer(self):
        return ('UNIX', self.addr)

    def getHost(self):
        return ('UNIX', )

class TCPClient(BaseClient):
    """A TCP client."""

    def __init__(self, host, port, bindAddress, connector, reactor=None):
        self.connector = connector
        skt = self.createInternetSocket()
        self.addr = (host, port)
        whenDone = self.resolveAddress
        err = None
        # try to bind to given address
        if bindAddress is not None:
            try:
                skt.bind(bindAddress)
            except socket.error, se:
                err = error.ConnectBindError(se[0], se[1])
                whenDone = None
        self._finishInit(whenDone, skt, err, reactor)


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
        try:
            self.hostname = client[0]
        except:
            self.hostname = 'unix'
        self.logstr = "%s,%s,%s" % (self.protocol.__class__.__name__, sessionno, self.hostname)
        self.repstr = "<%s #%s on %s>" % (self.protocol.__class__.__name__, self.sessionno, self.server.port)
        self.startReading()
        self.connected = 1

    def __repr__(self):
        """A string representation of this connection.
        """
        return self.repstr

    def getHost(self):
        """Returns a tuple of ('INET', hostname, port).

        This indicates the servers address.
        """
        return ('INET',)+self.socket.getsockname()

    def getPeer(self):
        """
        Returns a tuple of ('INET', hostname, port), indicating the connected
        client's address.
        """
        # ick someone clean this up someday
        if isinstance(self.client, types.TupleType):
            return ('INET',)+self.client
        else:
            return ("INET", self.client)


class Port(abstract.FileDescriptor):
    """I am a TCP server port, listening for connections.

    When a connection is accepted, I will call my factory's buildProtocol with
    the incoming connection as an argument, according to the specification
    described in twisted.protocols.protocol.Factory.

    If you wish to change the sort of transport that will be used, my
    `transport' attribute will be called with the signature expected for
    Server.__init__, so it can be replaced.
    """

    transport = Server
    sessionno = 0
    unixsocket = None
    interface = ''
    backlog = 5

    def __init__(self, port, factory, backlog=5, interface='', reactor=None):
        """Initialize with a numeric port to listen on.
        """
        abstract.FileDescriptor.__init__(self, reactor=reactor)
        self.port = port
        self.factory = factory
        self.backlog = backlog
        self.interface = interface

    def __repr__(self):
        return "<%s on %s>" % (self.factory.__class__, self.port)

    def createInternetSocket(self):
        """(internal) create an AF_INET socket.
        """
        s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        return s

    def __getstate__(self):
        """(internal) get my state for persistence
        """
        dct = self.__dict__.copy()
        try: del dct['socket']
        except: pass
        try: del dct['fileno']
        except: pass

        return dct

    def startListening(self):
        """Create and bind my socket, and begin listening on it.

        This is called on unserialization, and must be called after creating a
        server to begin listening on the specified port.
        """
        log.msg("%s starting on %s"%(self.factory.__class__, self.port))
        self.factory.doStart()
        if type(self.port) == types.StringType:
            skt = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                skt.bind(self.port)
            except socket.error, le:
                raise CannotListenError, (self.interface, self.port, le,)
            # Make the socket readable and writable to the world.
            os.chmod(self.port, 0666)
            self.unixsocket = 1
        else:
            skt = self.createInternetSocket()
            try:
                skt.bind((self.interface, self.port))
            except socket.error, le:
                raise CannotListenError, (self.interface, self.port, le)
        skt.setblocking(0)
        skt.listen(self.backlog)
        self.connected = 1
        self.socket = skt
        self.fileno = self.socket.fileno
        self.numberAccepts = 100
        self.startReading()

    def doRead(self):
        """Called when my socket is ready for reading.

        This accepts a connection and calls self.protocol() to handle the
        wire-level protocol.
        """
        try:
            if os.name == "posix":
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
                    skt,addr = self.socket.accept()
                except socket.error, e:
                    if e.args[0] == EWOULDBLOCK:
                        self.numberAccepts = i
                        break
                    raise
                protocol = self.factory.buildProtocol(addr)
                if protocol is None:
                    skt.close()
                    continue
                s = self.sessionno
                self.sessionno = s+1
                transport = self.transport(skt, protocol, addr, self, s)
                protocol.makeConnection(transport)
            else:
                self.numberAccepts = self.numberAccepts+20
        except:
            log.deferr()

    def doWrite(self):
        """Raises an AssertionError.
        """
        raise RuntimeError, "doWrite called on a %s" % reflect.qual(self.__class__)

    def loseConnection(self):
        """Stop accepting connections on this port.

        This will shut down my socket and call self.connectionLost().
        """
        self.disconnecting = 1
        self.stopReading()
        if self.connected:
            self.reactor.callLater(0, self.connectionLost,
                                   failure.Failure(main.CONNECTION_DONE))

    stopListening = loseConnection

    def connectionLost(self, reason):
        """Cleans up my socket.
        """
        log.msg('(Port %s Closed)' % self.port)
        abstract.FileDescriptor.connectionLost(self, reason)
        self.connected = 0
        self.socket.close()
        if self.unixsocket:
            os.unlink(self.port)
        del self.socket
        del self.fileno
        self.factory.doStop()

    def logPrefix(self):
        """Returns the name of my class, to prefix log entries with.
        """
        return reflect.qual(self.factory.__class__)

    def getHost(self):
        """Returns a tuple of ('INET', hostname, port).

        This indicates the servers address.
        """
        return ('INET',)+self.socket.getsockname()
