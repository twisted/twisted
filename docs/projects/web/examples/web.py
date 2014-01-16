# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This demonstrates a web server which can run behind a name-based virtual hosting
reverse proxy.  It decodes modified URLs like:

    host:port/vhost/http/external-host:port/

and dispatches the request as if it had been received on the given protocol,
external host, and port.

Usage:
    python web.py
"""

from twisted.internet import reactor
from twisted.web import static, server, vhost, twcgi, script

root = static.File("static")
root.processors = {
            '.cgi': twcgi.CGIScript,
            '.epy': script.PythonScript,
            '.rpy': script.ResourceScript,
}
root.putChild('vhost', vhost.VHostMonsterResource())
site = server.Site(root)
reactor.listenTCP(1999, site)
reactor.run()
