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
        return ('UNIX', repr(self.socket.getsockname()))

    def getPeer(self):
        return ('UNIX', repr(self.hostname))

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
        log.msg("%s starting on %r" % (self.factory.__class__, repr(self.port)))
        self.factory.doStart()
        try:
            skt = self.createInternetSocket()
            skt.bind(self.port)
        except socket.error, le:
            raise CannotListenError, (None, self.port, le)
        else:
            # Make the socket readable and writable to the world.
            try:
                os.chmod(self.port, self.mode)
            except: # probably not a visible filesystem name
                pass
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
        return ('UNIX', repr(self.socket.getsockname()))


class Client(tcp.BaseClient):
    """A client for Unix sockets."""
    addressFamily = socket.AF_UNIX
    socketType = socket.SOCK_STREAM
    
    def __init__(self, filename, connector, reactor=None):
        self.connector = connector
        self.realAddress = self.addr = filename
        self._finishInit(self.doConnect, self.createInternetSocket(),
                         None, reactor)

    def getPeer(self):
        return ('UNIX', repr(self.addr))

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
        log.msg("%s starting on %s"%(self.protocol.__class__, repr(self.port)))
        try:
            skt = self.createInternetSocket() # XXX: haha misnamed method
            if self.port:
                skt.bind(self.port)
        except socket.error, le:
            raise error.CannotListenError, (None, self.port, le)
        if self.port:
            try:
                os.chmod(self.port, self.mode)
            except: # probably not a visible filesystem name
                pass
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
            elif no == EAGAIN:
                # oh, well, drop the data. The only difference from UDP
                # is that UDP won't ever notice.
                # TODO: add TCP-like buffering
                pass
            else:
                raise

    def connectionLost(self, reason=None):
        """Cleans up my socket.
        """
        log.msg('(Port %s Closed)' % repr(self.port))
        base.BasePort.connectionLost(self, reason)
        if hasattr(self, "protocol"):
            # we won't have attribute in ConnectedPort, in cases
            # where there was an error in connection process
            self.protocol.doStop()
        self.connected = 0
        self.socket.close()
        del self.socket
        del self.fileno

    def setLogStr(self):
        self.logstr = reflect.qual(self.protocol.__class__) + " (UDP)"

    def getHost(self):
        """
        Returns a tuple of ('UNIX_DGRAM', address), indicating
        the servers address
        """
        return ('UNIX_DGRAM',repr(self.socket.getsockname()))

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
                if no == ECONNREFUSED:
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
            elif no == EAGAIN:
                # oh, well, drop the data. The only difference from UDP
                # is that UDP won't ever notice.
                # TODO: add TCP-like buffering
                pass
            else:
                raise

    def getPeer(self):
        """
        Returns a tuple of ('UNIX_DGRAM', address), indicating
        the remote address.
        """
        return ('UNIX_DGRAM', repr(self.remoteaddr))

