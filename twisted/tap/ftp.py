
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
I am the support module for making a ftp server with mktap.
"""

from twisted.protocols import ftp
from twisted.internet import tcp
from twisted.python import usage
import sys


usage_message = """
usage: mktap ftp [OPTIONS]

Options are as follows:
        --port <#>, -p:         set the port number to <#>.
"""

class Options(usage.Options):
    def opt_port(self, opt):
        try:
	    self.portno = int(opt)
	except ValueError:
	    raise usage.error("Invalid argument to 'port'!")
    opt_p = opt_port

def getPorts(app, config):
    t = ftp.ShellFactory()
    try:
        portno = config.portno
    except AttributeError:
        portno = 2121
    return [(portno, t)]
