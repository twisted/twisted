import types, socket, operator

from twisted.internet.abstract import isIPAddress # would rather not import "abstract"
from twisted.internet.error import ServiceNameUnknownError
from twisted.internet import defer
from twisted.python import log

import server
import iocpdebug

class Port(server.DatagramPort):
    af = socket.AF_INET
    type = socket.SOCK_DGRAM
    proto = 0

class ConnectedPort(server.ConnectedDatagramPort):
    af = socket.AF_INET
    type = socket.SOCK_DGRAM
    proto = 0

    def _filterRealAddress(self, host):
        return (host, self.addr[1])

    def prepareAddress(self):
        host, port = self.addr
#        if iocpdebug.debug:
#            print "connecting to (%s, %s)" % (host, port)
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

