"""Hook up an object to XML-RPC. An example session:
    
    >>> s = xmlrpclib.Server('http://localhost:7080/')
    >>> s.echo("lala")
    ['lala']
    >>> s.echo("lala", 1)
    ['lala', 1]
    >>> s.echo("lala", 4)
    ['lala', 4]
    >>> s.echo("lala", 4, 3.4)
    ['lala', 4, 3.3999999999999999]
    >>> s.echo("lala", 4, [1, 2])
    ['lala', 4, [1, 2]]
"""

from twisted.web import xmlrpc


class Echoer(xmlrpc.XMLRPC):
    """An example object to be published.
    
    Has two methods accessable by XML-RPC, 'echo' and 'hello'.
    """
    
    def _getFunction(self, functionPath):
        """Convert the functionPath to a method beginning with 'xmlrpc_'.
        
        For example, 'echo' returns the method 'xmlrpc_echo'.
        """
        f = getattr(self, "xmlrpc_%s" % functionPath, None)
        if f:
            return f
        else:
            raise xmlrpc.NoSuchFunction
    
    def xmlrpc_echo(self, *args):
        """Return all passed args."""
        return args
    
    def xmlrpc_hello(self, *args):
        """Return 'hello, world'."""
        return 'hello, world!'


def main():
    from twisted.internet.app import Application
    from twisted.web import server
    app = Application("xmlrpc")
    r = Echoer()
    app.listenTCP(7080, server.Site(r))
    app.run(0)


if __name__ == '__main__':
    main()
