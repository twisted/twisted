# Do everything properly
from twisted.internet import protocol, reactor, defer, app
from twisted.protocols import basic, irc
from twisted.web import resource, server, static, xmlrpc
import cgi

def catchError(err):
    return "Internal error in server"

class FingerProtocol(basic.LineReceiver):

    def lineReceived(self, user):
        d = self.factory.getUser(user)
        d.addErrback(catchError)
        def writeValue(value):
            self.transport.write(value)
            self.transport.loseConnection()
        d.addCallback(writeValue)


class FingerSetterProtocol(basic.LineReceiver):

      def connectionMade(self):
          self.lines = []

      def lineReceived(self, line):
          self.lines.append(line)

      def connectionLost(self):
          if len(self.lines) == 2:
              self.factory.setUser(*self.lines)


class IRCReplyBot(irc.IRCClient):

    def connectionMade(self):
        self.nickname = self.factory.nickname
        irc.IRCClient.connectionMade(self)

    def privmsg(self, user, channel, msg):
        if user.lower() == channel.lower():
            d = self.factory.getUser(msg)
            d.addErrback(catchError)
            d.addCallback(lambda m: "Status of %s: %s" % (user, m))
            d.addCallback(lambda m: self.msg(user, m))


class UserStatusTree(resource.Resource):

    def __init__(self, service):
        resource.Resource.__init__(self):
        self.service = service

    def render(self, request):
        d = self.service.getUsers()
        def formatUsers(users):
            l = ["<li><a href="%s">%s</a></li> % (user, user)
                for user in users]
            return '<ul>'+''.join(l)+'</ul>'
        d.addCallback(formatUsers)
        d.addCallback(request.write)
        d.addCallback(lambda _: request.finish())
        return server.NOT_DONE_YET

    def getChild(self, path, request):
        return UserStatus(path, self.service)


class UserStatus(resource.Resource):

    def __init__(self, user, service):
        resource.Resource.__init__(self):
        self.user = user
        self.service = service

    def render(self, request):
        d = self.service.getUser(self.user)
        d.addCallback(cgi.escape)
        d.addCallback(lambda m:
                     '<h1>%s</h1>'%self.user+'<p>%s</p>'%m)
        d.addCallback(request.write)
        d.addCallback(lambda _: request.finish())
        return server.NOT_DONE_YET


class UserStatusXR(xmlrpc.XMLPRC):

    def __init__(self, service):
        xmlrpc.XMLRPC.__init__(self)
        self.service = service

    def xmlrpc_getUser(self, user):
        return self.service.getUser(user)


class FingerService(app.ApplicationService):

      def __init__(self, file, *args, **kwargs):
          app.ApplicationService.__init__(self, *args, **kwargs)
          self.file = file

      def startService(self):
          app.ApplicationService.startService(self)
          self._read()

      def _read(self):
          self.users = {}
          for line in file(self.file):
              user, status = line.split(':', 1)
              self.users[user] = status
          self.call = reactor.callLater(30, self._read)

      def stopService(self):
          app.ApplicationService.stopService(self)
          self.call.cancel()

      def getUser(self, user):
          return defer.succeed(self.users.get(u, "No such user"))

      def getUsers(self):
          return defer.succeed(self.users.keys())

      def getFingerFactory(self):
          f = protocol.ServerFactory()
          f.protocol = FingerProtocol
          f.getUser = self.getUser
          return f

      def getResource(self):
          r = UserStatusTree(self)
          x = UserStatusXR(self)
          r.putChild('RPC2.0', x)
          return r

      def getIRCBot(self, nickname):
          f = protocol.ReconnectingClientFactory()
          f.protocol = IRCReplyBot
          f.nickname = nickname
          f.getUser = self.getUser
          return f

application = app.Application('finger', uid=1, gid=1)
f = FingerService('/etc/users', application, 'finger')
application.listenTCP(79, f.getFingerFactory())
application.listenTCP(80, server.Site(f.getResource()))
application.connectTCP('irc.freenode.org', 6667, f.getIRCBot('finger-bot'))
