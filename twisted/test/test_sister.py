# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
# 
from pyunit import unittest

from twisted.sister.sisterserv import SisterService, TicketAuthorizer
from twisted.sister.parentserv import ParentService
from twisted.cred.util import challenge
from twisted.internet.app import Application
from twisted.spread.pb import AuthRoot, BrokerFactory, Perspective, connect, Service

parent_port = 87871
sister_port = parent_port
shared_port = parent_port

shared_secret = challenge()

def pauseTheReactor(ignore):
    from twisted.internet import reactor
    reactor.crash()
    return ignore
    
stopTheReactor = pauseTheReactor
class MeterMaid(Perspective):
    def __init__(self, name):
        Perspective.__init__(self,name)
        self.setService(Service("bleh"))
        
    def perspective_whatsMyName(self):
        return self.perspectiveName

class TwistedSisterTestCase(unittest.TestCase):
    def setUp(self):
        self.auth = TicketAuthorizer()
        self.app = Application("sistertest", authorizer=self.auth)
        self.ss = SisterService(
            "localhost", parent_port, "twisted.sister.parent",
            sister_port, shared_secret, "localhost", "twisted.sister", self.app)
        self.ps = ParentService(shared_secret, "twisted.sister.parent", self.app)
        self.bf = BrokerFactory(AuthRoot(self.app))
        self.app.listenTCP(shared_port, self.bf)

    def tearDown(self):
        from twisted.internet import reactor
        from twisted.internet import main
        self.app._beforeShutDown()
        self.app.unlistenTCP(shared_port)
        reactor.iterate()
        # reactor.stop()
        main.running = 0
        
    def testDummyResource(self):
        from twisted.internet import reactor
        self.ss.registerResourceLoader("int", int)
        self.ps.loadRemoteResource("int", "17", 0).addBoth(stopTheReactor).setTimeout(5)
        self.app.bindPorts()
        reactor.run()
        self.assertEquals(self.ss.ownedResources[("int", "17")], 17)

    def testTicketRetrieval(self):
        from twisted.internet import reactor
        self.ss.registerResourceLoader("meter", MeterMaid)
        l = []
        self.ps.loadRemoteResource("meter", "fred", 1).addCallback(l.append).addBoth(pauseTheReactor)
        from twisted.internet import main
        main.running = 0
        self.app.bindPorts()
        reactor.run()
        ticket = l.pop()
        connect("localhost", sister_port, "fred", ticket[0], "twisted.sister-ticket").addCallback(
            lambda result,l=l: result.callRemote("whatsMyName").addBoth(l.append).addBoth(stopTheReactor)
            ).addErrback(stopTheReactor).setTimeout(1)
        reactor.run()
        fred = l.pop()
        self.assertEquals(fred, 'fred')
