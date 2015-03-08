# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# You can run this .tac file directly with:
#    twistd -ny demo_insults.tac

"""Various simple terminal manipulations using the insults module.

This demo sets up two listening ports: one on 6022 which accepts ssh
connections; one on 6023 which accepts telnet connections.  No login
for the telnet server is required; for the ssh server, \"username\" is
the username and \"password\" is the password.

The TerminalProtocol subclass defined here ignores most user input
(except to print it out to the server log) and spends the duration of
the connection drawing (the author's humble approximation of)
raindrops at random locations on the client's terminal.  +, -, *, and
/ are respected and each adjusts an aspect of the timing of the
animation process.
"""

import random, string

from twisted.python import log
from twisted.internet import protocol, task
from twisted.application import internet, service
from twisted.cred import checkers, portal

from twisted.conch.insults import insults
from twisted.conch.telnet import TelnetTransport, TelnetBootstrapProtocol
from twisted.conch.manhole_ssh import ConchFactory, TerminalRealm

class DrawingFinished(Exception):
    """Sentinel exception, raised when no \"frames\" for a particular
    \"animation\" remain to be drawn.
    """

class Drawable:
    """Representation of an animation.

    Constructed with a protocol instance and a coordinate on the
    screen, waits for invocations of iterate() at which point it
    erases the previous frame of the animation and draws the next one,
    using its protocol instance and always placing the upper left hand
    corner of the frame at the given coordinates.

    Frames are defined with draw_ prefixed methods.  Erasure is
    performed by erase_ prefixed methods.
    """
    n = 0

    def __init__(self, proto, col, line):
        self.proto = proto
        self.col = col
        self.line = line

    def drawLines(self, s):
        lines = s.splitlines()
        c = self.col
        line = self.line
        for l in lines:
            self.proto.cursorPosition(c - len(lines) / 2, line)
            self.proto.write(l)
            line += 1

    def iterate(self):
        getattr(self, 'erase_' + str(self.n))()
        self.n += 1
        f = getattr(self, 'draw_' + str(self.n), None)
        if f is None:
            raise DrawingFinished()
        f()

    def erase_0(self):
        pass


class Splat(Drawable):
    HEIGHT = 5
    WIDTH = 11

    def draw_1(self):
        # . .
        #. . .
        # . .
        self.drawLines(' . .\n. . .\n . .')

    def erase_1(self):
        self.drawLines('    \n     \n    ')

    def draw_2(self):
        #  . . . .
        # . o o o .
        #. o o o o .
        # . o o o .
        #  . . . .
        self.drawLines('  . . . .\n . o o o .\n. o o o o .\n . o o o .\n  . . . .')

    def erase_2(self):
        self.drawLines('         \n          \n           \n          \n         ')

    def draw_3(self):
        #  o o o o
        # o O O O o
        #o O O O O o
        # o O O O o
        #  o o o o
        self.drawLines('  o o o o\n o O O O o\no O O O O o\n o O O O o\n  o o o o')

    erase_3 = erase_2

    def draw_4(self):
        #  O O O O
        # O . . . O
        #O . . . . O
        # O . . . O
        #  O O O O
        self.drawLines('  O O O O\n O . . . O\nO . . . . O\n O . . . O\n  O O O O')

    erase_4 = erase_3

    def draw_5(self):
        #  . . . .
        # .       .
        #.         .
        # .       .
        #  . . . .
        self.drawLines('  . . . .\n .       .\n.         .\n .       .\n  . . . .')

    erase_5 = erase_4

class Drop(Drawable):
    WIDTH = 3
    HEIGHT = 4

    def draw_1(self):
        # o
        self.drawLines(' o')

    def erase_1(self):
        self.drawLines('  ')

    def draw_2(self):
        # _
        #/ \
        #\./
        self.drawLines(' _ \n/ \\\n\\./')

    def erase_2(self):
        self.drawLines('  \n   \n   ')

    def draw_3(self):
        # O
        self.drawLines(' O')

    def erase_3(self):
        self.drawLines('  ')

class DemoProtocol(insults.TerminalProtocol):
    """Draws random things at random places on the screen.
    """
    width = 80
    height = 24

    interval = 0.1
    rate = 0.05

    def connectionMade(self):
        self.run()

    def connectionLost(self, reason):
        self._call.stop()
        del self._call

    def run(self):
        # Clear the screen, matey
        self.terminal.eraseDisplay()

        self._call = task.LoopingCall(self._iterate)
        self._call.start(self.interval)

    def _iterate(self):
        cls = random.choice((Splat, Drop))

        # Move to a random location on the screen
        col = random.randrange(self.width - cls.WIDTH) + cls.WIDTH
        line = random.randrange(self.height - cls.HEIGHT) + cls.HEIGHT

        s = cls(self.terminal, col, line)

        c = task.LoopingCall(s.iterate)
        c.start(self.rate).addErrback(lambda f: f.trap(DrawingFinished)).addErrback(log.err)

    # ITerminalListener
    def terminalSize(self, width, height):
        self.width = width
        self.height = height

    def unhandledControlSequence(self, seq):
        log.msg("Client sent something weird: %r" % (seq,))

    def keystrokeReceived(self, keyID, modifier):
        if keyID == '+':
            self.interval /= 1.1
        elif keyID == '-':
            self.interval *= 1.1
        elif keyID == '*':
            self.rate /= 1.1
        elif keyID == '/':
            self.rate *= 1.1
        else:
            log.msg("Client sent: %r" % (keyID,))
            return

        self._call.stop()
        self._call = task.LoopingCall(self._iterate)
        self._call.start(self.interval)


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

makeService({'protocolFactory': DemoProtocol,
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)
