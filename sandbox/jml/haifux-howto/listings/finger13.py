# Fix asymmetry
from twisted.internet import protocol, reactor, defer, app
from twisted.protocols import basic
class FingerProtocol(basic.LineReceiver):
    def lineReceived(self, user):
        self.factory.getUser(user
        ).addErrback(lambda _: "Internal error in server"
        ).addCallback(lambda m:
            (self.transport.write(m+"\r\n"),self.transport.loseConnection()))
class FingerSetterProtocol(basic.LineReceiver):
      def connectionMade(self): self.lines = []
      def lineReceived(self, line): self.lines.append(line)
      def connectionLost(self): self.factory.setUser(*self.lines)
class FingerService(app.ApplicationService):
      def __init__(self, *args, **kwargs):
          app.ApplicationService.__init__(self, *args)
          self.users = kwargs
      def getUser(self, user):
          return defer.succeed(self.users.get(u, "No such user"))
      def getFingerFactory(self):
          f = protocol.ServerFactory()
          f.protocol, f.getUser = FingerProtocol, self.getUser
          return f
      def getFingerSetterFactory(self):
          f = protocol.ServerFactory()
          f.protocol, f.setUser = FingerSetterProtocol, self.users.__setitem__
          return f
application = app.Application('finger', uid=1, gid=1)
f = FingerService(application, 'finger', moshez='Happy and well')
application.listenTCP(79, f.getFingerFactory())
application.listenTCP(1079, f.getFingerSetterFactory(), interface='127.0.0.1')
