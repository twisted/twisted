"""SSL transport. Requires PyOpenSSL (http://pyopenssl.sf.net).

Most servers will likely want to overide the Port class's createContext()
method with their own.
"""

# System imports
from OpenSSL import SSL

# sibling imports
import tcp


class Client(tcp.Client):
    """I am an SSL client.
    """
    
    def getContext(self):
        """Get an SSL context. Override in subclasses."""
        return SSL.Context(SSL.SSLv23_METHOD)

    def createInternetSocket(self):
        """(internal) create an SSL socket
        """
        sock = tcp.Client.createInternetSocket(self)
        return SSL.Connection(self.getContext(), sock)


class Port(tcp.Port):
    """I am an SSL server.
    """

    def getContext(self):
        """Create an SSL context. Override in subclasses.
        
        This is a sample implementation that loads a certificate from a file 
        called 'server.pem'."""
        ctx = SSL.Context(SSL.SSLv23_METHOD)
        ctx.use_certificate_file('server.pem')
        ctx.use_privatekey_file('server.pem')
        return ctx
    
    def createInternetSocket(self):
        """(internal) create an SSL socket
        """
        sock = tcp.Port.createInternetSocket(self)
        return SSL.Connection(self.getContext(), sock)
