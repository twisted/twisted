import types, socket, operator

from twisted.internet.abstract import isIPAddress # would rather not import "abstract"
from twisted.internet.error import ServiceNameUnknownError
from twisted.internet import defer, interfaces
from twisted.python import log

import server#, client
import iocpdebug

class TcpMixin:
    def getTcpNoDelay(self):
        return operator.truth(self.socket.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY))

    def setTcpNoDelay(self, enabled):
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, enabled)

    def getTcpKeepAlive(self):
        return operator.truth(self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE))

    def setTcpKeepAlive(self, enabled):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, enabled)
 
class ServerSocket(server.ListeningPort.transport, TcpMixin):
    __implements__ = server.ListeningPort.transport.__implements__ + (interfaces.ITCPTransport,)
    pass

class Port(server.ListeningPort):
    sockinfo = (socket.AF_INET, socket.SOCK_STREAM, 0)
    transport = ServerSocket
    def __init__(self, (host, port), factory, backlog):
        if iocpdebug.debug:
            print "listening on (%s, %s)" % (host, port)
        if isinstance(port, types.StringTypes):
            try:
                port = socket.getservbyname(port, 'tcp')
            except socket.error, e:
                raise ServiceNameUnknownError(string=str(e))
        server.ListeningPort.__init__(self, (host, port), factory, backlog)

"""
class ClientSocket(client.SocketConnector.real_transport, TcpMixin):
    pass

class Connector(client.SocketConnector):
    af = socket.AF_INET
    type = socket.SOCK_STREAM
    proto = 0
    real_transport = ClientSocket

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
                return defer.fail(ServiceNameUnknownError(string=str(e)))
        self.addr = (host, port)
        if isIPAddress(host):
            return self.addr
        else:
            from twisted.internet import reactor
            return reactor.resolve(host).addCallback(self._filterRealAddress)
"""

