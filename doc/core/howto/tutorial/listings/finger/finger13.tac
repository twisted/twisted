# Fix asymmetry
from twisted.application import internet, service
from twisted.internet import protocol, reactor, defer
from twisted.protocols import basic
class FingerProtocol(basic.LineReceiver):
    def lineReceived(self, user):
        self.factory.getUser(user
        ).addErrback(lambda _: "Internal error in server"
        ).addCallback(lambda m:
                      (self.transport.write(m+"\r\n"),
                       self.transport.loseConnection()))

class FingerSetterProtocol(basic.LineReceiver):
    def connectionMade(self): self.lines = []
    def lineReceived(self, line): self.lines.append(line)
    def connectionLost(self,reason): self.factory.setUser(*self.lines[:2])
    # first line: user   second line: status

class FingerService(service.Service):
    def __init__(self, **kwargs):
        self.users = kwargs
    def getUser(self, user):
        return defer.succeed(self.users.get(user, "No such user"))
    def getFingerFactory(self):
        f = protocol.ServerFactory()
        f.protocol, f.getUser = FingerProtocol, self.getUser
        return f
    def getFingerSetterFactory(self):
        f = protocol.ServerFactory()
        f.protocol, f.setUser = FingerSetterProtocol, self.users.__setitem__
        return f

application = service.Application('finger', uid=1, gid=1)
f = FingerService(moshez='Happy and well')
serviceCollection = service.IServiceCollection(application)
internet.TCPServer(79,f.getFingerFactory()
                   ).setServiceParent(serviceCollection)
internet.TCPServer(1079,f.getFingerSetterFactory()
                   ).setServiceParent(serviceCollection)
