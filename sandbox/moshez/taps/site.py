
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

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
