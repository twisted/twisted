# Do everything properly, and componentize
from twisted.application import internet, service
from twisted.internet import protocol, reactor, defer
from twisted.protocols import basic, irc
from twisted.python import components
from twisted.web import resource, server, static, xmlrpc, microdom
from twisted.web.woven import page, model, interfaces
import cgi

class IFingerService(components.Interface):

    def getUser(self, user):
        """Return a deferred returning a string"""

    def getUsers(self):
        """Return a deferred returning a list of strings"""

class IFingerSetterService(components.Interface):

    def setUser(self, user, status):
        """Set the user's status to something"""

def catchError(err):
    return "Internal error in server"

class FingerProtocol(basic.LineReceiver):

    def lineReceived(self, user):
        d = self.factory.getUser(user)
        d.addErrback(catchError)
        def writeValue(value):
            self.transport.write(value+'\n')
            self.transport.loseConnection()
        d.addCallback(writeValue)


class IFingerFactory(components.Interface):

    def getUser(self, user):
        """Return a deferred returning a string"""

    def buildProtocol(self, addr):
        """Return a protocol returning a string"""


class FingerFactoryFromService(protocol.ServerFactory):

    __implements__ = IFingerFactory,

    protocol = FingerProtocol

    def __init__(self, service):
        self.service = service

    def getUser(self, user):
        return self.service.getUser(user)

components.registerAdapter(FingerFactoryFromService,
                           IFingerService,
                           IFingerFactory)

class FingerSetterProtocol(basic.LineReceiver):

    def connectionMade(self):
        self.lines = []

    def lineReceived(self, line):
        self.lines.append(line)

    def connectionLost(self, reason):
        if len(self.lines) == 2:
            self.factory.setUser(*self.lines)


class IFingerSetterFactory(components.Interface):

    def setUser(self, user, status):
        """Return a deferred returning a string"""

    def buildProtocol(self, addr):
        """Return a protocol returning a string"""


class FingerSetterFactoryFromService(protocol.ServerFactory):

    __implements__ = IFingerSetterFactory,

    protocol = FingerSetterProtocol

    def __init__(self, service):
        self.service = service

    def setUser(self, user, status):
        self.service.setUser(user, status)


components.registerAdapter(FingerSetterFactoryFromService,
                           IFingerSetterService,
                           IFingerSetterFactory)

class IRCReplyBot(irc.IRCClient):

    def connectionMade(self):
        self.nickname = self.factory.nickname
        irc.IRCClient.connectionMade(self)

    def privmsg(self, user, channel, msg):
        user = user.split('!')[0]
        if self.nickname.lower() == channel.lower():
            d = self.factory.getUser(msg)
            d.addErrback(catchError)
            d.addCallback(lambda m: "Status of %s: %s" % (msg, m))
            d.addCallback(lambda m: self.msg(user, m))


class IIRCClientFactory(components.Interface):

    """
    @ivar nickname
    """

    def getUser(self, user):
        """Return a deferred returning a string"""

    def buildProtocol(self, addr):
        """Return a protocol"""


class IRCClientFactoryFromService(protocol.ClientFactory):

    __implements__ = IIRCClientFactory,

    protocol = IRCReplyBot
    nickname = None

    def __init__(self, service):
        self.service = service

    def getUser(self, user):
        return self.service.getUser(user)

components.registerAdapter(IRCClientFactoryFromService,
                           IFingerService,
                           IIRCClientFactory)

class UsersModel(model.MethodModel):

    def initialize(self, *args, **kwargs):
        self.service=args[0]

    def wmfactory_users(self, request):
        return self.service.getUsers()

components.registerAdapter(UsersModel, IFingerService, interfaces.IModel)

class UserStatusTree(page.Page):

    template = """<html><head><title>Users</title></head><body>
    <h1>Users</h1>
    <ul model="users" view="List">
    <li pattern="listItem"><a view="Anchor" /></li>
    </ul></body></html>"""

    def initialize(self, *args, **kwargs):
        self.service=args[0]

    def getDynamicChild(self, path, request):
        return UserStatus(user=path, service=self.service)

    def wchild_RPC2 (self, request):
        return UserStatusXR(self.service)

components.registerAdapter(UserStatusTree, IFingerService, resource.IResource)


class UserStatus(page.Page):

    template='''<html><head><title view="Text" model="user"/></head>
    <body><h1 view="Text" model="user"/>
    <p model="status" view="Text" />
    </body></html>'''

    def initialize(self, **kwargs):
        self.user = kwargs['user']
        self.service = kwargs['service']

    def wmfactory_user(self, request):
        return self.user

    def wmfactory_status(self, request):
        return self.service.getUser(self.user)


class UserStatusXR(xmlrpc.XMLRPC):

    def __init__(self, service):
        xmlrpc.XMLRPC.__init__(self)
        self.service = service

    def xmlrpc_getUser(self, user):
        return self.service.getUser(user)

    def xmlrpc_getUsers(self):
        return self.service.getUsers()


class FingerService(service.Service):

    __implements__ = IFingerService,

    def __init__(self, filename):
        self.filename = filename
        self._read()

    def _read(self):
        self.users = {}
        for line in file(self.filename):
            user, status = line.split(':', 1)
            user = user.strip()
            status = status.strip()
            self.users[user] = status
        self.call = reactor.callLater(30, self._read)

    def getUser(self, user):
        return defer.succeed(self.users.get(user, "No such user"))

    def getUsers(self):
        return defer.succeed(self.users.keys())


application = service.Application('finger', uid=1, gid=1)
f = FingerService('/etc/users')
serviceCollection = service.IServiceCollection(application)
internet.TCPServer(79, IFingerFactory(f)
                   ).setServiceParent(serviceCollection)
internet.TCPServer(8000, server.Site(resource.IResource(f))
                   ).setServiceParent(serviceCollection)
i = IIRCClientFactory(f)
i.nickname = 'fingerbot'
internet.TCPClient('irc.freenode.org', 6667, i
                   ).setServiceParent(serviceCollection)
