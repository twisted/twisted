from socket import AF_INET, SOCK_STREAM

from twisted.internet.abstract import isIPAddress

import server, client

class Port(server.SocketPort):
    af = AF_INET
    type = SOCK_STREAM
    proto = 0

class Connector(client.SocketConnector):
    af = AF_INET
    type = SOCK_STREAM
    proto = 0

    def _filterRealAddress(self, host):
        return (host, self.addr[1])

    def prepareAddress(self):
        if isIPAddress(self.addr[0]):
            return self.addr
        else:
            from twisted.internet import reactor
            return reactor.resolve(self.addr[0]).addCallback(self._filterRealAddress)

