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
End users should only use the ContextFactory classes directly - for SSL
connections use the reactor.connectSSL/listenSSL and so on, as documented
in IReactorSSL.

All server context factories should inherit from ContextFactory, and all
client context factories should inherit from ClientContextFactory. At the
moment this is not enforced, but in the future it might be.

API Stability: stable

Future Plans: 
    - split module so reactor-specific classes are in a separate module 
    - support for switching TCP into SSL
    - more options

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

# System imports
from OpenSSL import SSL
import socket

# sibling imports
import tcp, main, interfaces

# Twisted imports
from twisted.python import log


class ContextFactory:
    """A factory for SSL context objects, for server SSL connections."""

    isClient = 0
    
    def getContext(self):
        """Return a SSL.Context object. override in subclasses."""
        raise NotImplementedError


class DefaultOpenSSLContextFactory(ContextFactory):

    def __init__(self, privateKeyFileName, certificateFileName,
                 sslmethod=SSL.SSLv23_METHOD):
        self.privateKeyFileName = privateKeyFileName
        self.certificateFileName = certificateFileName
        self.sslmethod = sslmethod
        self.cacheContext()

    def cacheContext(self):
        ctx = SSL.Context(self.sslmethod)
        ctx.use_certificate_file(self.certificateFileName)
        ctx.use_privatekey_file(self.privateKeyFileName)
        self._context = ctx

    def __getstate__(self):
        d = self.__dict__.copy()
        del d['_context']
        return d

    def __setstate__(self, state):
        self.__dict__ = state
        self.cacheContext()

    def getContext(self):
        """Create an SSL context.
        """
        return self._context


class ClientContextFactory:
    """A context factory for SSL clients."""

    isClient = 1
    
    def getContext(self):
        return SSL.Context(SSL.SSLv3_METHOD)


class Connection(tcp.Connection):
    """I am an SSL connection.
    """

    __implements__ = tcp.Connection.__implements__, interfaces.ISSLTransport
    
    writeBlockedOnRead = 0
    readBlockedOnWrite= 0
    sslShutdown = 0
    
    def getPeerCertificate(self):
        """Return the certificate for the peer."""
        return self.socket.get_peer_certificate()

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
            return main.CONNECTION_LOST
        if done:
            return main.CONNECTION_DONE
        else:
            # we wait for other side to close SSL connection -
            # this will be signaled by SSL.ZeroReturnError when reading
            # from the socket
            self.stopWriting()
            self.startReading()
            return None # don't close socket just yet
    
    def doRead(self):
        """See tcp.Connection.doRead for details.
        """
        if self.writeBlockedOnRead:
            self.writeBlockedOnRead = 0
            return self.doWrite()
        try:
            return tcp.Connection.doRead(self)
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
            return main.CONNECTION_LOST

    def doWrite(self):
        if self.readBlockedOnWrite:
            self.readBlockedOnWrite = 0
            if not self.unsent: self.stopWriting()
            return self.doRead()
        return tcp.Connection.doWrite(self)
    
    def writeSomeData(self, data):
        """See tcp.Connection.writeSomeData for details.
        """
        if not data:
            return 0

        try:
            return tcp.Connection.writeSomeData(self, data)
        except SSL.WantWriteError:
            return 0
        except SSL.WantReadError:
            self.writeBlockedOnRead = 1
            return 0
        except SSL.Error:
            return main.CONNECTION_LOST

    def _closeSocket(self):
        """Called to close our socket."""
        try:
            self.socket.sock_shutdown(2)
        except socket.error:
            pass



class Client(Connection, tcp.TCPClient):
    """I am an SSL client.
    """
    
    def __init__(self, host, port, bindAddress, ctxFactory, connector, reactor=None):
        self.ctxFactory = ctxFactory
        tcp.TCPClient.__init__(self, host, port, bindAddress, connector, reactor)
    
    def createInternetSocket(self):
        """(internal) create an SSL socket
        """
        sock = tcp.TCPClient.createInternetSocket(self)
        return SSL.Connection(self.ctxFactory.getContext(), sock)

    def getHost(self):
        """Returns a tuple of ('SSL', hostname, port).

        This indicates the address from which I am connecting.
        """
        return ('SSL',)+self.socket.getsockname()

    def getPeer(self):
        """Returns a tuple of ('SSL', hostname, port).

        This indicates the address that I am connected to.  I implement
        twisted.protocols.protocol.Transport.
        """
        return ('SSL',)+self.addr



class Server(Connection, tcp.Server):
    """I am an SSL server.
    """
    
    def __init__(*args, **kwargs):
        # we need those so we don't use ssl.Connection's __init__
        apply(tcp.Server.__init__, args, kwargs)

    def getHost(self):
        """Returns a tuple of ('SSL', hostname, port).

        This indicates the servers address.
        """
        return ('SSL',)+self.socket.getsockname()

    def getPeer(self):
        """
        Returns a tuple of ('SSL', hostname, port), indicating the connected
        client's address.
        """
        return ('SSL',)+self.client



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
                skt, addr = self.socket.accept()
            except socket.error, e:
                if e.args[0] == tcp.EWOULDBLOCK:
                    return
                raise
            except SSL.Error:
                log.deferr()
                return
            protocol = self.factory.buildProtocol(addr)
            if protocol is None:
                skt.close()
                return
            s = self.sessionno
            self.sessionno = s+1
            transport = self.transport(skt, protocol, addr, self, s)
            protocol.makeConnection(transport)
        except:
            log.deferr()


__all__ = ["ContextFactory", "DefaultOpenSSLContextFactory", "ClientContextFactory"]
