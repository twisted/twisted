
from manhole import ColoredManhole

class ConsoleManhole(ColoredManhole):
    def handle_QUIT(self):
        self.transport.loseConnection()
        from twisted.internet import reactor
        reactor.stop()
