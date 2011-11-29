# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# Run this example with:
#    python reverse-proxy.py
#
# Then visit http://localhost:8080 in your web browser. The reverse
# proxy will proxy your connection to www.yahoo.com.

from twisted.internet import reactor
from twisted.web import proxy, server

site = server.Site(proxy.ReverseProxyResource('www.yahoo.com', 80, ''))
reactor.listenTCP(8080, site)
reactor.run()
