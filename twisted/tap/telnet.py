
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
I am the support module for making a telnet server with mktap.
"""

from twisted.protocols import telnet
from twisted.internet import tcp
from twisted.python import usage
import sys


class Options(usage.Options):
    synopsis = "Usage: mktap telnet [options]"
    optParameters = [["username", "u", "admin","set the login username"],
                  ["password", "w", "changeme","set the password"]]

    longdesc = "Makes a telnet server to a Python shell."

    def opt_port(self, opt):
        """set the port to listen on
        """
        try:
            self.opts['portno'] = int(opt)
        except ValueError:
            raise usage.error("Invalid argument to 'port'!")
    opt_p = opt_port

def updateApplication(app, config):
    t = telnet.ShellFactory()
    t.username = config.opts['username']
    t.password = config.opts['password']
    try:
        portno = config.opts['portno']
    except KeyError:
        portno = 4040
    app.listenTCP(portno, t)
