# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# You can run this .tac file directly with:
#    twistd -ny demo_draw.tac

"""A trivial drawing application.

Clients are allowed to connect and spew various characters out over
the terminal.  Spacebar changes the drawing character, while the arrow
keys move the cursor.
"""

from twisted.conch.insults import insults
from twisted.conch.telnet import TelnetTransport, TelnetBootstrapProtocol
from twisted.conch.manhole_ssh import ConchFactory, TerminalRealm

from twisted.internet import protocol
from twisted.application import internet, service
from twisted.cred import checkers, portal

class Draw(insults.TerminalProtocol):
    """Protocol which accepts arrow key and spacebar input and places
    the requested characters onto the terminal.
    """
    cursors = list('!@#$%^&*()_+-=')

    def connectionMade(self):
        self.terminal.eraseDisplay()
        self.terminal.resetModes([insults.modes.IRM])
        self.cursor = self.cursors[0]

    def keystrokeReceived(self, keyID, modifier):
        if keyID == self.terminal.UP_ARROW:
            self.terminal.cursorUp()
        elif keyID == self.terminal.DOWN_ARROW:
            self.terminal.cursorDown()
        elif keyID == self.terminal.LEFT_ARROW:
            self.terminal.cursorBackward()
        elif keyID == self.terminal.RIGHT_ARROW:
            self.terminal.cursorForward()
        elif keyID == ' ':
            self.cursor = self.cursors[(self.cursors.index(self.cursor) + 1) % len(self.cursors)]
        else:
            return
        self.terminal.write(self.cursor)
        self.terminal.cursorBackward()

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

application = service.Application("Insults Demo App")
makeService({'protocolFactory': Draw,
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)
