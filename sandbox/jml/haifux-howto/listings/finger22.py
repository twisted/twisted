# Do everything properly, and componentize
from twisted.internet import protocol, reactor, defer, app
from twisted.protocols import basic, irc
from twisted.python import components
from twisted.web import resource, server, static, xmlrpc, microdom
from twisted.web.woven import page, widget
from twisted.spread import pb
from OpenSSL import SSL
import cgi

class IFingerService(components.Interface):

    def getUser(self, user):
        """Return a deferred returning a string"""

    def getUsers(self):
        """Return a deferred returning a list of strings"""

class IFingerSettingService(components.Interface):

    def setUser(self, user, status):
        """Set the user's status to something"""
    
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

components.registerAdapter(FingerFactoryFromService, IFingerService)


class FingerSetterProtocol(basic.LineReceiver):

      def connectionMade(self):
          self.lines = []

      def lineReceived(self, line):
          self.lines.append(line)

      def connectionLost(self):
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
                           IFingerSettingService)
    
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
        return self.service.getUser()

components.registerAdapter(IRCClientFactoryFromService, IFingerService)


class UsersModel(model.MethodModel):

    def __init__(self, service):
        self.service = service

    def wmfactory_users(self):
        return self.service.getUsers()

components.registerAdapter(UsersModel, IFingerService)

class UserStatusTree(page.Page):

    template = """<html><head><title>Users</title><head><body>
                  <h1>Users</h1>
                  <ul model="users" view="List">
                  <li pattern="listItem" /><a view="Link" model="."
                  href="dummy"><span model="." view="Text" /></a>
                  </ul></body></html>"""

    def initialize(self, **kwargs):
        self.putChild('RPC2.0', UserStatusXR(self.model.service))

    def getDynamicChild(self, path, request):
        return UserStatus(user=path, service=self.model.service)

components.registerAdapter(UserStatusTree, IFingerService)

class UserStatus(page.Page):

    template='''<html><head><title view="Text" model="user"/></head>
    <body><h1 view="Text" model="user"/>
    <p mode="status" view="Text" />
    </body></html>'''

    def initialize(self, **kwargs):
        self.user = kwargs['user']
        self.service = kwargs['service']

    def wmfactory_user(self):
        return self.user

    def wmfactory_status(self):
        return self.service.getUser(self.user)

class UserStatusXR(xmlrpc.XMLPRC):

    def __init__(self, service):
        xmlrpc.XMLRPC.__init__(self)
        self.service = service

    def xmlrpc_getUser(self, user):
        return self.service.getUser(user)


class IPerspectiveFinger(components.Interface):

    def remote_getUser(self, username):
        """return a user's status"""

    def remote_getUsers(self):
        """return a user's status"""


class PerspectiveFingerFromService(pb.Root):

    __implements__ = IPerspectiveFinger,

    def __init__(self, service):
        self.service = service

    def remote_getUser(self, username):
        return self.service.getUser(username)

    def remote_getUsers(self):
        return self.service.getUsers()

components.registerAdapter(PerspectiveFingerFromService, IFingerService)


class FingerService(app.ApplicationService):

    __implements__ = IFingerService,

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


class ServerContextFactory:

    def getContext(self):
        """Create an SSL context.

        This is a sample implementation that loads a certificate from a file
        called 'server.pem'."""
        ctx = SSL.Context(SSL.SSLv23_METHOD)
        ctx.use_certificate_file('server.pem')
        ctx.use_privatekey_file('server.pem')
        return ctx


application = app.Application('finger', uid=1, gid=1)
f = FingerService('/etc/users', application, 'finger')
application.listenTCP(79, IFingerFactory(f))
site = server.Site(resource.IResource(f))
application.listenTCP(80, site)
application.listenSSL(443, site, ServerContextFactory())
i = IIRCClientFactory(f)
i.nickname = 'fingerbot'
application.connectTCP('irc.freenode.org', 6667, i)
application.listenTCP(8889, pb.BrokerFactory(IPerspectiveFinger(f)))
