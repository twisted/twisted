
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
from twisted.python import usage
from twisted.application import internet
import sys

class Options(usage.Options):
    synopsis = "Usage: mktap socks [-i <interface>] [-p <port>] [-l <file>]"
    optParameters = [["interface", "i", "127.0.0.1", "local interface to which we listen"],
                  ["port", "p", 1080, "Port on which to listen"],
                  ["log", "l", None, "file to log connection data to"]]

    longdesc = "Makes a SOCKSv4 server."

def makeService(config):
    if config["interface"] != "127.0.0.1":
        print
        print "WARNING:"
        print "  You have chosen to listen on a non-local interface."
        print "  This may allow intruders to access your local network"
        print "  if you run this on a firewall."
        print
    t = socks.SOCKSv4Factory(config['log'])
    portno = int(config['port'])
    return internet.TCPServer(portno, t, interface=config['interface'])
