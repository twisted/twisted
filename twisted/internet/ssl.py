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
from twisted.internet import base

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
    method = SSL.SSLv3_METHOD

    def getContext(self):
        return SSL.Context(self.method)


class Client(tcp.Client):
    """I am an SSL client."""
    def __init__(self, host, port, bindAddress, ctxFactory, connector, reactor=None):
        # tcp.Client.__init__ depends on self.ctxFactory being set
        self.ctxFactory = ctxFactory
        tcp.Client.__init__(self, host, port, bindAddress, connector, reactor)

    def getHost(self):
        """Returns a tuple of ('SSL', hostname, port).

        This indicates the address from which I am connecting.
        """
        return ('SSL',)+self.socket.getsockname()

    def getPeer(self):
        """Returns a tuple of ('SSL', hostname, port).

        This indicates the address that I am connected to.
        """
        return ('SSL',)+self.addr

    def _finishInit(self, whenDone, skt, error, reactor):
        tcp.Client._finishInit(self, whenDone, skt, error, reactor)
        self.startTLS(self.ctxFactory)


class Server(tcp.Server):
    """I am an SSL server.
    """
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
    """I am an SSL port."""
    transport = Server
    
    def __init__(self, port, factory, ctxFactory, backlog=5, interface='', reactor=None):
        tcp.Port.__init__(self, port, factory, backlog, interface, reactor)
        self.ctxFactory = ctxFactory
    
    def createInternetSocket(self):
        """(internal) create an SSL socket
        """
        sock = tcp.Port.createInternetSocket(self)
        return SSL.Connection(self.ctxFactory.getContext(), sock)

    def _preMakeConnection(self, transport):
        # *Don't* call startTLS here
        # The transport already has the SSL.Connection object from above
        transport._startTLS()
        return tcp.Port._preMakeConnection(self, transport)


class Connector(base.BaseConnector):
    def __init__(self, host, port, factory, contextFactory, timeout, bindAddress, reactor=None):
        self.host = host
        self.port = port
        self.bindAddress = bindAddress
        self.contextFactory = contextFactory
        base.BaseConnector.__init__(self, factory, timeout, reactor)

    def _makeTransport(self):
        return Client(self.host, self.port, self.bindAddress, self.contextFactory, self, self.reactor)

    def getDestination(self):
        return ('SSL', self.host, self.port)

__all__ = ["ContextFactory", "DefaultOpenSSLContextFactory", "ClientContextFactory"]
