from twisted.web import xmlrpc, server

class EchoHandler:

    def echo(self, x):
        """
        Return all passed args
        """
        return x



class AddHandler:

    def add(self, a, b):
        """
        Return sum of arguments.
        """
        return a + b



class Example(xmlrpc.XMLRPC):
    """
    An example of using you own policy to fetch the handler
    """

    def __init__(self):
        xmlrpc.XMLRPC.__init__(self)
        self._addHandler = AddHandler()
        self._echoHandler = EchoHandler()

        #We keep a dict of all relevant
        #procedure names and callable.
        self._procedureToCallable = {
            'add':self._addHandler.add,
            'echo':self._echoHandler.echo
        }

    def lookupProcedure(self, procedurePath):
        try:
            return self._procedureToCallable[procedurePath]
        except KeyError, e:
            raise xmlrpc.NoSuchFunction(self.NOT_FOUND,
                        "procedure %s not found" % procedurePath)

    def listProcedures(self):
        """
        Since we override lookupProcedure, its suggested to override
        listProcedures too.
        """
        return ['add', 'echo']



if __name__ == '__main__':
    from twisted.internet import reactor
    r = Example()
    reactor.listenTCP(7080, server.Site(r))
    reactor.run()
