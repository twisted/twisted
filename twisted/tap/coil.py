
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

"""I am the support module for creating a coil web server with 'mktap'
"""

import string, os

# Twisted Imports
from twisted.web import server
from twisted.coil import web
from twisted.internet import tcp
from twisted.python import usage


class Options(usage.Options):
    synopsis = "Usage: mktap coil [options]"
    optParameters = [["port", "p", "9080","Port to start the server on."],]

    longdesc = """\
This creates a coil.tap file that can be used by twistd."""


def updateApplication(app, config):
    root = web.ConfigRoot(app)
    site = server.Site(root)
    app.listenTCP(int(config.port), site)

