from twisted.spread import pb
from twisted.cred.portal import IRealm
from twisted.internet import reactor
from twisted.application import service, internet

class PBBenchPerspective(pb.Avatar):
    callsPerSec = 0
    def __init__(self):
        pass
    
    def perspective_simple(self):
        self.callsPerSec = self.callsPerSec + 1
        return None

    def printCallsPerSec(self):
        print '(s) cps:', self.callsPerSec
        self.callsPerSec = 0
#        reactor.callLater(1, self.printCallsPerSec)

    def perspective_complexTypes(self):
        return ['a', 1, 1l, 1.0, [], ()]


class SimpleRealm:
    __implements__ = IRealm

    def requestAvatar(self, avatarId, mind, *interfaces):
        if pb.IPerspective in interfaces:
            p = PBBenchPerspective()
            p.printCallsPerSec()
            return pb.IPerspective, p, lambda : None
        else:
            raise NotImplementedError("no interface")


def main():
    from twisted.cred.portal import Portal
    from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
    portal = Portal(SimpleRealm())
    checker = InMemoryUsernamePasswordDatabaseDontUse()
    checker.addUser("benchmark", "benchmark")
    portal.registerChecker(checker)
    app = service.Application("pbs")
    s = internet.TCPServer(8787, pb.PBServerFactory(portal))
    s.setServiceParent(service.IServiceCollection(app))
    return app

application = main()

