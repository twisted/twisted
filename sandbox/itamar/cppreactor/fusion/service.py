"""Services for running Fusion based protocols."""

from twisted.application import internet
from fusion import creactor

class _AbstractFusionServer(internet._AbstractServer):

    def _getPort(self):
        return getattr(creactor, 'listen'+self.method)(*self.args, **self.kwargs)


class TCPClient(internet._AbstractClient):
    """Service for TCP clients."""
    
    method = "TCP"

    def _getConnection(self):
        return creactor.connectTCP(*self.args, **self.kwargs)

class TCPServer(_AbstractFusionServer):
    method = "TCP"

class UDPServer(_AbstractFusionServer):
    method = "UDP"

class MulticastServer(_AbstractFusionServer):
    method = "Multicast"


__all__ = ["TCPClient", "TCPServer", "UDPServer", "MulticastServer"]
