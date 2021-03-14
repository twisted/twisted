# Do everything properly, and componentize
from twisted.application import internet, service, strports
from twisted.internet import protocol, reactor, defer, endpoints
from twisted.words.protocols import irc
from twisted.protocols import basic
from twisted.python import components
from twisted.web import resource, server, static, xmlrpc
from zope.interface import Interface, implementer
import cgi


class IFingerService(Interface):
    def getUser(user):
        """Return a deferred returning L{bytes}"""

    def getUsers():
        """Return a deferred returning a L{list} of L{bytes}"""


class IFingerSetterService(Interface):
    def setUser(user, status):
        """Set the user's status to something"""


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


class IFingerFactory(Interface):
    def getUser(user):
        """Return a deferred returning L{bytes}"""

    def buildProtocol(addr):
        """Return a protocol returning L{bytes}"""


@implementer(IFingerFactory)
class FingerFactoryFromService(protocol.ServerFactory):
    protocol = FingerProtocol

    def __init__(self, service):
        self.service = service

    def getUser(self, user):
        return self.service.getUser(user)


components.registerAdapter(FingerFactoryFromService, IFingerService, IFingerFactory)


class FingerSetterProtocol(basic.LineReceiver):
    def connectionMade(self):
        self.lines = []

    def lineReceived(self, line):
        self.lines.append(line)

    def connectionLost(self, reason):
        if len(self.lines) == 2:
            self.factory.setUser(*self.lines)


class IFingerSetterFactory(Interface):
    def setUser(user, status):
        """Return a deferred returning L{bytes}"""

    def buildProtocol(addr):
        """Return a protocol returning L{bytes}"""


@implementer(IFingerSetterFactory)
class FingerSetterFactoryFromService(protocol.ServerFactory):
    protocol = FingerSetterProtocol

    def __init__(self, service):
        self.service = service

    def setUser(self, user, status):
        self.service.setUser(user, status)


components.registerAdapter(
    FingerSetterFactoryFromService, IFingerSetterService, IFingerSetterFactory
)


class IRCReplyBot(irc.IRCClient):
    def connectionMade(self):
        self.nickname = self.factory.nickname
        irc.IRCClient.connectionMade(self)

    def privmsg(self, user, channel, msg):
        user = user.split("!")[0]
        if self.nickname.lower() == channel.lower():
            d = self.factory.getUser(msg)
            d.addErrback(catchError)
            d.addCallback(lambda m: f"Status of {msg}: {m}")
            d.addCallback(lambda m: self.msg(user, m))


class IIRCClientFactory(Interface):

    """
    @ivar nickname
    """

    def getUser(user):
        """Return a deferred returning a string"""

    def buildProtocol(addr):
        """Return a protocol"""


@implementer(IIRCClientFactory)
class IRCClientFactoryFromService(protocol.ClientFactory):
    protocol = IRCReplyBot
    nickname = None

    def __init__(self, service):
        self.service = service

    def getUser(self, user):
        return self.service.getUser(user)


components.registerAdapter(
    IRCClientFactoryFromService, IFingerService, IIRCClientFactory
)


@implementer(resource.IResource)
class UserStatusTree(resource.Resource):
    def __init__(self, service):
        resource.Resource.__init__(self)
        self.service = service
        self.putChild("RPC2", UserStatusXR(self.service))

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


components.registerAdapter(UserStatusTree, IFingerService, resource.IResource)


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


@implementer(IFingerService, IFingerSetterService)
class MemoryFingerService(service.Service):
    def __init__(self, users):
        self.users = users

    def getUser(self, user):
        return defer.succeed(self.users.get(user, b"No such user"))

    def getUsers(self):
        return defer.succeed(list(self.users.keys()))

    def setUser(self, user, status):
        self.users[user] = status


application = service.Application("finger", uid=1, gid=1)
f = MemoryFingerService({b"moshez": b"Happy and well"})
serviceCollection = service.IServiceCollection(application)
strports.service("tcp:79", IFingerFactory(f)).setServiceParent(serviceCollection)
strports.service("tcp:8000", server.Site(resource.IResource(f))).setServiceParent(
    serviceCollection
)
i = IIRCClientFactory(f)
i.nickname = "fingerbot"
internet.ClientService(
    endpoints.clientFromString(reactor, "tcp:irc.freenode.org:6667"), i
).setServiceParent(serviceCollection)
strports.service(
    "tcp:1079:interface=127.0.0.1", IFingerSetterFactory(f)
).setServiceParent(serviceCollection)
