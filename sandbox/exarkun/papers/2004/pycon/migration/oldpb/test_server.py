
import sys
from twisted.python import log
log.startLogging(sys.stdout)

from twisted.spread import pb
from twisted.internet import reactor
from twisted.cred import portal
from twisted.cred import checkers

import pbold
import jelliers

def makeAFactory():
    from twisted.web import server, static
    pb.globalSecurity.allowInstancesOf(server.Site)
    return server.Site(static.File('.'))

class MigrationServer(pb.Avatar):
    def __init__(self, servers):
        self.servers = servers

    def perspective_getServerList(self):
        return self.servers.keys()

    def perspective_getServer(self, name):
        try:
            return self.servers.pop(name)
        finally:
            if not self.servers:
                from twisted.internet import reactor
                reactor.callLater(5, reactor.stop)

class MigrationRealm:
    __implements__ = (portal.IRealm,)

    def __init__(self, servers):
        self.servers = servers

    def requestAvatar(self, avatarID, mind, *interfaces):
        assert pb.IPerspective in interfaces
        return pb.IPerspective, MigrationServer(self.servers), lambda: None

def main():
    port = reactor.listenTCP(0, makeAFactory())

    r = MigrationRealm({'blah': port})
    p = portal.Portal(r)
    p.registerChecker(checkers.FilePasswordDB('passwd'))

    reactor.listenUNIX('migrate', pb.PBServerFactory(p, True))
    reactor.run()

if __name__ == '__main__':
    main()
