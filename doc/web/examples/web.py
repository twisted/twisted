# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


# This web server makes it possible to put it behind a reverse proxy
# transparently. Just have the reverse proxy proxy to 
# host:port/vhost/http/external-host:port/
# and on redirects and other link calculation, the external-host:port will
# be transmitted to the client.

from twisted.internet import reactor
from twisted.web import static, server, vhost, twcgi, script

root = static.File("static")
root.processors = {
            '.cgi': twcgi.CGIScript,
            '.php3': twcgi.PHP3Script,
            '.php': twcgi.PHPScript,
            '.epy': script.PythonScript,
            '.rpy': script.ResourceScript,
}
root.putChild('vhost', vhost.VHostMonsterResource())
site = server.Site(root)
reactor.listenTCP(1999, site)
reactor.run()
