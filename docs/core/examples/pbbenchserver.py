# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""Server for PB benchmark."""
from __future__ import print_function

from zope.interface import implementer

from twisted.spread import pb
from twisted.internet import reactor
from twisted.cred.portal import IRealm

class PBBenchPerspective(pb.Avatar):
    callsPerSec = 0
    def __init__(self):
        pass
    
    def perspective_simple(self):
        self.callsPerSec = self.callsPerSec + 1
        return None

    def printCallsPerSec(self):
        print('(s) cps:', self.callsPerSec)
        self.callsPerSec = 0
        reactor.callLater(1, self.printCallsPerSec)

    def perspective_complexTypes(self):
        return ['a', 1, 1, 1.0, [], ()]


@implementer(IRealm)
class SimpleRealm:
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
    reactor.listenTCP(8787, pb.PBServerFactory(portal))
    reactor.run()

if __name__ == '__main__':
    main()
