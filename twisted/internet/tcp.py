
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
import traceback
import string

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
from twisted.python import log

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
            return main.CONNECTION_LOST

    def connectionLost(self):
        """See abstract.FileDescriptor.connectionLost().
        """
        abstract.FileDescriptor.connectionLost(self)
        self.socket.close()
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
    def __init__(self, host, port, protocol, timeout=None, connector=None):
        """Initialize the client, setting up its socket, and request to connect.
        """
        if host == 'unix':
            # "port" in this case is really a filename
            try:
                mode = os.stat(port)[0]
            except OSError, ose:
                protocol.connectionFailed()  # no such file or directory
                return
            if not (mode & (stat.S_IFSOCK |  # that's not a socket
                            stat.S_IROTH  |  # that's not readable
                            stat.S_IWOTH )):# that's not writable
                protocol.connectionFailed()
                return
            # success.
            self.realAddress = self.addr = port
            # we are using unix sockets
            skt = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            whenDone = self.doConnect
        else:
            skt = self.createInternetSocket()
            self.addr = (host, port)
            whenDone = self.resolveAddress
        self.host = host
        self.port = port
        self.connector = connector
        Connection.__init__(self, skt, protocol)
        self.doWrite = self.doConnect
        self.doRead = self.doConnect
        self.logstr = self.protocol.__class__.__name__+",client"
        whenDone()
        if timeout is not None:
            main.addTimeout(self.failIfNotConnected, timeout)

    def failIfNotConnected(self):
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
            main.resolver.resolve(self.addr[0],
                                  self._setRealAddress,
                                  self.failIfNotConnected)

    def _setRealAddress(self, address):
        # print 'real address:',repr(address),repr(self.addr)
        self.realAddress = (address, self.addr[1])
        self.doConnect()

    def doConnect(self):
        """I connect the socket.

        Then, call the protocol's makeConnection, and start waiting for data.
        """
        try:
            self.socket.connect(self.realAddress)
        except socket.error, se:
            if se.args[0] == EISCONN:
                pass
            elif se.args[0] in (EINPROGRESS, EWOULDBLOCK, EALREADY, EINVAL):
                self.startWriting()
                self.startReading()
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
        self.startReading()
        self.protocol.makeConnection(self)

    def connectionLost(self):
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
        self.startReading()
        self.connected = 1
        self.logstr = "%s,%s,%s" % (self.protocol.__class__.__name__, sessionno, self.hostname)
        self.repstr = "<%s #%s on %s>" % (self.protocol.__class__.__name__, self.sessionno, self.server.port)

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

    def __init__(self, port, factory, backlog=5, interface=''):
        """Initialize with a numeric port to listen on.
        """
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
            mode = os.stat(self.port)[0]
            os.chmod(self.port, mode | stat.S_IROTH | stat.S_IWOTH)
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
        self.factory.startFactory()

    def doRead(self):
        """Called when my socket is ready for reading.

        This accepts a connection and callse self.protocol() to handle the
        wire-level protocol.
        """
        try:
            for i in range(self.numberAccepts):
                try:
                    skt,addr = self.socket.accept()
                except socket.error, e:
                    if e.args[0] == EWOULDBLOCK:
                        self.numberAccepts = i
                        break
                    raise
                protocol = self.factory.buildProtocol(addr)
                s = self.sessionno
                self.sessionno = s+1
                transport = self.transport(skt, protocol, addr, self, s)
                protocol.makeConnection(transport, self)
            else:
                self.numberAccepts = self.numberAccepts+20
        except:
            traceback.print_exc(file=log.logfile)

    def doWrite(self):
        """Raises an AssertionError.
        """
        assert 0, "doWrite called on a %s" % str(self.__class__)

    def loseConnection(self):
        """ Stop accepting connections on this port.

        This will shut down my socket and call self.connectionLost().
        """
        # Since ports can't, by definition, write any data, we can just close
        # instantly (no need for the more complex stuff for selectables which
        # write)
        self.stopReading()
        self.connectionLost()

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
