
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
"""
Support module for creating simple web sites
"""
from twisted.web import static, twcgi, script
from twisted.python import usage
from twisted.application import strports, service

class Options(usage.Options):
    synopsis = "Usage: mktap web [options]"
    longdesc = "Create simple file-based web sites"
    optParameters = [
           ["logfile", "l", None, "Path to web CLF (Combined Log Format) "
                                  "log file."],
           ["root", "r", "/var/www/htdocs", "Path to web site root"],
    ]
    ports = ()
    def opt_port(self, port):
        """Add a port"""
        self.ports = self.ports + (port,)
    opt_p = opt_port
        

def makeService(config):
    ret = service.MultiService()
    root = static.File(config['root'])
    root.processors = {
            '.cgi': twcgi.CGIScript,
            '.rpy': script.ResourceScript,
    }
    site = server.Site(root, logPath=config['logfile'])
    for port in config.ports:
        strports.service(port, site).setServiceParent(ret)
    return s
