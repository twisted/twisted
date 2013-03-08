# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
TAP plugin for creating telnet- and ssh-accessible manhole servers.

@author: Jp Calderone
"""

from zope.interface import implements

from twisted.internet import protocol
from twisted.application import service, strports
from twisted.conch.ssh import session
from twisted.conch import interfaces as iconch
from twisted.cred import portal, checkers
from twisted.python import usage

from twisted.conch.insults import insults
from twisted.conch import manhole, manhole_ssh, telnet

class makeTelnetProtocol:
    def __init__(self, portal):
        self.portal = portal

    def __call__(self):
        auth = telnet.AuthenticatingTelnetProtocol
        args = (self.portal,)
        return telnet.TelnetTransport(auth, *args)

class chainedProtocolFactory:
    def __init__(self, namespace):
        self.namespace = namespace
    
    def __call__(self):
        return insults.ServerProtocol(manhole.ColoredManhole, self.namespace)

class _StupidRealm:
    implements(portal.IRealm)

    def __init__(self, proto, *a, **kw):
        self.protocolFactory = proto
        self.protocolArgs = a
        self.protocolKwArgs = kw

    def requestAvatar(self, avatarId, *interfaces):
        if telnet.ITelnetProtocol in interfaces:
            return (telnet.ITelnetProtocol,
                    self.protocolFactory(*self.protocolArgs, **self.protocolKwArgs),
                    lambda: None)
        raise NotImplementedError()

class Options(usage.Options):
    optParameters = [
        ["telnetPort", "t", None, "strports description of the address on which to listen for telnet connections"],
        ["sshPort", "s", None, "strports description of the address on which to listen for ssh connections"],
        ["passwd", "p", "/etc/passwd", "name of a passwd(5)-format username/password file"]]

    def __init__(self):
        usage.Options.__init__(self)
        self['namespace'] = None
    
    def postOptions(self):
        if self['telnetPort'] is None and self['sshPort'] is None:
            raise usage.UsageError("At least one of --telnetPort and --sshPort must be specified")

def makeService(options):
    """Create a manhole server service.

    @type options: C{dict}
    @param options: A mapping describing the configuration of
    the desired service.  Recognized key/value pairs are::

        "telnetPort": strports description of the address on which
                      to listen for telnet connections.  If None,
                      no telnet service will be started.

        "sshPort": strports description of the address on which to
                   listen for ssh connections.  If None, no ssh
                   service will be started.

        "namespace": dictionary containing desired initial locals
                     for manhole connections.  If None, an empty
                     dictionary will be used.

        "passwd": Name of a passwd(5)-format username/password file.

    @rtype: L{twisted.application.service.IService}
    @return: A manhole service.
    """

    svc = service.MultiService()

    namespace = options['namespace']
    if namespace is None:
        namespace = {}

    checker = checkers.FilePasswordDB(options['passwd'])

    if options['telnetPort']:
        telnetRealm = _StupidRealm(telnet.TelnetBootstrapProtocol,
                                   insults.ServerProtocol,
                                   manhole.ColoredManhole,
                                   namespace)

        telnetPortal = portal.Portal(telnetRealm, [checker])

        telnetFactory = protocol.ServerFactory()
        telnetFactory.protocol = makeTelnetProtocol(telnetPortal)
        telnetService = strports.service(options['telnetPort'],
                                         telnetFactory)
        telnetService.setServiceParent(svc)

    if options['sshPort']:
        sshRealm = manhole_ssh.TerminalRealm()
        sshRealm.chainedProtocolFactory = chainedProtocolFactory(namespace)

        sshPortal = portal.Portal(sshRealm, [checker])
        sshFactory = manhole_ssh.ConchFactory(sshPortal)
        sshService = strports.service(options['sshPort'],
                                      sshFactory)
        sshService.setServiceParent(svc)

    return svc
