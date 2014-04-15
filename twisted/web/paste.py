# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Integration with L{paste.deploy}
"""

from twisted.internet.endpoints import serverFromString
from twisted.application.reactors import installReactor
from twisted.python.threadpool import ThreadPool


class _PasteServer(object):
    def __init__(self, reactorName, ports):
        self.ports = ports
        self.reactorName = reactorName
    def __call__(self, app):
        from twisted.web.server import Site
        from twisted.web.wsgi import WSGIResource
        reactor = installReactor(self.reactorName)

        threads = ThreadPool()
        threads.start()

        resource = WSGIResource(reactor, threads, app)
        site = Site(resource)

        for port in self.ports:
            endpoint = serverFromString(reactor, port)
            endpoint.listen(site)

        reactor.run()



def serverFactory(globalConfig, ports=b"tcp:8080", reactor=None):
    """
    Creates a WSGI server for use with L{paste.deploy}.

    @param globalConfig: Global configuration from paste.
    @type globalConfig: L{dict} of L{str}

    @param ports: Space seperate list of endpoint description to listen on.
    @type ports: L{str}

    @param reactor: Name of reactor to use.
    @type reactor: L{str}
    """
    return _PasteServer(reactor, ports.split(b' '))
