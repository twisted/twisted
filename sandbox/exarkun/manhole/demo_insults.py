
import random, string

from twisted.application import internet, service
from twisted.internet import protocol, task
from twisted.python import log

import insults

class SplatFinished(Exception):
    pass

class Splat:
    n = 0

    def __init__(self, proto, line, col):
        self.proto = proto
        self.line = line
        self.col = col

    def iterate(self):
        getattr(self, 'erase_' + str(self.n))()
        self.n += 1
        f = getattr(self, 'draw_' + str(self.n), None)
        if f is None:
            raise SplatFinished()
        f()

    def erase_0(self):
        pass

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

    def drawLines(self, s):
        lines = s.splitlines()
        c = self.col - len(lines)
        for l in lines:
            self.proto.cursorPosition(c, self.line - len(lines) / 2)
            self.proto.write(l)
            c += 1

class DemoHandler(insults.TerminalListener):
    def run(self, proto):
        # Clear the screen, matey
        proto.eraseDisplay()

        self._call = task.LoopingCall(self._iterate, proto)
        self._call.start(0.5)

    def _iterate(self, proto):
        # Move to a random location on the screen
        line = random.randrange(60) + 20
        col = random.randrange(10) + 10

        s = Splat(proto, line, col)
        c = task.LoopingCall(s.iterate)
        c.start(0.2).addErrback(lambda f: f.trap(SplatFinished)).addErrback(log.err)

    # ITerminalListener
    def unhandledControlSequence(self, seq):
        log.msg("Client sent something weird: %r" % (seq,))

    def keystrokeReceived(self, keyID):
        log.msg("Client sent: %r" % (keyID,))

class SillyProtocol(insults.ServerProtocol):
    def connectionMade(self):
        self.handler = DemoHandler()
        self.handler.run(self)

def makeService(args):
    f = protocol.ServerFactory()
    f.protocol = SillyProtocol
    s = internet.TCPServer(args['port'], f)
    return s

application = service.Application("Insults Demo App")
makeService({'port': 6464}).setServiceParent(application)
