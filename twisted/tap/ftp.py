
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
import os.path

usage_message = """
usage: mktap ftp [OPTIONS]

Options are as follows:
        -p, --port <#>:         set the port number to <#>.
        -r, --root <path>:      define the root of the ftp-site.
        
        -a, --anonymous:        allow anonymous logins
        -3, --thirdparty:       allow third-party connections
        
"""

class Options(usage.Options):
    optStrings = [["port", "p", "2121"],
                  ["root", "r", "/usr/local/ftp"],
                  ["useranonymous", "", "anonymous"]]
    optFlags = [["anonymous", "a"],
                ["thirdparty", "3"]]

def getPorts(app, config):
    t = ftp.FTPFactory()
    # setting the config
    t.anonymous = config.anonymous
    t.thirdparty = config.thirdparty
    t.root = config.root
    t.useranonymous = config.useranonymous
    # adding a default user
    t.userdict = {}
    t.userdict["twisted"] = "twisted"
    try:
        portno = config.portno
    except AttributeError:
        portno = 2121
    return [(portno, t)]
