# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# Run this example with:
#    python proxy.py
#
# Then configure your web browser to use localhost:8080 as a proxy and
# visit a URL. This proxy is proxying the connection to that URL's
# host.

from twisted.web import proxy, http
from twisted.internet import reactor

class ProxyFactory(http.HTTPFactory):
    def buildProtocol(self, addr):
        return proxy.Proxy()
 
reactor.listenTCP(8080, ProxyFactory())
reactor.run()
