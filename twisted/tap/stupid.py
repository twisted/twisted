
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
I am the support module for making a stupid proxy with mktap.
"""

from twisted.internet import tcp, stupidproxy
from twisted.python import usage
import sys


usage_message = """
usage: mktap stupid [OPTIONS]

Options are as follows:
        --port <#>, -p:         set the port number to <#>.
        --host <host>, -h:      set the host to <host>
        --dest_port <#>, -d:    set the destination port to <#>
"""

class Options(usage.Options):
    optStrings = [["port", "p", 6666],
        	  ["host", "h", "localhost"],
        	  ["dest_port", "d", 6665]]

def getPorts(app, config):
    s = stupidproxy.makeStupidFactory(config.host, int(config.dest_port))
    return [(int(config.port), s)]
