
import insults
from telnet import TelnetTransport, TelnetBootstrapProtocol
from ssh import session, TerminalUser, TerminalSession, TerminalSessionTransport, ConchFactory

from twisted.python import components
from twisted.internet import protocol
from twisted.application import internet, service

class TerminalForwardingProtocol(insults.ServerProtocol):
    def terminalSize(self, width, height):
        self.protocol.terminalSize(width, height)

def makeService(args):
    # SSH classes
    class ConstructedSessionTransport(TerminalSessionTransport):
        protocolFactory = staticmethod(lambda: TerminalForwardingProtocol(args['protocolFactory']))

    class ConstructedSession(TerminalSession):
        transportFactory = ConstructedSessionTransport

    # XXX Can only support one handler via ssh per process!  Muy suck.
    components.registerAdapter(ConstructedSession, TerminalUser, session.ISession)

    f = protocol.ServerFactory()
    f.protocol = lambda: TelnetTransport(TelnetBootstrapProtocol, TerminalForwardingProtocol, args['protocolFactory'])
    tsvc = internet.TCPServer(args['telnet'], f)

    f = ConchFactory()
    csvc = internet.TCPServer(args['ssh'], f)

    m = service.MultiService()
    tsvc.setServiceParent(m)
    csvc.setServiceParent(m)
    return m

