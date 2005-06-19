# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# 
# Twisted, the Framework of Your Internet
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


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
    zsh_actions = {"data" : "_dirs", "moduli" : "_dirs"}


def makeService(config):
    t = factory.OpenSSHFactory()
    t.portal = portal.Portal(unix.UnixSSHRealm())
    t.portal.registerChecker(checkers.UNIXPasswordDatabase())
    t.portal.registerChecker(checkers.SSHPublicKeyDatabase())
    if checkers.pamauth:
        t.portal.registerChecker(checkers.PluggableAuthenticationModulesChecker())
    t.dataRoot = config['data']
    t.moduliRoot = config['moduli'] or config['data']
    port = config['port']
    if config['interface']:
        # Add warning here
        port += ':interface='+config['interface']
    return strports.service(port, t)
