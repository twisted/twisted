
import tty, sys, termios

from twisted.internet import reactor, stdio

from manhole import Manhole
from insults import ServerProtocol

class ConsoleManhole(Manhole):
    def __init__(self, *a, **kw):
        Manhole.__init__(self, *a, **kw)

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
