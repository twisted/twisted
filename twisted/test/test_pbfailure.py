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

from twisted.spread import pb
from twisted.internet import reactor, defer
from twisted.python import log, failure

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
class SimpleRoot(pb.Root):
    def remote_poop(self):
        return defer.fail(failure.Failure(PoopError("Someone threw poopie at me!")))
    def remote_fail(self):
        raise FailError("I'm a complete failure! :(")
    def remote_die(self):
        raise DieError("*gack*")


class PBFailureTest(unittest.TestCase):

    compare = unittest.TestCase.assertEquals
    unsafeTracebacks = 0
    
    def setUp(self):
        self.results = [42000, 4200, 420, 42]
        
    def testPBFailures(self):
        factory = pb.PBServerFactory(SimpleRoot())
        factory.unsafeTracebacks = self.unsafeTracebacks
        p = reactor.listenTCP(0, factory, interface="127.0.0.1")
        self.port = p.getHost()[2]
        self.runClient()
        reactor.run()
        p.stopListening()
        log.flushErrors(PoopError, FailError, DieError, AttributeError)

    def runClient(self):
        f = pb.PBClientFactory()
        reactor.connectTCP("127.0.0.1", self.port, f)
        f.getRootObject().addCallbacks(self.connected, self.notConnected)
        self.id = reactor.callLater(10, self.timeOut)

    def a(self, d):
        for m in (self.failurePoop, self.failureFail, self.failureDie, self.failureNoSuch, lambda x: x):
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
        self.a(persp.callRemote("nosuch"))

    def notConnected(self, fail):
        self.stopReactor()
        raise pb.Error("There's probably something wrong with your environment"
                       ", because I couldn't connect to myself.")

    def success(self, result):
        if result == self.results[-1]:
            self.results.pop()
        if not self.results:
            self.stopReactor()

    def failurePoop(self, fail):
        fail.trap(PoopError)
        self.compare(fail.traceback, "Traceback unavailable\n")
        return 42

    def failureFail(self, fail):
        fail.trap(FailError)
        self.compare(fail.traceback, "Traceback unavailable\n")
        return 420

    def failureDie(self, fail):
        fail.trap(DieError)
        self.compare(fail.traceback, "Traceback unavailable\n")
        return 4200

    def failureNoSuch(self, fail):
        # XXX maybe PB shouldn't send AttributeErrors? and make generic exception
        # for no such method?
        fail.trap(AttributeError)
        self.compare(fail.traceback, "Traceback unavailable\n")
        return 42000
        
    def timeOut(self):
        reactor.crash()
        raise TimeoutError("Never got all three failures!")


class PBFailureTestUnsafe(PBFailureTest):

    compare = unittest.TestCase.failIfEquals
    unsafeTracebacks = 1
