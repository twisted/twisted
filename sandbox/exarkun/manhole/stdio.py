
from manhole import ColoredManhole

class ConsoleManhole(ColoredManhole):
    lineDelimiter = '\r'

    def handle_QUIT(self):
        self.transport.loseConnection()
        from twisted.internet import reactor
        reactor.stop()
