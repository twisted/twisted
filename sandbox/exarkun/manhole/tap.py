
from zope.interface import implements

from twisted.internet import protocol
from twisted.application import service, strports
from twisted.conch.ssh import session
from twisted.cred import portal
from twisted.python import components

import insults, manhole, ssh, telnet

class TerminalForwardingProtocol(insults.ServerProtocol):
    def terminalSize(self, width, height):
        self.protocol.terminalSize(width, height)

class ConstructedSessionTransport(ssh.TerminalSessionTransport):
    # Empty, but see below.
    pass

class ConstructedSession(ssh.TerminalSession):
    transportFactory = ConstructedSessionTransport

components.registerAdapter(ConstructedSession, ssh.TerminalUser, session.ISession)

def makeTelnetProtocol(portal, namespace):
    def protocol():
        auth = telnet.AuthenticatingTelnetProtocol
        args = (portal,
                telnet.TelnetBootstrapProtocol,
                TerminalForwardingProtocol,
                manhole.ColoredManhole,
                namespace)
        return telnet.TelnetTransport(auth, *args)
    return protocol

class _StupidRealm:
    implements(portal.IRealm)

    def requestAvatar(self, avatarId, *interfaces):
        if telnet.ITelnetProtocol in interfaces:
            return telnet.ITelnetProtocol, None, lambda: None

def makeService(options):
    """Create a manhole server service.

    @type options: C{dict}
    @param options: A mapping describing the configuration of
    the desired service.  Recognized key/value pairs are:

        "telnetPort": strports description of the address on which
                      to listen for telnet connections.  If None,
                      no telnet service will be started.

        "sshPort": strports description of the address on which to
                   listen for ssh connections.  If None, no ssh
                   service will be started.

        "namespace": dictionary containing desired initial locals
                     for manhole connections.  If None, an empty
                     dictionary will be used.

        "checkers": A sequence of cred checkers used to authenticate
                    logins.  Must contain at least one checker.

    @rtype: L{twisted.application.service.IService}
    @return: A manhole service.
    """

    svc = service.MultiService()

    realm = _StupidRealm()
    p = portal.Portal(realm)
    for c in options['checkers']:
        p.registerChecker(c)

    namespace = options['namespace']
    if namespace is None:
        namespace = {}

    if options['telnetPort']:
        telnetFactory = protocol.ServerFactory()
        telnetFactory.protocol = makeTelnetProtocol(p, namespace)
        telnetService = strports.service(options['telnetPort'],
                                         telnetFactory)
        telnetService.setServiceParent(svc)

    if options['sshPort']:
        def protocolFactory():
            return TerminalForwardingProtocol(manhole.ColoredManhole, namespace)
        protocolFactory = staticmethod(protocolFactory)
        ConstructedSessionTransport.protocolFactory = protocolFactory

        sshFactory = ssh.ConchFactory(options['checkers'])
        sshService = strports.service(options['sshPort'],
                                      sshFactory)
        sshService.setServiceParent(svc)

    return svc
