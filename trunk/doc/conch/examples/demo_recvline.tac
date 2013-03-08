# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# You can run this .tac file directly with:
#    twistd -ny demo_recvline.tac

"""Demonstrates line-at-a-time handling with basic line-editing support.

This is a variation on the echo server.  It sets up two listening
ports: one on 6022 which accepts ssh connections; one on 6023 which
accepts telnet connections.  No login for the telnet server is
required; for the ssh server, \"username\" is the username and
\"password\" is the password.

The demo protocol defined in this module is handed a line of input at
a time, which it simply writes back to the connection.
HistoricRecvline, which the demo protocol subclasses, provides basic
line editing and input history features.
"""

from twisted.conch import recvline
from twisted.conch.insults import insults
from twisted.conch.telnet import TelnetTransport, TelnetBootstrapProtocol
from twisted.conch.manhole_ssh import ConchFactory, TerminalRealm

from twisted.internet import protocol
from twisted.application import internet, service
from twisted.cred import checkers, portal

class DemoRecvLine(recvline.HistoricRecvLine):
    """Simple echo protocol.

    Accepts lines of input and writes them back to its connection.  If
    a line consisting solely of \"quit\" is received, the connection
    is dropped.
    """

    def lineReceived(self, line):
        if line == "quit":
            self.terminal.loseConnection()
        self.terminal.write(line)
        self.terminal.nextLine()
        self.terminal.write(self.ps[self.pn])

def makeService(args):
    checker = checkers.InMemoryUsernamePasswordDatabaseDontUse(username="password")

    f = protocol.ServerFactory()
    f.protocol = lambda: TelnetTransport(TelnetBootstrapProtocol,
                                         insults.ServerProtocol,
                                         args['protocolFactory'],
                                         *args.get('protocolArgs', ()),
                                         **args.get('protocolKwArgs', {}))
    tsvc = internet.TCPServer(args['telnet'], f)

    def chainProtocolFactory():
        return insults.ServerProtocol(
            args['protocolFactory'],
            *args.get('protocolArgs', ()),
            **args.get('protocolKwArgs', {}))

    rlm = TerminalRealm()
    rlm.chainedProtocolFactory = chainProtocolFactory
    ptl = portal.Portal(rlm, [checker])
    f = ConchFactory(ptl)
    csvc = internet.TCPServer(args['ssh'], f)

    m = service.MultiService()
    tsvc.setServiceParent(m)
    csvc.setServiceParent(m)
    return m

application = service.Application("Insults RecvLine Demo")

makeService({'protocolFactory': DemoRecvLine,
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)
