# finger.py module

from zope.interface import Interface, implementer

from twisted.application import internet, service, strports
from twisted.internet import protocol, reactor, defer, endpoints
from twisted.words.protocols import irc
from twisted.protocols import basic
from twisted.python import components, log
from twisted.web import resource, server, xmlrpc
from twisted.spread import pb

class IFingerService(Interface):

    def getUser(user):
        """
        Return a deferred returning a L{bytes}.
        """

    def getUsers():
        """
        Return a deferred returning a L{list} of L{bytes}.
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
            self.transport.write(value + b'\n')
            self.transport.loseConnection()
        d.addCallback(writeValue)


class IFingerFactory(Interface):

    def getUser(user):
        """
        Return a deferred returning L{bytes}.
        """

    def buildProtocol(addr):
        """
        Return a protocol returning L{bytes}.
        """


@implementer(IFingerFactory)
class FingerFactoryFromService(protocol.ServerFactory):

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
        Return a deferred returning L{bytes}.
        """

    def buildProtocol(addr):
        """
        Return a protocol returning L{bytes}.
        """


@implementer(IFingerSetterFactory)
class FingerSetterFactoryFromService(protocol.ServerFactory):

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


class IIRCClientFactory(Interface):

    """
    @ivar nickname
    """

    def getUser(user):
        """
        Return a deferred returning L{bytes}.
        """

    def buildProtocol(addr):
        """
        Return a protocol.
        """


@implementer(IIRCClientFactory)
class IRCClientFactoryFromService(protocol.ClientFactory):

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

    template = """<html><head><title>Users</title></head><body>
    <h1>Users</h1>
    <ul>
    %(users)s
    </ul>
    </body>
    </html>"""

    def __init__(self, service):
        resource.Resource.__init__(self)
        self.service = service

    def getChild(self, path, request):
        if path == '':
            return self
        elif path == 'RPC2':
            return UserStatusXR(self.service)
        else:
            return UserStatus(path, self.service)

    def render_GET(self, request):
        users = self.service.getUsers()
        def cbUsers(users):
            request.write(self.template % {'users': ''.join([
                    # Name should be quoted properly these uses.
                    '<li><a href="%s">%s</a></li>' % (name, name)
                    for name in users])})
            request.finish()
        users.addCallback(cbUsers)
        def ebUsers(err):
            log.err(err, "UserStatusTree failed")
            request.finish()
        users.addErrback(ebUsers)
        return server.NOT_DONE_YET

components.registerAdapter(UserStatusTree, IFingerService, resource.IResource)


class UserStatus(resource.Resource):

    template='''<html><head><title>%(title)s</title></head>
    <body><h1>%(name)s</h1><p>%(status)s</p></body></html>'''

    def __init__(self, user, service):
        resource.Resource.__init__(self)
        self.user = user
        self.service = service

    def render_GET(self, request):
        status = self.service.getUser(self.user)
        def cbStatus(status):
            request.write(self.template % {
                'title': self.user,
                'name': self.user,
                'status': status})
            request.finish()
        status.addCallback(cbStatus)
        def ebStatus(err):
            log.err(err, "UserStatus failed")
            request.finish()
        status.addErrback(ebStatus)
        return server.NOT_DONE_YET


class UserStatusXR(xmlrpc.XMLRPC):

    def __init__(self, service):
        xmlrpc.XMLRPC.__init__(self)
        self.service = service

    def xmlrpc_getUser(self, user):
        return self.service.getUser(user)

    def xmlrpc_getUsers(self):
        return self.service.getUsers()


class IPerspectiveFinger(Interface):

    def remote_getUser(username):
        """
        Return a user's status.
        """

    def remote_getUsers():
        """
        Return a user's status.
        """


@implementer(IPerspectiveFinger)
class PerspectiveFingerFromService(pb.Root):

    def __init__(self, service):
        self.service = service

    def remote_getUser(self, username):
        return self.service.getUser(username)

    def remote_getUsers(self):
        return self.service.getUsers()

components.registerAdapter(PerspectiveFingerFromService,
                           IFingerService,
                           IPerspectiveFinger)


@implementer(IFingerService)
class FingerService(service.Service):

    def __init__(self, filename):
        self.filename = filename

    def _read(self):
        self.users = {}
        with open(self.filename, "rb") as f:
            for line in f:
                user, status = line.split(b':', 1)
                user = user.strip()
                status = status.strip()
                self.users[user] = status
        self.call = reactor.callLater(30, self._read)

    def getUser(self, user):
        return defer.succeed(self.users.get(user, b"No such user"))

    def getUsers(self):
        return defer.succeed(self.users.keys())

    def startService(self):
        self._read()
        service.Service.startService(self)

    def stopService(self):
        service.Service.stopService(self)
        self.call.cancel()



# Easy configuration

def makeService(config):
    # finger on port 79
    s = service.MultiService()
    f = FingerService(config['file'])
    h = strports.service("tcp:1079", IFingerFactory(f))
    h.setServiceParent(s)


    # website on port 8000
    r = resource.IResource(f)
    r.templateDirectory = config['templates']
    site = server.Site(r)
    j = strports.service("tcp:8000", site)
    j.setServiceParent(s)

    # ssl on port 443
#    if config.get('ssl'):
#        k = strports.service(
#            "ssl:port=443:certKey=cert.pem:privateKey=key.pem", site
#        )
#        k.setServiceParent(s)

    # irc fingerbot
    if 'ircnick' in config:
        i = IIRCClientFactory(f)
        i.nickname = config['ircnick']
        ircserver = config['ircserver']
        b = internet.ClientService(
            endpoints.HostnameEndpoint(reactor, ircserver, 6667), i
        )
        b.setServiceParent(s)

    # Pespective Broker on port 8889
    if 'pbport' in config:
        m = internet.StreamServerEndpointService(
            endpoints.TCP4ServerEndpoint(reactor, int(config['pbport'])),
            pb.PBServerFactory(IPerspectiveFinger(f))
        )
        m.setServiceParent(s)

    return s
