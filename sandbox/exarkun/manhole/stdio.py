
import tty, sys, termios

from twisted.internet import reactor, stdio

from manhole import Manhole
from insults import ServerProtocol

class ConsoleManhole(Manhole):
    def __init__(self, *a, **kw):
        Manhole.__init__(self, *a, **kw)
        self.keyHandlers['\n'] = self.keyHandlers.pop('\r')

def main():
    oldSettings = termios.tcgetattr(sys.stdin.fileno())
    tty.setraw(sys.stdin.fileno())
    try:
        p = ServerProtocol()
        p.handlerFactory = Manhole
        stdio.StandardIO(p)
        reactor.run()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, oldSettings)

if __name__ == '__main__':
    main()
