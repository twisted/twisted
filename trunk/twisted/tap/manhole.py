
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
I am the support module for making a manhole server with twistd.
"""

from twisted.manhole import service
from twisted.spread import pb
from twisted.python import usage, util
from twisted.cred import portal, checkers
from twisted.application import strports
import os, sys

class Options(usage.Options):
    synopsis = "[options]"
    optParameters = [
           ["user", "u", "admin", "Name of user to allow to log in"],
           ["port", "p", str(pb.portno), "Port to listen on"],
    ]

    optFlags = [
        ["tracebacks", "T", "Allow tracebacks to be sent over the network"],
    ]

    compData = usage.Completions(
        optActions={"user": usage.CompleteUsernames()}
        )

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
