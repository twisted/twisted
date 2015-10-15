# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This example demonstrates a very simple HTTP proxy.

Usage:
    $ python proxy.py

Then configure your web browser to use localhost:8080 as a proxy, and visit a
URL (This is not a SOCKS proxy). When browsing in this configuration, this
example will proxy connections from the browser to the server indicated by URLs
which are visited.

See also logging-proxy.py for a proxy with additional features.
"""

from twisted.web import proxy, http
from twisted.internet import reactor

class ProxyFactory(http.HTTPFactory):
    def buildProtocol(self, addr):
        return proxy.Proxy()

reactor.listenTCP(8080, ProxyFactory())
reactor.run()
