
from gluhgluh import PBServerFactory, PBClientFactory, IPBRoot, schema

from twisted.cred import portal
from twisted.cred import credentials
from twisted.python import log

from twisted.application import internet
from twisted.application import service

class HuhWhat(object):
    def getMethodSchema(self, methodname):
        print 'methodSchema'
        return schema.MethodArgumentsConstraint()

    def remote_login(self):
        print 'login'

class Realm:
    __implements__ = (portal.IRealm, IPBRoot)

    def rootObject(self, broker):
        return HuhWhat()

def main():
    r = Realm()
    p = portal.Portal(r)

    s = PBServerFactory(r)
    c = PBClientFactory()

    d = c.login(credentials.UsernamePassword("user", "pass"))
    d.addCallback(str)
    d.addCallback(log.msg)

    a = service.Application("new pb test junk")
    internet.TCPServer(6767, s).setServiceParent(a)
    internet.TCPClient('127.0.0.1', 6767, c).setServiceParent(a)
    return a

application = main()
