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
from twisted.internet import reactor, app
from twisted.cred import authorizer

class PBBenchPerspective(pb.Perspective):
    callsPerSec = 0
    def perspective_simple(self):
        self.callsPerSec = self.callsPerSec + 1
        return None

    def printCallsPerSec(self):
        print '(s) cps:', self.callsPerSec
        self.callsPerSec = 0
        reactor.callLater(1, self.printCallsPerSec)

    def perspective_complexTypes(self):
        return ['a', 1, 1l, 1.0, [], ()]

class PBBenchService(pb.Service):
    perspectiveClass = PBBenchPerspective

a = app.Application("pbbench")
auth = authorizer.DefaultAuthorizer(a)
a.listenTCP(8787, pb.BrokerFactory(pb.AuthRoot(auth)))
b = PBBenchService("benchmark", a, authorizer=auth)
u = b.createPerspective("benchmark")
u.makeIdentity("benchmark")
u.printCallsPerSec()
a.run()
