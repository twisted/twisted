# But let's try and fix setting away messages, shall we?
from twisted.internet import protocol, reactor, defer, app
from twisted.protocols import basic
class FingerProtocol(basic.LineReceiver):
    def lineReceived(self, user):
        self.factory.getUser(user
        ).addErrback(lambda _: "Internal error in server"
        ).addCallback(lambda m:
            (self.transport.write(m+"\r\n"),self.transport.loseConnection()))
class FingerFactory(protocol.ServerFactory):
    protocol = FingerProtocol
    def __init__(self, **kwargs): self.users = kwargs
    def getUser(self, user):
        return defer.succeed(self.users.get(user, "No such user"))
class FingerSetterProtocol(basic.LineReceiver):
      def connectionMade(self): self.lines = []
      def lineReceived(self, line): self.lines.append(line)
      def connectionLost(self): self.factory.setUser(*self.lines)
class FingerSetterFactory(protocol.ServerFactory):
      def __init__(self, ff): self.setUser = self.ff.users.__setitem__
ff = FingerFactory(moshez='Happy and well')
fsf = FingerSetterFactory(ff)
application = app.Application('finger', uid=1, gid=1)
application.listenTCP(79, ff)
application.listenTCP(1079, fsf, interface='127.0.0.1')
