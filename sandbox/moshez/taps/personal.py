
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Support module for creating personal web servers with 'mktap'
"""
import pwd, os
from twisted.web import server, static, twcgi, script, distrib
from twisted.python import usage
from twisted.spread import pb
from twisted.application import internet

class Options(usage.Options):
    synopsis = "Usage: mktap web [options]"
    longdesc = "Create a personal site which can be served by a users server"
    optParameters = [
      ["logfile", "l", None, "Path to web CLF (Combined Log Format) log file."],
      ["root", "r", "~/public_html.twistd", "Path to personal site root"],
    ]

def makeService(config):
    root = static.File(config['root'])
    root.processors = {
        '.cgi': twcgi.CGIScript,
        '.rpy': script.ResourceScript,
    }
    site = server.Site(root, logPath=config['logfile'])
    path = os.path.expanduser("~/"+distrib.UserDirectory.userSocketName)
    factory = pb.BrokerFactory(distrib.ResourcePublisher(site))
    return internet.UNIXServer(path, factory)
