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
from twisted.python import defer
import xmlrpclib


class Echoer(xmlrpc.XMLRPC):
    """An example object to be published.
    
    Has five methods accessable by XML-RPC, 'echo', 'hello', 'defer',
    'defer_fail' and 'fail.
    """
    
    def xmlrpc_echo(self, *args):
        """Return all passed args."""
        return args
    
    def xmlrpc_hello(self):
        """Return 'hello, world'."""
        return 'hello, world!'
    
    def xmlrpc_defer(self):
        """Show how xmlrpc methods can return Deferred."""
        return defer.succeed("hello")
    
    def xmlrpc_defer_fail(self):
        """Show how xmlrpc methods can return failed Deferred."""
        return defer.fail(12)

    def xmlrpc_fail(self):
        """Show how we can return a failure code."""
        return xmlrpclib.Fault(7, "Out of cheese.")


def main():
    from twisted.internet.app import Application
    from twisted.web import server
    app = Application("xmlrpc")
    r = Echoer()
    app.listenTCP(7080, server.Site(r))
    app.run(0)


if __name__ == '__main__':
    main()
