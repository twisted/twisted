
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
I am a support module for making SOCKS servers with mktap.
"""

from twisted.protocols import socks
from twisted.internet import tcp
from twisted.python import usage
import sys

class Options(usage.Options):
    synopsis = "Usage: mktap socks [-p <port>] [-l <file>]"
    optStrings = [["port", "p", 1080],
                  ["log", "l", "None", "file to log connection data to"]]

    longdesc = "Makes a SOCKSv4 server."

def getPorts(app, config):
    print "\n\nWARNING: This SOCKSv4 proxy is configured insecurely.\nDO NOT RUN IT ON YOUR FIREWALL.\n\n"
    if config.log=="None": config.log=None
    t = socks.SOCKSv4Factory(config.log)
    portno = int(config.port)
    return [(portno, t)]
