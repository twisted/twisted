# Read from file, announce on the web!
import cgi

from twisted.application import service, strports
from twisted.internet import defer, protocol, reactor
from twisted.protocols import basic
from twisted.web import resource, server, static


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


class FingerResource(resource.Resource):
    def __init__(self, users):
        self.users = users
        resource.Resource.__init__(self)

    # we treat the path as the username
    def getChild(self, username, request):
        """
        'username' is L{bytes}.
        'request' is a 'twisted.web.server.Request'.
        """
        messagevalue = self.users.get(username)
        if messagevalue:
            messagevalue = messagevalue.decode("ascii")
        if username:
            username = username.decode("ascii")
        username = cgi.escape(username)
        if messagevalue is not None:
            messagevalue = cgi.escape(messagevalue)
            text = f"<h1>{username}</h1><p>{messagevalue}</p>"
        else:
            text = f"<h1>{username}</h1><p>No such user</p>"
        text = text.encode("ascii")
        return static.Data(text, "text/html")


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
        r = FingerResource(self.users)
        return r

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
