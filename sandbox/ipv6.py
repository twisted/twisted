
import socket

from twisted.internet import tcp, default, protocol
from twisted.python.compat import inet_pton

def isIPv6Address(ip):
    try:
        inet_pton(socket.AF_INET6, ip)
    except:
        return 0
    return 1

class IPv6Client(tcp.TCPClient):
    def createInternetSocket(self):
        return socket.socket(socket.AF_INET6, socket.SOCK_STREAM)

    def resolveAddress(self):
        if isIPv6Address(self.addr[0]):
            self._setRealAddress(self.addr[0])
        else:
            reactor.resolve(self.addr[0]).addCallbacks(
                self._setRealAddress, self.failIfNotConnected
            )

    def getPeer(self):
        return ('INET6',) + self.socket.getpeername()

    def getHost(self):
        return ('INET6',) + self.socket.getsockname()


class IPv6Connector(default.TCPConnector):
    def _makeTransport(self):
        return IPv6Client(self.host, self.port, self.bindAddress, self, self.reactor)
    
    def getDestination(self):
        return ('INET6', self.host, self.port)

class IPv6Server(tcp.Server):
    def getHost(self):
        return ('INET6',) + self.socket.getsockname()

    def getPeer(self):
        if isinstance(self.client, tuple):
            return ('INET6',) + self.client
        else:
            return ('INET6', self.client)

class IPv6Port(tcp.Port):
    transport = IPv6Server

    def createInternetSocket(self):
        s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s
    
    def getHost(self):
        return ('INET6',) + self.socket.getsockname()
    
    def getPeer(self):
        return ('INET6',) + self.socket.getpeername()

def connectTCP6(host, port, factory, timeout=30, bindAddress=None, reactor=None):
    if reactor is None:
        from twisted.internet import reactor
    
    c = IPv6Connector(reactor, host, port, factory, timeout, bindAddress)
    c.connect()
    return c


def listenTCP6(port, factory, backlog=5, interface='::'):
    p = IPv6Port(port, factory, backlog, interface)
    p.startListening()
    return p

def main():
    from twisted.internet import reactor

    class TrivialProtocol(protocol.Protocol):
        def connectionMade(self):
            print 'I (', self.transport.getHost(), ') am connected! (to ', self.transport.getPeer(), ')'
            self.transport.write('Hello, world!\n')
        
        def dataReceived(self, data):
            print 'Received: ' + repr(data)

    class TrivialServerFactory(protocol.ServerFactory):
        protocol = TrivialProtocol
    class TrivialClientFactory(protocol.ClientFactory):
        protocol = TrivialProtocol
    
    p = listenTCP6(6666, TrivialServerFactory())
    c = connectTCP6('::1', 6666, TrivialClientFactory())
    
    reactor.run()

if __name__ == '__main__':
    main()

