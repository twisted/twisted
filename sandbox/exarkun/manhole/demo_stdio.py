
import tty, sys, termios

from twisted.internet import reactor, stdio as stdio

from insults import ServerProtocol
from stdio import ConsoleManhole

def main():
    oldSettings = termios.tcgetattr(sys.stdin.fileno())
    tty.setraw(sys.stdin.fileno())
    try:
        p = ServerProtocol(ConsoleManhole)
        stdio.StandardIO(p)
        reactor.run()
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, oldSettings)
        print

if __name__ == '__main__':
    main()
