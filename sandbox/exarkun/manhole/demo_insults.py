
import random, string

from twisted.application import service
from twisted.internet import task
from twisted.python import log

import insults

class DrawingFinished(Exception):
    pass

class Drawable:
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
    width = 80
    height = 24

    interval = 0.1
    rate = 0.05

    def connectionMade(self):
        self.run()

    def run(self):
        # Clear the screen, matey
        self.transport.eraseDisplay()

        self._call = task.LoopingCall(self._iterate)
        self._call.start(self.interval)

    def _iterate(self):
        cls = random.choice((Splat, Drop))

        # Move to a random location on the screen
        col = random.randrange(self.width - cls.WIDTH) + cls.WIDTH
        line = random.randrange(self.height - cls.HEIGHT) + cls.HEIGHT

        s = cls(self.transport, col, line)

        c = task.LoopingCall(s.iterate)
        c.start(self.rate).addErrback(lambda f: f.trap(DrawingFinished)).addErrback(log.err)

    # ITerminalListener
    def terminalSize(self, width, height):
        self.width = width
        self.height = height

    def unhandledControlSequence(self, seq):
        log.msg("Client sent something weird: %r" % (seq,))

    def keystrokeReceived(self, keyID):
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


application = service.Application("Insults Demo App")

from demolib import makeService
makeService({'protocolFactory': DemoProtocol,
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)
