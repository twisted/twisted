from __future__ import print_function

from twisted.python import util
from twisted.spread import pb
from twisted.cred import portal, checkers, credentials

class Avatar(pb.Avatar):
    def perspective_exception(self, x):
        return x / 0

class Realm:
    def requestAvatar(self, interface, mind, *interfaces):
        if pb.IPerspective in interfaces:
            return pb.IPerspective, Avatar(), lambda: None

def cbLogin(avatar):
    avatar.callRemote("exception", 10).addCallback(str).addCallback(util.println)

def ebLogin(failure):
    print(failure)

def main():
    c = checkers.InMemoryUsernamePasswordDatabaseDontUse(user="pass")
    p = portal.Portal(Realm(), [c])
    server = pb.PBServerFactory(p)
    server.unsafeTracebacks = True
    client = pb.PBClientFactory()
    login = client.login(credentials.UsernamePassword("user", "pass"))
    login.addCallback(cbLogin).addErrback(ebLogin).addBoth(lambda: reactor.stop())

    from twisted.internet import reactor
    p = reactor.listenTCP(0, server)
    c = reactor.connectTCP('127.0.0.1', p.getHost().port, client)
    reactor.run()

if __name__ == '__main__':
    main()
