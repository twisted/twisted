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

from twisted.conch import checkers, unix
from twisted.conch.openssh_compat import factory
from twisted.cred import portal
from twisted.python import usage
from twisted.application import strports


class Options(usage.Options):
    synopsis = "Usage: mktap conch [-i <interface>] [-p <port>] [-d <dir>] "
    longdesc = "Makes a Conch SSH server.."
    optParameters = [
         ["interface", "i", "", "local interface to which we listen"],
         ["port", "p", "22", "Port on which to listen"],
         ["data", "d", "/etc", "directory to look for host keys in"],
         ["moduli", "", None, "directory to look for moduli in "
                              "(if different from --data)"]
    ]


def makeService(config):
    t = factory.OpenSSHFactory()
    t.portal = portal.Portal(unix.UnixSSHRealm())
    t.portal.registerChecker(checkers.UNIXPasswordDatabase())
    t.portal.registerChecker(checkers.SSHPublicKeyDatabase())
    #if checkers.pamauth:
    #    t.portal.registerChecker(checkers.PluggableAuthenticationModulesChecker())
    t.dataRoot = config['data']
    t.moduliRoot = config['moduli'] or config['data']
    port = config['port']
    if config['interface']:
        # Add warning here
        port += ':interface='+config['interface']
    return strports.service(port, t)
