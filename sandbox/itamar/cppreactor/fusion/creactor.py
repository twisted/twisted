"""C++ hooks from inside reactor."""

from twisted.internet import tcp, udp, reactor
from fusion import _fusion


class CServer(_fusion.TCPTransportMixin, tcp.Server):

    def __init__(self, *args, **kwargs):
        _fusion.TCPTransportMixin.__init__(self, self)
        tcp.Server.__init__(self, *args, **kwargs)
        self.initProtocol()


class CPort(tcp.Port):

    transport = CServer


class CClient(_fusion.TCPTransportMixin, tcp.Client):

    def __init__(self, *args, **kwargs):
        _fusion.TCPTransportMixin.__init__(self, self)
        tcp.Client.__init__(self, *args, **kwargs)
    
    def _connectDone(self):
        self.protocol = self.connector.buildProtocol(self.getPeer())
        self.initProtocol()
        self.connected = 1
        self.protocol.makeConnection(self)
        self.logstr = self.protocol.__class__.__name__+",client"
        self.startReading()


class CConnector(tcp.Connector):

    def _makeTransport(self):
        return CClient(self.host, self.port, self.bindAddress, self, self.reactor)


class CUDPPort(_fusion.UDPPortMixin, udp.Port):

    def __init__(self, *args, **kwargs):
        udp.Port.__init__(self, *args, **kwargs)

    def _bindSocket(self):
        udp.Port._bindSocket(self)
        _fusion.UDPPortMixin.__init__(self, self)


class CMulticastPort(_fusion.UDPPortMixin, udp.MulticastPort):

    def __init__(self, *args, **kwargs):
        udp.MulticastPort.__init__(self, *args, **kwargs)

    def _bindSocket(self):
        udp.MulticastPort._bindSocket(self)
        _fusion.UDPPortMixin.__init__(self, self)


def _listenWith(portType, *args, **kwargs):
    p = portType(*args, **kwargs)
    p.startListening()
    return p


def listenTCP(port, factory, backlog=50, interface=""):
    return _listenWith(CPort, port, factory, backlog, interface, reactor)

def listenUDP(port, protocol, interface='', maxPacketSize=8192):
    return _listenWith(CUDPPort, port, protocol, interface, maxPacketSize, reactor)

def listenMulticast(port, protocol, interface='', maxPacketSize=8192, listenMultiple=False):
    return _listenWith(CMulticastPort, port, protocol, interface, maxPacketSize, reactor, listenMultiple)

def connectTCP(host, port, factory, timeout=30, bindAddress=None):
    c = CConnector(host, port, factory, timeout, bindAddress, reactor)
    c.connect()
    return c



__all__ = ["listenTCP", "connectTCP", "listenUDP", "listenMulticast"]
