# Read from file, announce on the web!
from twisted.application import internet, service
from twisted.internet import protocol, reactor, defer
from twisted.protocols import basic
from twisted.web import resource, server, static
import cgi

class FingerProtocol(basic.LineReceiver):
    def lineReceived(self, user):
        self.factory.getUser(user
        ).addErrback(lambda _: "Internal error in server"
        ).addCallback(lambda m:
         (self.transport.write(m+"\r\n"),self.transport.loseConnection()))


class FingerService(service.Service):
    def __init__(self, file):
        self.file = file
        self._read()
    def _read(self):
        self.users = {}
        for line in file(self.file):
            user, status = line.split(':', 1)
            user=user.strip()
            status=status.strip()
            self.users[user] = status
        self.call = reactor.callLater(30, self._read)
    def getUser(self, user):
        return defer.succeed(self.users.get(user, "No such user"))
    def getFingerFactory(self):
        f = protocol.ServerFactory()
        f.protocol, f.getUser = FingerProtocol, self.getUser
        f.startService = self.startService
        return f
    def getResource(self):
        r = resource.Resource()
        r.getChild = (lambda path, request:
                      static.Data('<h1>%s</h1><p>%s</p>' %
                      tuple(map(cgi.escape,
                      [path,self.users.get(path,
                      "No such user.<p/>http://this.site/user")])),
                      'text/html'))
        return r
    
application = service.Application('finger', uid=1, gid=1)
f = FingerService('/etc/users')
serviceCollection = service.IServiceCollection(application)
internet.TCPServer(79,f.getFingerFactory()
                   ).setServiceParent(serviceCollection)
internet.TCPServer(8000,server.Site(f.getResource())
                   ).setServiceParent(serviceCollection)






