
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

"""SSL transport. Requires PyOpenSSL (http://pyopenssl.sf.net).

SSL connections require a ContextFactory so they can create SSL contexts.
"""

# System imports
from OpenSSL import SSL
import socket
import traceback


# sibling imports
import tcp, main


class ContextFactory:
    """A factory for SSL context objects."""
    
    def getContext(self):
        """Return a SSL.Context object. override in subclasses."""
        raise NotImplementedError


class ClientContextFactory(ContextFactory):
    """A sample context factory for SSL clients."""
    
    def getContext(self):
        return SSL.Context(SSL.SSLv23_METHOD)


class Connection(tcp.Connection):
    """I am an SSL connection.
    """
    
    def doRead(self):
        """See tcp.Connection.doRead for details.
        """
        try:
            return tcp.Connection.doRead(self)
        except SSL.WantReadError:
            # redo command with same arguments
            return self.doRead()
        except (SSL.ZeroReturnError, SSL.SysCallError):
            return main.CONNECTION_LOST
    
    def writeSomeData(self, data):
        """See tcp.Connection.writeSomeData for details.
        """
        try:
            return tcp.Connection.writeSomeData(self, data)
        except SSL.WantWriteError:
            # redo command with same arguments
            return self.writeSomeData(data)
        except (SSL.ZeroReturnError, SSL.SysCallError):
            return main.CONNECTION_LOST

    def connectionLost(self):
        """See tcp.Connection.connectionLost for details.
        """
        # do the SSL shutdown exchange, before we close the underlying socket
        try:
            self.socket.shutdown()
        except SSL.Error:
            pass
        tcp.Connection.connectionLost(self)


class Client(Connection, tcp.Client):
    """I am an SSL client.
    """
    
    def __init__(self, host, port, protocol, ctxFactory, timeout=None):
        self.ctxFactory = ctxFactory
        apply(tcp.Client.__init__, (self, host, port, protocol), {'timeout': timeout})
    
    def createInternetSocket(self):
        """(internal) create an SSL socket
        """
        sock = tcp.Client.createInternetSocket(self)
        return SSL.Connection(self.ctxFactory.getContext(), sock)


class Server(Connection, tcp.Server):
    """I am an SSL server.
    """
    
    def __init__(*args, **kwargs):
        # we need those so we don't use ssl.Connection's __init__
        apply(tcp.Server.__init__, args, kwargs)


class Port(tcp.Port):
    """I am an SSL port.
    """
    
    transport = Server
    
    def __init__(self, port, factory, ctxFactory, backlog=5, interface=''):
        self.ctxFactory = ctxFactory
        apply(tcp.Port.__init__, (self, port, factory), {'backlog': backlog, 'interface': interface})
    
    def createInternetSocket(self):
        """(internal) create an SSL socket
        """
        sock = tcp.Port.createInternetSocket(self)
        return SSL.Connection(self.ctxFactory.getContext(), sock)
    
    def doRead(self):
        """Called when my socket is ready for reading.

        This accepts a connection and callse self.protocol() to handle the
        wire-level protocol.
        """
        try:
            try:
                skt,addr = self.socket.accept()
            except socket.error, e:
                if e.args[0] == EWOULDBLOCK:
                    return
                raise
            except SSL.Error:
                return
            protocol = self.factory.buildProtocol(addr)
            s = self.sessionno
            self.sessionno = s+1
            transport = self.transport(skt, protocol, addr, self, s)
            protocol.makeConnection(transport, self)
        except:
            traceback.print_exc(file=log.logfile)
