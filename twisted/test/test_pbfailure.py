
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

from twisted.trial import unittest


import traceback


from twisted.spread import pb
from twisted.internet import app, reactor
from twisted.python import log
from twisted.cred import authorizer


PORTNO = 54321

##
# test exceptions
##
class PoopError(Exception): pass
class FailError(Exception): pass
class DieError(Exception): pass
class TimeoutError(Exception): pass

####
# server-side
####
class SimplePerspective(pb.Perspective):
    def perspective_poop(self):
        raise PoopError("Someone threw poopie at me!")
    def perspective_fail(self):
        raise FailError("I'm a complete failure! :(")
    def perspective_die(self):
        raise DieError("*gack*")

class SimpleService(pb.Service):
    def __init__(self, name, auth, appl, tester):
        self.tester = tester
        pb.Service.__init__(self, name, authorizer=auth, serviceParent=appl)

    def startService(self):
        self.tester.runClient()

    def getPerspectiveNamed(self, name):
        p = SimplePerspective(name)
        p.setService(self)
        return p


class PBFailureTest(unittest.TestCase):
    def __init__(self):
        self.total = 0


    def testPBFailures(self):
        auth = authorizer.DefaultAuthorizer()
        appl = app.Application("pbfailure", authorizer=auth)
        SimpleService("pbfailure",auth,appl,self).getPerspectiveNamed("guest").makeIdentity("guest")
        appl.listenTCP(PORTNO, pb.BrokerFactory(pb.AuthRoot(auth)))
        appl.run(save=0)
        log.flushErrors(PoopError, FailError, DieError)


    def runClient(self):
        pb.connect("localhost", PORTNO, "guest", "guest",
                   "pbfailure", "guest", 30).addCallbacks(self.connected, self.notConnected)
        self.id = reactor.callLater(10, self.timeOut)


    def a(self, d):
        for m in (self.failurePoop, self.failureFail, self.failureDie, lambda: None):
            d.addCallbacks(self.success, m)



    def stopReactor(self):
        self.id.cancel()
        reactor.crash()

    ##
    # callbacks
    ##

    def connected(self, persp):
        self.a(persp.callRemote('poop'))
        self.a(persp.callRemote('fail'))
        self.a(persp.callRemote('die'))

    def notConnected(self, fail):
        self.stopReactor()
        raise pb.Error("There's probably something wrong with your environment"
                       "(is port 54321 free?), because I couldn't connect to myself.")


    def success(self, result):
        if result in [42, 420, 4200]:
            self.total = self.total + 1
        if self.total == 3:
            self.stopReactor()

    def failurePoop(self, fail):
        fail.trap(PoopError)
        return 42

    def failureFail(self, fail):
        fail.trap(FailError)
        return 420

    def failureDie(self, fail):
        fail.trap(DieError)
        return 4200

    def timeOut(self):
        reactor.crash()
        raise TimeoutError("Never got all three failures!")

testCases = [PBFailureTest]
