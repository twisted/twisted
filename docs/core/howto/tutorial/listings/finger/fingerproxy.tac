# finger proxy
from zope.interface import Interface, implementer

from twisted.application import internet, service, strports
from twisted.internet import defer, endpoints, protocol, reactor
from twisted.protocols import basic
from twisted.python import components


def catchError(err):
    return "Internal error in server"


class IFingerService(Interface):
    def getUser(user):
        """Return a deferred returning L{bytes}"""

    def getUsers():
        """Return a deferred returning a L{list} of L{bytes}"""


class IFingerFactory(Interface):
    def getUser(user):
        """Return a deferred returning L{bytes}"""

    def buildProtocol(addr):
        """Return a protocol returning L{bytes}"""


class FingerProtocol(basic.LineReceiver):
    def lineReceived(self, user):
        d = self.factory.getUser(user)
        d.addErrback(catchError)

        def writeValue(value):
            self.transport.write(value)
            self.transport.loseConnection()

        d.addCallback(writeValue)


@implementer(IFingerFactory)
class FingerFactoryFromService(protocol.ClientFactory):

    protocol = FingerProtocol

    def __init__(self, service):
        self.service = service

    def getUser(self, user):
        return self.service.getUser(user)


components.registerAdapter(FingerFactoryFromService, IFingerService, IFingerFactory)


class FingerClient(protocol.Protocol):
    def connectionMade(self):
        self.transport.write(self.factory.user + b"\r\n")
        self.buf = []

    def dataReceived(self, data):
        self.buf.append(data)

    def connectionLost(self, reason):
        self.factory.gotData("".join(self.buf))


class FingerClientFactory(protocol.ClientFactory):

    protocol = FingerClient

    def __init__(self, user):
        self.user = user
        self.d = defer.Deferred()

    def clientConnectionFailed(self, _, reason):
        self.d.errback(reason)

    def gotData(self, data):
        self.d.callback(data)


def finger(user, host, port=79):
    f = FingerClientFactory(user)
    endpoint = endpoints.TCP4ClientEndpoint(reactor, host, port)
    endpoint.connect(f)
    return f.d


@implementer(IFingerService)
class ProxyFingerService(service.Service):
    def getUser(self, user):
        try:
            user, host = user.split("@", 1)
        except BaseException:
            user = user.strip()
            host = "127.0.0.1"
        ret = finger(user, host)
        ret.addErrback(lambda _: "Could not connect to remote host")
        return ret

    def getUsers(self):
        return defer.succeed([])


application = service.Application("finger", uid=1, gid=1)
f = ProxyFingerService()
strports.service("tcp:7779", IFingerFactory(f)).setServiceParent(
    service.IServiceCollection(application)
)
