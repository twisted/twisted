
from twisted.internet import protocol
from twisted.application import service, strports
from twisted.conch.ssh import session

import insults, manhole, ssh

from telnet import TelnetTransport, TelnetBootstrapProtocol

class TerminalForwardingProtocol(insults.ServerProtocol):
    def terminalSize(self, width, height):
        self.protocol.terminalSize(width, height)

class ConstructedSessionTransport(ssh.TerminalSessionTransport):
    def protocolFactory():
        return TerminalForwardingProtocol(args['protocolFactory'])
    protocolFactory = staticmethod(protocolFactory)

class ConstructedSession(ssh.TerminalSession):
    transportFactory = ConstructedSessionTransport

components.registerAdapter(ConstructedSession, ssh.TerminalUser, session.ISession)

def makeTelnetProtocol(portal):
    def protocol():
        auth = AuthenticatingTelnetProtocol(portal,
                                            TelnetBootstrapProtocol,
                                            TerminalForwardingProtocol,
                                            manhole.ColoredManhole))
        return TelnetTransport(auth)
    return protocol

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

    realm = SomeRealm()
    portal = portal.Portal(realm)
    for c in options['checkers']:
        portal.registerChecker(c)

    if options['telnetPort']:
        telnetFactory = protocol.ServerFactory()
        telnetFactory.protocol = makeTelnetProtocol(portal)
        telnetService = strports.service(options['telnetPort'],
                                         telnetFactory)
        telnetService.setServiceParent(svc)

    if options['sshPort']:
        f = ssh.ConchFactory()
