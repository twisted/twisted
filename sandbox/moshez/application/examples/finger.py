from twisted.internet import protocol, defer, ssl
from twisted.application import service, internet
from twisted.protocols import basic, irc
from twisted.python import components
from twisted.web import resource, server, static, xmlrpc
from twisted.web.woven import page, model, interfaces
from twisted.spread import pb

class IFingerService(components.Interface):

    def getUser(self, user):
        '''Return a deferred returning a string'''

    def getUsers(self):
        '''Return a deferred returning a list of strings'''

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

components.registerAdapter(FingerFactoryFromService, IFingerService,
                           IFingerFactory)


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
        if self.nickname.lower() == channel.lower() and '!' in user:
            user = user.split('!')[0]
            print "got", msg, "from", user
            d = self.factory.getUser(msg)
            d.addErrback(catchError)
            d.addCallback(lambda m: m.strip())
            d.addCallback(lambda m: "Status of %s: %s" % (msg, m))
            d.addCallback(lambda m: self.msg(user, m))


class IIRCClientFactory(components.Interface):

    '''
    @ivar nickname
    '''

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

components.registerAdapter(IRCClientFactoryFromService, IFingerService,
                           IIRCClientFactory)


class UsersModel(model.MethodModel):

    def __init__(self, service):
        model.MethodModel.__init__(self)
        self.service = service

    def wmfactory_users(self, request):
        print "getting users"
        return self.service.getUsers()

components.registerAdapter(UsersModel, IFingerService, interfaces.IModel)

class UserStatusTree(page.Page):

    template = """<html><head><title>Users</title></head><body>
                  <h1>Users</h1>
                  <ul model="users" view="List">
                  <li pattern="listItem"><span view="Text" /></li>
                  </ul></body></html>"""

    def wchild_RPC2(self, request):
        return UserStatusXR(self.model.service)

    def getDynamicChild(self, path, request):
        return UserStatus(user=path, service=self.model.service)

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

components.registerAdapter(PerspectiveFingerFromService, IFingerService,
                           IPerspectiveFinger)


class FingerService(internet.TimerService):

    __implements__ = internet.TimerService.__implements__, IFingerService,

    def __init__(self, file):
        self.file = file
        internet.TimerService.__init__(self, 1, self._read)

    def _read(self):
        self.users = {}
        for line in file(self.file):
            user, status = line.split(':', 1)
            self.users[user] = status

    def getUser(self, user):
        return defer.succeed(self.users.get(user, "No such user"))

    def getUsers(self):
        print self.users.keys()
        return defer.succeed(self.users.keys())


def makeService(file):
    m = service.MultiService()
    f = FingerService(file)
    f.setName('finger')
    f.setServiceParent(m)
    return m
