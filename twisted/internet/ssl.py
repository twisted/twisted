
# System imports

# sibling imports
import tcp

class Client(tcp.Client):
    """I am an SSL client.
    """
    def __init__(self, host, port):
        """Initialize.
        """
        self.ctx = SSL.Context('sslv23')
        tcp.Client.__init__(self,host,port)

    def createInternetSocket(self):
        """(internal) create an SSL socket
        """
        return SSL.Connection(self.ctx)

class Port(tcp.Port):
    """I am an SSL server.
    """
    def __init__(self, port, factory, cert):
        """
        Initialize.
        """
        self.ctx=SSL.Context('sslv23')
        self.ctx.load_cert(cert)
        tcp.Port.__init__(self, port, factory)

    def createInternetSocket(self):
        """(internal) create an SSL socket
        """
        return SSL.Connection(self.ctx)
