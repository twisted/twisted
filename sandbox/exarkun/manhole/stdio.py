
import tty, sys, termios

from twisted.internet import reactor, stdio

from manhole import Manhole
from insults import ServerProtocol

class ConsoleManhole(Manhole):
    def __init__(self, *a, **kw):
        Manhole.__init__(self, *a, **kw)
        self.keyHandlers['\x03'] = self.handle_INT
        self.keyHandlers['\x04'] = self.handle_QUIT
        self.keyHandlers['\x1c'] = self.handle_QUIT

    def handle_INT(self):
        self.proto.nextLine()
        self.proto.write("KeyboardInterrupt")
        self.proto.nextLine()
        self.proto.write(self.ps[self.pn])
        self.lineBuffer = []
        self.lineBufferIndex = 0

    def handle_QUIT(self):
        self.proto.reset()
        reactor.stop()

def main():
    oldSettings = termios.tcgetattr(sys.stdin.fileno())
    tty.setraw(sys.stdin.fileno())
    try:
        p = ServerProtocol()
        p.handlerFactory = ConsoleManhole
        stdio.StandardIO(p)
        reactor.run()
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, oldSettings)
        print

if __name__ == '__main__':
    main()
