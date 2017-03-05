# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An example of a proxy which logs all requests processed through it.

Usage:
    $ python logging-proxy.py

Then configure your web browser to use localhost:8080 as a proxy, and visit a
URL (This is not a SOCKS proxy). When browsing in this configuration, this
example will proxy connections from the browser to the server indicated by URLs
which are visited.  The client IP and the request hostname will be logged for
each request.

HTTP is supported.  HTTPS is not supported.

See also proxy.py for a simpler proxy example.
"""

from __future__ import print_function

from twisted.internet import reactor
from twisted.web import proxy, http

class LoggingProxyRequest(proxy.ProxyRequest):
    def process(self):
        """
        It's normal to see a blank HTTPS page. As the proxy only works
        with the HTTP protocol.
        """
        print("Request from %s for %s" % (
            self.getClientIP(), self.getAllHeaders()['host']))
        try:
            proxy.ProxyRequest.process(self)
        except KeyError:
            print("HTTPS is not supported at the moment!")

class LoggingProxy(proxy.Proxy):
    requestFactory = LoggingProxyRequest

class LoggingProxyFactory(http.HTTPFactory):
    def buildProtocol(self, addr):
        return LoggingProxy()

reactor.listenTCP(8080, LoggingProxyFactory())
reactor.run()
