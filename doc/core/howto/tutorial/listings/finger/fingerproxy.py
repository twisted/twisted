# finger proxy
from twisted.application import internet, service
from twisted.internet import defer, protocol, reactor
from twisted.protocols import basic
from twisted.python import components
from zope.interface import Interface, implements


def catchError(err):
    return "Internal error in server"

class IFingerService(Interface):

    def getUser(user):
        """Return a deferred returning a string"""

    def getUsers():
        """Return a deferred returning a list of strings"""


class IFingerFactory(Interface):

    def getUser(user):
        """Return a deferred returning a string"""

    def buildProtocol(addr):
        """Return a protocol returning a string"""

class FingerProtocol(basic.LineReceiver):
            
    def lineReceived(self, user):
        d = self.factory.getUser(user)
        d.addErrback(catchError)
        def writeValue(value):
            self.transport.write(value)
            self.transport.loseConnection()
        d.addCallback(writeValue)



class FingerFactoryFromService(protocol.ClientFactory):
    
    implements(IFingerFactory)

    protocol = FingerProtocol
    
    def __init__(self, service):
        self.service = service
        
    def getUser(self, user):
        return self.service.getUser(user)


components.registerAdapter(FingerFactoryFromService,
                           IFingerService,
                           IFingerFactory)

class FingerClient(protocol.Protocol):
                                
    def connectionMade(self):
        self.transport.write(self.factory.user+"\r\n")
        self.buf = []                        

    def dataReceived(self, data):
        self.buf.append(data)

    def connectionLost(self, reason):
        self.factory.gotData(''.join(self.buf))

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
    reactor.connectTCP(host, port, f)                   
    return f.d


class ProxyFingerService(service.Service):
    implements(IFingerService)

    def getUser(self, user):
        try:
            user, host = user.split('@', 1)
        except:
            user = user.strip()
            host = '127.0.0.1'
        ret = finger(user, host)
        ret.addErrback(lambda _: "Could not connect to remote host")
        return ret

    def getUsers(self):
        return defer.succeed([])
                             
application = service.Application('finger', uid=1, gid=1) 
f = ProxyFingerService()
internet.TCPServer(7779, IFingerFactory(f)).setServiceParent(
    service.IServiceCollection(application))
