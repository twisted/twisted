
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# This web server makes it possible to put it behind a reverse proxy
# transparently. Just have the reverse proxy proxy to 
# host:port/vhost/http/external-host:port/
# and on redirects and other link calculation, the external-host:port will
# be transmitted to the client.

from twisted.internet import reactor
from twisted.web import static, server, vhost, twcgi, script, trp

root = static.File("static")
root.processors = {
            '.cgi': twcgi.CGIScript,
            '.php3': twcgi.PHP3Script,
            '.php': twcgi.PHPScript,
            '.epy': script.PythonScript,
            '.rpy': script.ResourceScript,
            '.trp': trp.ResourceUnpickler,
}
root.putChild('vhost', vhost.VHostMonsterResource())
site = server.Site(root)
reactor.listenTCP(1999, site)
reactor.run()
