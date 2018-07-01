# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This example demonstrates how to run a reverse proxy.

Run this example with:
    $ python transparent-proxy.py

Then visit http://localhost:8080/ in your web browser.
"""

from twisted.internet import reactor
from twisted.web import proxy


factory = proxy.ReverseProxyFactory(b'www.asdf.com', 80)
reactor.listenTCP(8080, factory)
reactor.run()
