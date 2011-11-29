# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# Run this example with:
#    python logging-proxy.py
#
# Then configure your web browser to use localhost:8080 as a proxy,
# and visit a URL. This proxy is proxying the connection to that URL's
# host and will log the client IP and hostname.

from twisted.internet import reactor
from twisted.web import proxy, http

class LoggingProxyRequest(proxy.ProxyRequest):
    def process(self):
        print "Request from %s for %s" % (
            self.getClientIP(), self.getAllHeaders()['host'])
        proxy.ProxyRequest.process(self)

class LoggingProxy(proxy.Proxy):
    requestFactory = LoggingProxyRequest

class LoggingProxyFactory(http.HTTPFactory):
    def buildProtocol(self, addr):
        return LoggingProxy()

reactor.listenTCP(8080, LoggingProxyFactory())
reactor.run()
