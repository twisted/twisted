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

if not hasattr(socket, 'AF_UNIX'):
    raise ImportError, "UNIX sockets not supported on this platform"

# Twisted imports
from twisted.internet import base, tcp, error
from twisted.internet.error import CannotListenError
from twisted.python import log
from twisted.python.compat import *

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
