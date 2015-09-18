# Do everything properly, and componentize
from twisted.application import internet, service
from twisted.internet import protocol, reactor, defer, utils
from twisted.words.protocols import irc
from twisted.protocols import basic
from twisted.python import components
from twisted.web import resource, server, static, xmlrpc
from zope.interface import Interface, implements
import cgi
import pwd
import os

class IFingerService(Interface):

    def getUser(user):
        """
        Return a deferred returning a string.
        """

    def getUsers():
        """
        Return a deferred returning a list of strings.
        """


class IFingerSetterService(Interface):

    def setUser(user, status):
        """
        Set the user's status to something.
        """


class IFingerSetterService(Interface):

    def setUser(user, status):
        """
        Set the user's status to something.
        """


def catchError(err):
    return "Internal error in server"


class FingerProtocol(basic.LineReceiver):

    def lineReceived(self, user):
        d = self.factory.getUser(user)
        d.addErrback(catchError)
        def writeValue(value):
            self.transport.write(value+'\r\n')
            self.transport.loseConnection()
        d.addCallback(writeValue)


class IFingerFactory(Interface):

    def getUser(user):
        """
        Return a deferred returning a string.
        """

    def buildProtocol(addr):
        """
        Return a protocol returning a string.
        """


class FingerFactoryFromService(protocol.ServerFactory):

    implements(IFingerFactory)

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


class IFingerSetterFactory(Interface):

    def setUser(user, status):
        """
        Return a deferred returning a string.
        """

    def buildProtocol(addr):
        """
        Return a protocol returning a string.
        """


class FingerSetterFactoryFromService(protocol.ServerFactory):

    implements(IFingerSetterFactory)

    protocol = FingerSetterProtocol

    def __init__(self, service):
        self.service = service

    def setUser(self, user, status):
        self.service.setUser(user, status)


components.registerAdapter(FingerSetterFactoryFromService,
                           IFingerSetterService,
                           IFingerSetterFactory)


class IRCReplyBot(irc.IRCClient):

    def connectionMade():
        self.nickname = self.factory.nickname
        irc.IRCClient.connectionMade(self)

    def privmsg(self, user, channel, msg):
        user = user.split('!')[0]
        if self.nickname.lower() == channel.lower():
            d = self.factory.getUser(msg)
            d.addErrback(catchError)
            d.addCallback(lambda m: "Status of %s: %s" % (msg, m))
            d.addCallback(lambda m: self.msg(user, m))


class IIRCClientFactory(Interface):

    """
    @ivar nickname
    """

    def getUser(user):
        """
        Return a deferred returning a string.
        """

    def buildProtocol(addr):
        """
        Return a protocol.
        """


class IRCClientFactoryFromService(protocol.ClientFactory):

    implements(IIRCClientFactory)

    protocol = IRCReplyBot
    nickname = None

    def __init__(self, service):
        self.service = service

    def getUser(self, user):
        return self.service.getUser(user)

components.registerAdapter(IRCClientFactoryFromService,
                           IFingerService,
                           IIRCClientFactory)


class UserStatusTree(resource.Resource):

    implements(resource.IResource)

    def __init__(self, service):
        resource.Resource.__init__(self)
        self.service = service
        self.putChild('RPC2', UserStatusXR(self.service))

    def render_GET(self, request):
        d = self.service.getUsers()
        def formatUsers(users):
            l = ['<li><a href="%s">%s</a></li>' % (user, user)
                 for user in users]
            return '<ul>'+''.join(l)+'</ul>'
        d.addCallback(formatUsers)
        d.addCallback(request.write)
        d.addCallback(lambda _: request.finish())
        return server.NOT_DONE_YET

    def getChild(self, path, request):
        if path=="":
            return UserStatusTree(self.service)
        else:
            return UserStatus(path, self.service)

components.registerAdapter(UserStatusTree, IFingerService,
                           resource.IResource)


class UserStatus(resource.Resource):

    def __init__(self, user, service):
        resource.Resource.__init__(self)
        self.user = user
        self.service = service

    def render_GET(self, request):
        d = self.service.getUser(self.user)
        d.addCallback(cgi.escape)
        d.addCallback(lambda m:
                      '<h1>%s</h1>'%self.user+'<p>%s</p>'%m)
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

    implements(IFingerService)

    def __init__(self, filename):
        self.filename = filename
        self.users = {}

    def _read(self):
        self.users.clear()
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

    def startService(self):
        self._read()
        service.Service.startService(self)

    def stopService(self):
        service.Service.stopService(self)
        self.call.cancel()


# Yet another back-end

class LocalFingerService(service.Service):

    implements(IFingerService)

    def getUser(self, user):
        user = user.strip()
        try:
            entry = pwd.getpwnam(user)
        except KeyError:
            return defer.succeed("No such user")
        try:
            f = file(os.path.join(entry[5],'.plan'))
        except (IOError, OSError):
            return defer.succeed("No such user")
        data = f.read()
        data = data.strip()
        f.close()
        return defer.succeed(data)
    
    def getUsers(self):
        return defer.succeed([])


application = service.Application('finger', uid=1, gid=1)
f = LocalFingerService()
serviceCollection = service.IServiceCollection(application)
internet.TCPServer(79, IFingerFactory(f)
                   ).setServiceParent(serviceCollection)
internet.TCPServer(8000, server.Site(resource.IResource(f))
                   ).setServiceParent(serviceCollection)
i = IIRCClientFactory(f)
i.nickname = 'fingerbot'
internet.TCPClient('irc.freenode.org', 6667, i
                   ).setServiceParent(serviceCollection)
