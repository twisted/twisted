"""C hooks from inside reactor."""

from twisted.internet import tcp

from rexactor import tcp as ctcp


class CServer(ctcp._CMixin, tcp.Server):

    def __init__(self, *args, **kwargs):
        tcp.Server.__init__(self, *args, **kwargs)
        ctcp._CMixin.__init__(self)


class CPort(tcp.Port):

    transport = CServer


class CClient(ctcp._CMixin, tcp.Client):

    def __init__(self, *args, **kwargs):
        tcp.Client.__init__(self, *args, **kwargs)
        ctcp._CMixin.__init__(self)


class CConnector(tcp.Connector):

    def _makeTransport(self):
        return CClient(self.host, self.port, self.bindAddress, self, self.reactor)


def install():
    """Install support for C protocols."""
    # XXX this'll fail if code does "from t.i.tcp import Port"
    # but since default.py doesn't this should be ok for now
    tcp.Port = CPort
    tcp.Connector = CConnector


__all__ = ["install"]
