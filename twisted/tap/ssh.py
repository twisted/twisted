# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
# 
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
I am a support module for making SSH servers with mktap.
"""

from twisted.conch import identity, authorizer
from twisted.conch.ssh import factory
from twisted.python import reflect, usage
import sys, pwd

class Options(usage.Options):
    synopsis = "Usage: mktap sshd [-i <interface>] [-p <port>] [-d <dir>] "
    optParameters = [["interface", "i", "", "local interface to which we listen"],
                  ["port", "p", 5822, "Port on which to listen"],
                  ["data", "d", "/etc", "directory to look for host keys in"],
                  ["moduli", "", None, "directory to look for moduli in (if different from --data"]]

    longdesc = "Makes a SSH server.."

    def opt_auth(self, authName):
        authObj = reflect.namedClass(authName)
        self.opts['auth'] = authObj()

def updateApplication(app, config):
    t = factory.OpenSSHFactory()
    t.authorizer = config.opts.has_key('auth') and config.opts['auth'] or authorizer.OpenSSHConchAuthorizer()
    t.authorizer.setApplication(app)
    t.dataRoot = config.opts['data']
    t.moduliRoot = config.opts['moduli'] or config.opts['data']
    portno = int(config.opts['port'])
    app.listenTCP(portno, t, interface=config.opts['interface'])
