
import tty, sys, termios

from twisted.internet import reactor, stdio, protocol, defer
from twisted.python import failure, reflect

from insults import ServerProtocol
from stdio import ConsoleManhole

class UnexpectedOutputError(Exception):
    pass

class TerminalProcessProtocol(protocol.ProcessProtocol):
    def __init__(self, proto):
        self.proto = proto
        self.onConnection = defer.Deferred()

    def connectionMade(self):
        self.proto.makeConnection(self)
        self.onConnection.callback(None)
        self.onConnection = None

    def write(self, bytes):
        self.transport.write(bytes)

    def outReceived(self, bytes):
        self.proto.dataReceived(bytes)

    def errReceived(self, bytes):
        self.transport.loseConnection()
        if self.proto is not None:
            self.proto.connectionLost(failure.Failure(UnexpectedOutputError(bytes)))
            self.proto = None

    def connectionLost(self, reason):
        if self.proto is not None:
            self.proto.connectionLost(reason)
            self.proto = None

def runWithProtocol(klass):
    oldSettings = termios.tcgetattr(sys.stdin.fileno())
    tty.setraw(sys.stdin.fileno())
    try:
        p = ServerProtocol(klass)
        stdio.StandardIO(p)
        reactor.run()
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, oldSettings)
        print

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if argv:
        klass = reflect.namedClass(argv[0])
    else:
        klass = ConsoleManhole
    runWithProtocol(klass)

if __name__ == '__main__':
    main()
