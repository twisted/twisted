
from manhole import Manhole

class ConsoleManhole(Manhole):
    def handle_QUIT(self):
        self.transport.loseConnection()
        from twisted.internet import reactor
        reactor.stop()

