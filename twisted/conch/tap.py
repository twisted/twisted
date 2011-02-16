# -*- test-case-name: twisted.conch.test.test_tap -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Support module for making SSH servers with twistd.
"""

from twisted.conch import checkers, unix
from twisted.conch.openssh_compat import factory
from twisted.cred import portal
from twisted.python import usage
from twisted.application import strports
try:
    from twisted.cred import pamauth
except ImportError:
    pamauth = None



class Options(usage.Options):
    synopsis = "[-i <interface>] [-p <port>] [-d <dir>] "
    longdesc = "Makes a Conch SSH server."
    optParameters = [
         ["interface", "i", "", "local interface to which we listen"],
         ["port", "p", "tcp:22", "Port on which to listen"],
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
    if pamauth is not None:
        from twisted.cred.checkers import PluggableAuthenticationModulesChecker
        t.portal.registerChecker(PluggableAuthenticationModulesChecker())
    t.dataRoot = config['data']
    t.moduliRoot = config['moduli'] or config['data']
    port = config['port']
    if config['interface']:
        # Add warning here
        port += ':interface='+config['interface']
    return strports.service(port, t)
