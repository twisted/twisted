# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


import types, socket, operator

from twisted.internet.abstract import isIPAddress # would rather not import "abstract"
from twisted.internet import defer, interfaces, address, error
from twisted.python import log

import server, client
import iocpdebug
from zope.interface import implements


class TcpMixin:
    def getTcpNoDelay(self):
        return operator.truth(self.socket.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY))

    def setTcpNoDelay(self, enabled):
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, enabled)

    def getTcpKeepAlive(self):
        return operator.truth(self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE))

    def setTcpKeepAlive(self, enabled):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, enabled)
 
    def getHost(self):
        return address.IPv4Address('TCP', *(self.socket.getsockname() + ('INET',)))

    def getPeer(self):
        return address.IPv4Address('TCP', *(self.socket.getpeername() + ('INET',)))

    def getPeerHost(self):
        return self.socket.getpeername()[0]

    def getPeerPort(self):
        return self.socket.getpeername()[1]

class ServerSocket(server.ListeningPort.transport_class, TcpMixin):
    implements(interfaces.ITCPTransport)

class Port(server.ListeningPort):
    sockinfo = (socket.AF_INET, socket.SOCK_STREAM, 0)
    transport_class = ServerSocket
    def __init__(self, (host, port), factory, backlog):
        if iocpdebug.debug:
            print "listening on (%s, %s)" % (host, port)
        if isinstance(port, types.StringTypes):
            try:
                port = socket.getservbyname(port, 'tcp')
            except socket.error, e:
                raise error.ServiceNameUnknownError(string=str(e))
        server.ListeningPort.__init__(self, (host, port), factory, backlog)

    def getOwnPort(self):
        return self.addr[1]

    def getHost(self):
        return address.IPv4Address('TCP', *(self.socket.getsockname() + ('INET',)))

    def buildAddress(self, addr):
        return address._ServerFactoryIPv4Address('TCP', addr[0], addr[1], 'INET')

class ClientSocket(client.SocketConnector.transport_class, TcpMixin):
    implements(interfaces.ITCPTransport)

class Connector(client.SocketConnector):
    sockinfo = (socket.AF_INET, socket.SOCK_STREAM, 0)
    transport_class = ClientSocket

    def _filterRealAddress(self, host):
        return (host, self.addr[1])

    def prepareAddress(self):
        host, port = self.addr
        if iocpdebug.debug:
            print "connecting to (%s, %s)" % (host, port)
        if isinstance(port, types.StringTypes):
            try:
                port = socket.getservbyname(port, 'tcp')
            except socket.error, e:
                raise error.ServiceNameUnknownError(string=str(e))
        self.addr= (host, port)
    
    def resolveAddress(self):
        host, port = self.addr
        if isIPAddress(host):
            return self.addr
        else:
            from twisted.internet import reactor
            return reactor.resolve(host).addCallback(self._filterRealAddress)

    def getDestination(self):
        return address.IPv4Address('TCP', self.addr[0], self.addr[1], 'INET')

    def buildAddress(self, addr):
        return address.IPv4Address('TCP', addr[0], addr[1], 'INET')

