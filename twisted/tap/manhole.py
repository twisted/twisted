
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
I am the support module for making a manhole server with mktap.
"""

from twisted.manhole import service
from twisted.spread import pb
from twisted.python import usage, util
from twisted.cred import portal, checkers
from twisted.application import strports
import os, sys

class Options(usage.Options):
    synopsis = "mktap manhole [options]"
    optParameters = [
           ["user", "u", "admin", "Name of user to allow to log in"],
           ["port", "p", str(pb.portno), "Port to listen on"],
    ]

    optFlags = [
        ["tracebacks", "T", "Allow tracebacks to be sent over the network"],
    ]

    def opt_password(self, password):
        """Required.  '-' will prompt or read a password from stdin.
        """
        # If standard input is a terminal, I prompt for a password and
        # confirm it.  Otherwise, I use the first line from standard
        # input, stripping off a trailing newline if there is one.
        if password in ('', '-'):
            self['password'] = util.getPassword(confirm=1)
        else:
            self['password'] = password
    opt_w = opt_password

    def postOptions(self):
        if not self.has_key('password'):
            self.opt_password('-')

def makeService(config):
    port, user, password = config['port'], config['user'], config['password']
    p = portal.Portal(
        service.Realm(service.Service(config["tracebacks"], config.get('namespace'))),
        [checkers.InMemoryUsernamePasswordDatabaseDontUse(**{user: password})]
    )
    return strports.service(port, pb.PBServerFactory(p, config["tracebacks"]))
