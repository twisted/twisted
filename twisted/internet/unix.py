# -*- test-case-name: twisted.test.test_unix -*-

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

# System imports
import os, stat, socket
from errno import *

if not hasattr(socket, 'AF_UNIX'):
    raise ImportError, "UNIX sockets not supported on this platform"

# Twisted imports
from twisted.internet import base, tcp, udp, error, interfaces, protocol
from twisted.internet.error import CannotListenError
from twisted.python import log, reflect, failure

class Server(tcp.Server):
    def __init__(self, sock, protocol, client, server, sessionno):
        tcp.Server.__init__(self, sock, protocol, (client, None), server, sessionno)

    def getHost(self):
        return ('UNIX', self.socket.getsockname())

    def getPeer(self):
        return ('UNIX', self.hostname)

class Port(tcp.Port):
    addressFamily = socket.AF_UNIX
    socketType = socket.SOCK_STREAM
    
    transport = Server

    def __init__(self, fileName, factory, backlog=5, mode=0666, reactor=None):
        tcp.Port.__init__(self, fileName, factory, backlog, reactor=reactor)
        self.mode = mode

    def __repr__(self):
        return '<%s on %r>' % (self.factory.__class__, self.port)

    def startListening(self):
        """Create and bind my socket, and begin listening on it.

        This is called on unserialization, and must be called after creating a
        server to begin listening on the specified port.
        """
        log.msg("%s starting on %r" % (self.factory.__class__, self.port))
        self.factory.doStart()
        try:
            skt = self.createInternetSocket()
            skt.bind(self.port)
        except socket.error, le:
            raise CannotListenError, (None, self.port, le)
        else:
            # Make the socket readable and writable to the world.
            os.chmod(self.port, self.mode)
            skt.listen(self.backlog)
            self.connected = True
            self.socket = skt
            self.fileno = self.socket.fileno
            self.numberAccepts = 100
            self.startReading()

    def connectionLost(self, reason):
        tcp.Port.connectionLost(self, reason)
        os.unlink(self.port)

    def getHost(self):
        """Returns a tuple of ('UNIX', fileName)

        This indicates the server's address.
        """
        return ('UNIX', self.socket.getsockname())


class Client(tcp.BaseClient):
    """A client for Unix sockets."""
    addressFamily = socket.AF_UNIX
    socketType = socket.SOCK_STREAM
    
    REQ_FLAGS = (stat.S_IFSOCK | # that's not a socket
                 stat.S_IRUSR  | # that's not readable
                 stat.S_IWUSR)   # that's not writable

    def __init__(self, filename, connector, reactor=None):
        # Base __init__ is invoked later.  Yea, it's evil.
        self.connector = connector
        err = skt = whenDone = None

        try:
            mode = os.stat(filename)[0]
        except OSError, ose:
            # no such file or directory
            err = error.BadFileError(string="No such file or directory")
        else:
            if (mode & self.REQ_FLAGS) != self.REQ_FLAGS:
                err = error.BadFileError(string="File is not socket or unreadable/unwritable")
            else:
                self.realAddress = self.addr = filename
                skt = self.createInternetSocket()
                whenDone = self.doConnect

        self._finishInit(whenDone, skt, err, reactor)

    def getPeer(self):
        return ('UNIX', self.addr)

    def getHost(self):
        return ('UNIX', )


class Connector(base.BaseConnector):
    def __init__(self, address, factory, timeout, reactor):
        base.BaseConnector.__init__(self, factory, timeout, reactor)
        self.address = address

    def _makeTransport(self):
        return Client(self.address, self, self.reactor)

    def getDestination(self):
        return ('UNIX', self.address)

class DatagramPort(udp.Port):
    """Datagram UNIX port, listening for packets."""

    __implements__ = base.BasePort.__implements__, interfaces.IUNIXDatagramTransport

    addressFamily = socket.AF_UNIX

    def __init__(self, addr, proto, maxPacketSize=8192, mode=0666, reactor=None):
        """Initialize with address to listen on.
        """
        udp.Port.__init__(self, addr, proto, maxPacketSize=maxPacketSize, reactor=reactor)
        self.mode = mode

    def _bindSocket(self):
        log.msg("%s starting on %s"%(self.protocol.__class__, self.port))
        try:
            skt = self.createInternetSocket() # XXX: haha misnamed method
            if self.port:
                skt.bind(self.port)
        except socket.error, le:
            raise error.CannotListenError, (None, self.port, le)
        if self.port:
            os.chmod(self.port, self.mode)
        self.connected = 1
        self.socket = skt
        self.fileno = self.socket.fileno

    def write(self, datagram, address):
        """Write a datagram."""
        try:
            return self.socket.sendto(datagram, address)
        except socket.error, se:
            no = se.args[0]
            if no == EINTR:
                return self.write(datagram, address)
            elif no == EMSGSIZE:
                raise error.MessageLengthError, "message too long"
            else:
                raise

    def setLogStr(self):
        self.logstr = reflect.qual(self.protocol.__class__) + " (UDP)"

    def getHost(self):
        """
        Returns a tuple of ('UNIX_DGRAM', address), indicating
        the servers address
        """
        return ('UNIX_DGRAM',)+self.socket.getsockname()

class ConnectedDatagramPort(DatagramPort):
    """A connected datagram UNIX socket."""

    __implements__ = base.BasePort.__implements__,  interfaces.IUNIXDatagramConnectedTransport

    def __init__(self, addr, proto, maxPacketSize=8192, mode=0666, bindAddress=None, reactor=None):
        assert isinstance(proto, protocol.ConnectedDatagramProtocol)
        DatagramPort.__init__(self, bindAddress, proto, maxPacketSize, mode, reactor)
        self.remoteaddr = addr

    def startListening(self):
        try:
            self._bindSocket()
            self.socket.connect(self.remoteaddr)
            self._connectToProtocol()
        except:
            self.connectionFailed(failure.Failure())

    def connectionFailed(self, reason):
        self.loseConnection()
        self.protocol.connectionFailed(reason)
        del self.protocol

    def doRead(self):
        """Called when my socket is ready for reading."""
        read = 0
        while read < self.maxThroughput:
            try:
                data, addr = self.socket.recvfrom(self.maxPacketSize)
                read += len(data)
                self.protocol.datagramReceived(data)
            except socket.error, se:
                no = se.args[0]
                if no in (EAGAIN, EINTR, EWOULDBLOCK):
                    return
                if (no == ECONNREFUSED) or (platformType == "win32" and no == WSAECONNRESET):
                    self.protocol.connectionRefused()
                else:
                    raise
            except:
                log.deferr()

    def write(self, data):
        """Write a datagram."""
        try:
            return self.socket.send(data)
        except socket.error, se:
            no = se.args[0]
            if no == EINTR:
                return self.write(data)
            elif no == EMSGSIZE:
                raise error.MessageLengthError, "message too long"
            elif no == ECONNREFUSED:
                self.protocol.connectionRefused()
            else:
                raise

    def getPeer(self):
        """
        Returns a tuple of ('UNIX_DGRAM', address), indicating
        the remote address.
        """
        return ('UNIX_DGRAM', self.remoteaddr)

