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


class Echoer:
    """An example object to be published."""
    
    def perspective_echo(self, *args):
        """Return all passed args."""
        return args


def main():
    from twisted.internet.app import Application
    from twisted.web import server
    app = Application("xmlrpc")
    r = xmlrpc.PB(Echoer())
    app.listenTCP(7080, server.Site(r))
    app.run(0)


if __name__ == '__main__':
    main()
