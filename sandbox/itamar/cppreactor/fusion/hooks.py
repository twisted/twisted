"""C++ hooks from inside reactor."""

from twisted.internet import tcp, udp
from fusion import tcp as ctcp
from fusion import udp as cudp


class CServer(ctcp.TCPTransportMixin, tcp.Server):

    def __init__(self, *args, **kwargs):
        tcp.Server.__init__(self, *args, **kwargs)
        ctcp.TCPTransportMixin.__init__(self, self)
        self.initProtocol()


class CPort(tcp.Port):

    transport = CServer


class CClient(ctcp.TCPTransportMixin, tcp.Client):

    def __init__(self, *args, **kwargs):
        tcp.Client.__init__(self, *args, **kwargs)
        ctcp.TCPTransportMixin.__init__(self, self)
    
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


_origUDPPort = udp.Port

class CUDPPort(cudp.UDPPortMixin, _origUDPPort):

    def __init__(self, *args, **kwargs):
        _origUDPPort.__init__(self, *args, **kwargs)

    def _bindPort(self):
        _origUDPPort._bindPort(self)
        cudp.UDPPortMixin.__init__(self, self)


class CMulticastPort(cudp.UDPPortMixin, udp.MulticastPort):

    def __init__(self, *args, **kwargs):
        udp.MulticastPort.__init__(self, *args, **kwargs)
        cudp.UDPPortMixin.__init__(self, self)


INSTALLED = False

def install():
    """Install support for C protocols."""
    global INSTALLED
    if INSTALLED:
        return
    # XXX this'll fail if code does "from t.i.tcp import Port"
    # but since default.py doesn't this should be ok for now
    tcp.Port = CPort
    tcp.Connector = CConnector
    udp.Port = CUDPPort
    udp.MulticastPort = CMulticastPort
    INSTALLED = True

__all__ = ["install"]
