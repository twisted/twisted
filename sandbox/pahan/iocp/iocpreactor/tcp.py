from twisted.internet import tcp # and confusion begins
import abstract # TODO: change me to fully-qualified name

BUFFER_SIZE = 8192

class Connection(abstract.IoHandle):
    """I am the superclass of all socket-based FileDescriptors.

    This is an abstract superclass of all objects which represent a TCP/IP
    connection based socket.
    """

    __implements__ = abstract.IoHandle.__implements__, interfaces.ITCPTransport

    TLS = 0

    def __init__(self, skt, protocol, reactor=None):
        abstract.IoHandle.__init__(self, reactor=reactor)
        self.socket = skt
        self.protocol = protocol

class Connector(tcp.Connector):
    def _makeTransport(self):
        return Client(self.host, self.port, self.bindAddress, self, self.reactor)

