# Do everything properly
import cgi

from twisted.application import internet, service, strports
from twisted.internet import defer, endpoints, protocol, reactor
from twisted.protocols import basic
from twisted.web import resource, server, static, xmlrpc
from twisted.words.protocols import irc


def catchError(err):
    return "Internal error in server"


class FingerProtocol(basic.LineReceiver):
    def lineReceived(self, user):
        d = self.factory.getUser(user)
        d.addErrback(catchError)

        def writeValue(value):
            self.transport.write(value + b"\r\n")
            self.transport.loseConnection()

        d.addCallback(writeValue)


class IRCReplyBot(irc.IRCClient):
    def connectionMade(self):
        self.nickname = self.factory.nickname
        irc.IRCClient.connectionMade(self)

    def privmsg(self, user, channel, msg):
        user = user.split("!")[0]
        if self.nickname.lower() == channel.lower():
            d = self.factory.getUser(msg.encode("ascii"))
            d.addErrback(catchError)
            d.addCallback(lambda m: f"Status of {msg}: {m}")
            d.addCallback(lambda m: self.msg(user, m))


class UserStatusTree(resource.Resource):
    def __init__(self, service):
        resource.Resource.__init__(self)
        self.service = service

    def render_GET(self, request):
        d = self.service.getUsers()

        def formatUsers(users):
            l = [f'<li><a href="{user}">{user}</a></li>' for user in users]
            return "<ul>" + "".join(l) + "</ul>"

        d.addCallback(formatUsers)
        d.addCallback(request.write)
        d.addCallback(lambda _: request.finish())
        return server.NOT_DONE_YET

    def getChild(self, path, request):
        if path == "":
            return UserStatusTree(self.service)
        else:
            return UserStatus(path, self.service)


class UserStatus(resource.Resource):
    def __init__(self, user, service):
        resource.Resource.__init__(self)
        self.user = user
        self.service = service

    def render_GET(self, request):
        d = self.service.getUser(self.user)
        d.addCallback(cgi.escape)
        d.addCallback(lambda m: "<h1>%s</h1>" % self.user + "<p>%s</p>" % m)
        d.addCallback(request.write)
        d.addCallback(lambda _: request.finish())
        return server.NOT_DONE_YET


class UserStatusXR(xmlrpc.XMLRPC):
    def __init__(self, service):
        xmlrpc.XMLRPC.__init__(self)
        self.service = service

    def xmlrpc_getUser(self, user):
        return self.service.getUser(user)


class FingerService(service.Service):
    def __init__(self, filename):
        self.filename = filename
        self.users = {}

    def _read(self):
        self.users.clear()
        with open(self.filename, "rb") as f:
            for line in f:
                user, status = line.split(b":", 1)
                user = user.strip()
                status = status.strip()
                self.users[user] = status
        self.call = reactor.callLater(30, self._read)

    def getUser(self, user):
        return defer.succeed(self.users.get(user, b"No such user"))

    def getUsers(self):
        return defer.succeed(list(self.users.keys()))

    def getFingerFactory(self):
        f = protocol.ServerFactory()
        f.protocol = FingerProtocol
        f.getUser = self.getUser
        return f

    def getResource(self):
        r = UserStatusTree(self)
        x = UserStatusXR(self)
        r.putChild("RPC2", x)
        return r

    def getIRCBot(self, nickname):
        f = protocol.ClientFactory()
        f.protocol = IRCReplyBot
        f.nickname = nickname
        f.getUser = self.getUser
        return f

    def startService(self):
        self._read()
        service.Service.startService(self)

    def stopService(self):
        service.Service.stopService(self)
        self.call.cancel()


application = service.Application("finger", uid=1, gid=1)
f = FingerService("/etc/users")
serviceCollection = service.IServiceCollection(application)
f.setServiceParent(serviceCollection)
strports.service("tcp:79", f.getFingerFactory()).setServiceParent(serviceCollection)
strports.service("tcp:8000", server.Site(f.getResource())).setServiceParent(
    serviceCollection
)
internet.ClientService(
    endpoints.clientFromString(reactor, "tcp:irc.freenode.org:6667"),
    f.getIRCBot("fingerbot"),
).setServiceParent(serviceCollection)
