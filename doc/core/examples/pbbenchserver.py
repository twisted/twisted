# Twisted, the Framework of Your Internet
# Copyright (C) 2001, 2002 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Server for PB benchmark."""

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
        print '(s) cps:', self.callsPerSec
        self.callsPerSec = 0
        reactor.callLater(1, self.printCallsPerSec)

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
    reactor.listenTCP(8787, pb.PBServerFactory(portal))
    reactor.run()

if __name__ == '__main__':
    main()
