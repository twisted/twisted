
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
"""


# System Imports
import os
import stat
import types
import copy
import socket
import sys
import string
import select

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
from twisted.protocols import protocol
from twisted.persisted import styles
from twisted.python import log, defer
from twisted.python.runtime import platform

from twisted.internet.interfaces import IConnector
# Sibling Imports
import abstract
import main


class Connection(abstract.FileDescriptor,
                 protocol.Transport,
                 styles.Ephemeral):
    """I am the superclass of all socket-based FileDescriptors.

    This is an abstract superclass of all objects which represent a TCP/IP
    connection based socket.
    """
    def __init__(self, skt, protocol):
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

    def connectionLost(self):
        """See abstract.FileDescriptor.connectionLost().
        """
        abstract.FileDescriptor.connectionLost(self)
        # This used to close() the socket, but that doesn't *really* close it if
        # there's another reference to it in the TCP/IP stack, e.g. if it was
        # was inherited by a subprocess. And we really do want to close the
        # connection.
        try:
            self.socket.shutdown(2)
        except socket.error:
            pass
        protocol = self.protocol
        del self.protocol
        del self.socket
        del self.fileno
        protocol.connectionLost()

    logstr = "Uninitialized"

    def logPrefix(self):
        """Return the prefix to log with when I own the logging thread.
        """
        return self.logstr


class Client(Connection):
    """A client for TCP (and similiar) sockets.
    """
    def __init__(self, host, port, protocol, timeout=None, connector=None, reactor=None):
        """Initialize the client, setting up its socket, and request to connect.
        """
        if reactor is None:
            from twisted.internet import reactor
        self.reactor = reactor
        if host == 'unix':
            # "port" in this case is really a filename
            try:
                mode = os.stat(port)[0]
            except OSError, ose:
                # no such file or directory
                whenDone = None
            else:
                if not (mode & (stat.S_IFSOCK |  # that's not a socket
                                stat.S_IROTH  |  # that's not readable
                                stat.S_IWOTH )):# that's not writable
                    whenDone = None
                else:
                    # success.
                    self.realAddress = self.addr = port
                    # we are using unix sockets
                    skt = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    whenDone = self.doConnect
        else:
            skt = self.createInternetSocket()
            self.addr = (host, port)
            whenDone = self.resolveAddress
        if whenDone:
            self.host = host
            self.port = port
            self.connector = connector
            Connection.__init__(self, skt, protocol)
            self.doWrite = self.doConnect
            self.doRead = self.doConnect
            self.logstr = self.protocol.__class__.__name__+",client"
            # slightly cheezy -- deferreds in pb expect you to go through a
            # mainloop before you actually connect them.  connecting immediately
            # screws up that logic.
            self.reactor.callLater(0, whenDone)
            if timeout is not None:
                self.reactor.callLater(timeout, self.failIfNotConnected)
        else:
            self.reactor.callLater(0, protocol.connectionFailed)

    def failIfNotConnected(self, *ignored):
        # print 'failing if not connected'
        if (not self.connected) and (not self.disconnected):
            if self.connector:
                self.connector.connectionFailed()
            self.protocol.connectionFailed()
            self.stopReading()
            self.stopWriting()

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
                ).arm()

    def _setRealAddress(self, address):
        # print 'real address:',repr(address),repr(self.addr)
        self.realAddress = (address, self.addr[1])
        self.doConnect()

    def doConnect(self):
        """I connect the socket.

        Then, call the protocol's makeConnection, and start waiting for data.
        """
        if platform.getType() == "win32":
            r, w, e = select.select([], [], [self.fileno()], 0.0)
            if e:
                self.protocol.connectionFailed()
                self.stopReading()
                self.stopWriting()
                return

        try:
            self.socket.connect(self.realAddress)
        except socket.error, se:
            if se.args[0] in (EISCONN, EALREADY):
                pass
            elif se.args[0] in (EWOULDBLOCK, EINVAL, EINPROGRESS):
                self.startReading()
                self.startWriting()
                return
            else:
                self.protocol.connectionFailed()
                self.stopReading()
                self.stopWriting()
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
        self.protocol.makeConnection(self)

    def connectionLost(self):
        if not self.connected:
            self.failIfNotConnected()
        else:
            Connection.connectionLost(self)
            if self.connector:
                self.connector.connectionLost()

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



class Connector:
    """Connect a protocol to a server using TCP and if it fails make a new one."""

    transportFactory = Client
    protocol = None

    __implements__ = [IConnector]

    def __init__(self, host, portno, protocolFactory, timeout=30):
        self.host = host
        self.portno = portno
        self.factory = protocolFactory
        self.timeout = timeout

    def connectionFailed(self):
        self.startConnecting()

    def connectionLost(self):
        self.connectionFailed()

    def startConnecting(self):
        proto = self.factory.buildProtocol((self.host, self.portno))
        self.transportFactory(self.host, self.portno, proto, self.timeout, self)
        self.protocol = proto

    def getProtocol(self):
        """Get the current protocol instance."""
        return self.protocol

    def __getstate__(self):
        state = self.__dict__.copy()
        if state.has_key('protocol'):
            del state['protocol']
        return state


class Server(Connection):
    """Serverside socket-stream connection class.

    I am a serverside network connection transport; a socket which came from an
    accept() on a server.  Programmers for the twisted.net framework should not
    have to use me directly, since I am automatically instantiated in
    TCPServer's doRead method.  For documentation on what I do, refer to the
    documentation for twisted.protocols.protocol.Transport.
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
        return ('INET',)+self.client

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
        self.port = port
        self.factory = factory
        self.backlog = backlog
        self.interface = interface
        if reactor is None:
            from twisted.internet import reactor
        self.reactor = reactor

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
        dct = copy.copy(self.__dict__)
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
        if type(self.port) == types.StringType:
            skt = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            skt.bind(self.port)
            # Make the socket readable and writable to the world.
            os.chmod(self.port, 0666)
            self.unixsocket = 1
        else:
            skt = self.createInternetSocket()
            skt.bind((self.interface, self.port))
        skt.setblocking(0)
        skt.listen(self.backlog)
        self.connected = 1
        self.socket = skt
        self.fileno = self.socket.fileno
        self.numberAccepts = 100
        self.startReading()

    def doRead(self):
        """Called when my socket is ready for reading.

        This accepts a connection and callse self.protocol() to handle the
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
                protocol.makeConnection(transport, self)
            else:
                self.numberAccepts = self.numberAccepts+20
        except:
            log.deferr()

    def doWrite(self):
        """Raises an AssertionError.
        """
        raise RuntimeError, "doWrite called on a %s" % str(self.__class__)

    def loseConnection(self):
        """ Stop accepting connections on this port.

        This will shut down my socket and call self.connectionLost().
        """
        self.disconnecting = 1
        self.stopReading()
        if self.connected:
            self.reactor.callLater(0, self.connectionLost)

    stopListening = loseConnection

    def connectionLost(self):
        """Cleans up my socket.
        """
        log.msg('(Port %s Closed)' % self.port)
        abstract.FileDescriptor.connectionLost(self)
        self.connected = 0
        self.socket.close()
        if self.unixsocket:
            os.unlink(self.port)
        del self.socket
        del self.fileno
        self.factory.stopFactory()

    def logPrefix(self):
        """Returns the name of my class, to prefix log entries with.
        """
        return str(self.factory.__class__)

    def getHost(self):
        """Returns a tuple of ('INET', hostname, port).

        This indicates the servers address.
        """
        return ('INET',)+self.socket.getsockname()
