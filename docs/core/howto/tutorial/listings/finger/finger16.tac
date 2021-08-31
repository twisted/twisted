# Read from file, announce on the web, irc
import cgi

from twisted.application import internet, service, strports
from twisted.internet import defer, endpoints, protocol, reactor
from twisted.protocols import basic
from twisted.web import resource, server, static
from twisted.words.protocols import irc


class FingerProtocol(basic.LineReceiver):
    def lineReceived(self, user):
        d = self.factory.getUser(user)

        def onError(err):
            return b"Internal error in server"

        d.addErrback(onError)

        def writeResponse(message):
            self.transport.write(message + b"\r\n")
            self.transport.loseConnection()

        d.addCallback(writeResponse)


class IRCReplyBot(irc.IRCClient):
    def connectionMade(self):
        self.nickname = self.factory.nickname
        irc.IRCClient.connectionMade(self)

    def privmsg(self, user, channel, msg):
        user = user.split("!")[0]
        if self.nickname.lower() == channel.lower():
            d = self.factory.getUser(msg.encode("ascii"))

            def onError(err):
                return b"Internal error in server"

            d.addErrback(onError)

            def writeResponse(message):
                message = message.decode("ascii")
                irc.IRCClient.msg(self, user, msg + ": " + message)

            d.addCallback(writeResponse)


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

    def getFingerFactory(self):
        f = protocol.ServerFactory()
        f.protocol = FingerProtocol
        f.getUser = self.getUser
        return f

    def getResource(self):
        def getData(path, request):
            user = self.users.get(path, b"No such users <p/> usage: site/user")
            path = path.decode("ascii")
            user = user.decode("ascii")
            text = f"<h1>{path}</h1><p>{user}</p>"
            text = text.encode("ascii")
            return static.Data(text, "text/html")

        r = resource.Resource()
        r.getChild = getData
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
