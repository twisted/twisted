
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
I am a support module for making SOCKSv4 servers with mktap.
"""

from twisted.protocols import socks
from twisted.internet import tcp
from twisted.python import usage
import sys

class Options(usage.Options):
    synopsis = "Usage: mktap socks [-i <interface>] [-p <port>] [-l <file>]"
    optParameters = [["interface", "i", "127.0.0.1", "local interface to which we listen"],
                  ["port", "p", 1080],
                  ["log", "l", "None", "file to log connection data to"]]

    longdesc = "Makes a SOCKSv4 server."

def updateApplication(app, config):
    if config.interface != "127.0.0.1":
        print
        print "WARNING:"
        print "  You have chosen to listen on a non-local interface."
        print "  This may allow intruders to access your local network"
        print "  if you run this on a firewall."
        print
    if config.opts['log']=="None": config.opts['log']=None
    t = socks.SOCKSv4Factory(config.opts['log'])
    portno = int(config.opts['port'])
    app.listenTCP(portno, t, interface=config.opts['interface'])
