
"""Tests for ReconnectingPBClientFactory.
"""

import sys, os, time

from twisted.trial import unittest
dR = unittest.deferredResult

# the new module
from pbutil import ReconnectingPBClientFactory

from twisted.spread import pb, util
from twisted.internet import protocol, main
from twisted.internet.app import Application
from twisted.python import failure, log
from twisted.cred import identity, authorizer
from twisted.internet import reactor, defer

class Dummy(pb.Viewable):
    def view_doNothing(self, user):
        if isinstance(user, DummyPerspective):
            return 'hello world!'
        else:
            return 'goodbye, cruel world!'

class DummyPerspective(pb.Perspective):
    def perspective_getDummyViewPoint(self):
        return Dummy()

class DummyService(pb.Service):
    """A dummy PB service to test with.
    """
    def getPerspectiveNamed(self, user):
        """
        """
        # Note: I don't need to go back and forth between identity and
        # perspective here, so I _never_ need to specify identityName.
        p = DummyPerspective(user)
        p.setService(self)
        return p

class Reconnecting(ReconnectingPBClientFactory):
    def __init__(self):
        ReconnectingPBClientFactory.__init__(self)
        self.root = []
        self.perspective = []

    def gotRootObject(self, root):
        self.root.append(root)
    def gotPerspective(self, perspective):
        self.perspective.append(perspective)

class ConnectionTestCase(unittest.TestCase):

    def setUp(self):
        c = pb.Broker()
        auth = authorizer.DefaultAuthorizer()
        appl = Application("pb-test")
        auth.setServiceCollection(appl)
        ident = identity.Identity("guest", authorizer=auth)
        ident.setPassword("guest")
        svc = DummyService("test", appl, authorizer=auth)
        ident.addKeyForPerspective(svc.getPerspectiveNamed("any"))
        auth.addIdentity(ident)
        ident2 = identity.Identity("foo", authorizer=auth)
        ident2.setPassword("foo")
        ident2.addKeyForPerspective(svc.getPerspectiveNamed("foo"))
        auth.addIdentity(ident2)
        self.svr = pb.BrokerFactory(pb.AuthRoot(auth))
        self.port = reactor.listenTCP(0, self.svr, interface="127.0.0.1")
        self.portno = self.port.getHost()[-1]

    def tearDown(self):
        self.port.stopListening()
        reactor.iterate(); reactor.iterate();

    def _checkRootObject(self, root):
        challenge = dR(root.callRemote("username", "guest"))
        self.assertEquals(len(challenge), 2)
        self.assert_(isinstance(challenge[1], pb.RemoteReference))

    def testReconnecting(self):
        f = Reconnecting()
        f.factor = 0.5 # speed up reconnection speed. But be careful about
                       # your Internet! (note that this is actually
                       # logarithmic backoff instead of exponential backoff,
                       # very bad)
        reactor.connectTCP("127.0.0.1", self.portno, f)

        limit = time.time() + 1
        while time.time() < limit:
            if len(f.root) != 0:
                break
            reactor.iterate(0.1)

        self.assertEqual(len(f.root), 1)
        r = f.root[-1]
        self._checkRootObject(r)
        r.broker.transport.loseConnection()

        # give it a chance to reconnect. The first attempt will be in 0.5s
        limit = time.time() + 1
        while time.time() < limit:
            if len(f.root) != 1:
                break
            reactor.iterate(0.1)
        self.assertEqual(len(f.root), 2)
        r = f.root[-1]
        self._checkRootObject(r)
        f.stopTrying()

        # now it should not reconnect
        r.broker.transport.loseConnection()
        limit = time.time() + 1
        while time.time() < limit:
            if len(f.root) != 2:
                break
            reactor.iterate(0.1)
        self.assertEqual(len(f.root), 2)

    # TODO: make sure a connectionFailed will trigger a reconnect too. I'm
    # not quite sure how to implement this.. maybe create the server, get the
    # port number, shut off the server, start the connection attempt, see it
    # fail, restart the server at the same port number, then watch the
    # connect succeed?
        

# yay new cred, everyone use this:

from twisted.cred import portal, checkers, credentials

class MyRealm:
    """A test realm."""

    def __init__(self):
        self.p = MyPerspective()
    
    def requestAvatar(self, avatarId, mind, interface):
        assert interface == pb.IPerspective
        assert mind == "BRAINS!"
        self.p.loggedIn = 1
        return pb.IPerspective, self.p, self.p.logout

class MyPerspective(pb.Perspective):

    __implements__ = pb.IPerspective,

    def __init__(self):
        pass
    
    def perspective_getViewPoint(self):
        return MyView()

    def logout(self):
        self.loggedOut = 1

class NewCredTestCase(unittest.TestCase):

    def setUp(self):
        self.realm = MyRealm()
        self.portal = portal.Portal(self.realm)
        self.checker = checkers.InMemoryUsernamePasswordDatabaseDontUse()
        self.checker.addUser("user", "pass")
        self.portal.registerChecker(self.checker)
        self.factory = pb.PBServerFactory(self.portal)
        self.port = reactor.listenTCP(0, self.factory, interface="127.0.0.1")
        self.portno = self.port.getHost()[-1]

    def tearDown(self):
        self.port.stopListening()
        reactor.iterate()
        reactor.iterate()

    def err(self, why):
        print "ERR"
        print why

    def testReconnecting(self):
        # check gotPerspective
        f = Reconnecting()
        f.factor = 0.5
        f.login(credentials.UsernamePassword("user", "pass"), "BRAINS!")
        reactor.connectTCP("127.0.0.1", self.portno, f)

        limit = time.time() + 1
        while time.time() < limit:
            if len(f.perspective) != 0:
                break
            reactor.iterate(0.1)

        self.assertEqual(len(f.perspective), 1)
        p = f.perspective[-1]
        self.assert_(isinstance(p, pb.RemoteReference))
        p.broker.transport.loseConnection()

        # give it a chance to reconnect. The first attempt will be in 0.5s
        limit = time.time() + 1
        while time.time() < limit:
            if len(f.perspective) != 1:
                break
            reactor.iterate(0.1)

        self.assertEqual(len(f.perspective), 2)
        p = f.perspective[-1]
        self.assert_(isinstance(p, pb.RemoteReference))
        f.stopTrying()

        # now it should not reconnect
        p.broker.transport.loseConnection()
        limit = time.time() + 1
        while time.time() < limit:
            if len(f.perspective) != 2:
                break
            reactor.iterate(0.1)

        self.assertEqual(len(f.perspective), 2)

    # TODO: verify that bad credentials call the error function
