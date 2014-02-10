#! /usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# Run this example with:
#    python connect-proxy.py
#
# Then configure your web browser to use localhost:8181 as a proxy and
# visit a URL. This proxy is proxying the connection to that URL's
# host.
#
# This differs from proxy.py because it supports the http CONNECT method.
# When using this as a browser proxy you should be able to visit both
# http:// and https:// URLs.

from twisted.web import proxy
from twisted.internet import reactor
from twisted.python import log
import sys
log.startLogging(sys.stdout)


reactor.listenTCP(8181, proxy.TunnelProxyFactory())
reactor.run()
