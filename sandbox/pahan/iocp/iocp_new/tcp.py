from socket import AF_INET, SOCK_STREAM, getservbyname
import types

from twisted.internet.abstract import isIPAddress # would rather not import "abstract"
from twisted.internet.error import ServiceNameUnknownError
from twisted.internet import defer

import server, client

class Port(server.SocketPort):
    af = AF_INET
    type = SOCK_STREAM
    proto = 0
    def __init__(self, (host, port), factory, backlog, **kw):
        if isinstance(port, types.StringTypes):
            try:
                port = getservbyname(port, 'tcp')
            except socket.error, e:
                raise ServiceNameUnknownError(string=str(e))
        server.SocketPort.__init__(self, (host, port), factory, backlog, **kw)

class Connector(client.SocketConnector):
    af = AF_INET
    type = SOCK_STREAM
    proto = 0

    def _filterRealAddress(self, host):
        return (host, self.addr[1])

    def prepareAddress(self):
        host, port = self.addr
        if isinstance(port, types.StringTypes):
            try:
                port = getservbyname(port, 'tcp')
            except socket.error, e:
                return defer.fail(ServiceNameUnknownError(string=str(e)))
        self.addr = (host, port)
        if isIPAddress(host):
            return self.addr
        else:
            from twisted.internet import reactor
            return reactor.resolve(host).addCallback(self._filterRealAddress)

