
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
