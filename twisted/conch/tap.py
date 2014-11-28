# -*- test-case-name: twisted.conch.test.test_tap -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Support module for making SSH servers with twistd.
"""

from twisted.conch import unix
from twisted.conch import checkers as conch_checkers
from twisted.conch.openssh_compat import factory
from twisted.cred import portal, checkers, strcred
from twisted.python import usage
from twisted.application import strports
try:
    from twisted.cred import pamauth
except ImportError:
    pamauth = None



class Options(usage.Options, strcred.AuthOptionMixin):
    synopsis = "[-i <interface>] [-p <port>] [-d <dir>] "
    longdesc = ("Makes a Conch SSH server.  If no authentication methods are "
        "specified, the default authentication methods are UNIX passwords, "
        "SSH public keys, and PAM if it is available.  If --auth options are "
        "passed, only the measures specified will be used.")
    optParameters = [
        ["interface", "i", "", "local interface to which we listen"],
        ["port", "p", "tcp:22", "Port on which to listen"],
        ["data", "d", "/etc", "directory to look for host keys in"],
        ["moduli", "", None, "directory to look for moduli in "
            "(if different from --data)"]
    ]
    compData = usage.Completions(
        optActions={"data": usage.CompleteDirs(descr="data directory"),
                    "moduli": usage.CompleteDirs(descr="moduli directory"),
                    "interface": usage.CompleteNetInterfaces()}
        )


    def __init__(self, *a, **kw):
        usage.Options.__init__(self, *a, **kw)

        # call the default addCheckers (for backwards compatibility) that will
        # be used if no --auth option is provided - note that conch's
        # UNIXPasswordDatabase is used, instead of twisted.plugins.cred_unix's
        # checker
        super(Options, self).addChecker(conch_checkers.UNIXPasswordDatabase())
        super(Options, self).addChecker(conch_checkers.SSHPublicKeyDatabase())
        if pamauth is not None:
            super(Options, self).addChecker(
                checkers.PluggableAuthenticationModulesChecker())
        self._usingDefaultAuth = True


    def addChecker(self, checker):
        """
        Add the checker specified.  If any checkers are added, the default
        checkers are automatically cleared and the only checkers will be the
        specified one(s).
        """
        if self._usingDefaultAuth:
            self['credCheckers'] = []
            self['credInterfaces'] = {}
            self._usingDefaultAuth = False
        super(Options, self).addChecker(checker)



def makeService(config):
    """
    Construct a service for operating a SSH server.

    @param config: An L{Options} instance specifying server options, including
    where server keys are stored and what authentication methods to use.

    @return: An L{IService} provider which contains the requested SSH server.
    """

    t = factory.OpenSSHFactory()

    r = unix.UnixSSHRealm()
    t.portal = portal.Portal(r, config.get('credCheckers', []))
    t.dataRoot = config['data']
    t.moduliRoot = config['moduli'] or config['data']

    port = config['port']
    if config['interface']:
        # Add warning here
        port += ':interface=' + config['interface']
    return strports.service(port, t)
