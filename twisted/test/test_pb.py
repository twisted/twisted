
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

"""Tests for ProtoBroker module.
"""

import sys

from cStringIO import StringIO

from pyunit import unittest

from twisted.spread import pb
from twisted.protocols import protocol
from twisted.internet import passport, main
from twisted.python import defer

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
        p = DummyPerspective("any")
        p.setService(self)
        return p

class IOPump:
    """Utility to pump data between clients and servers for protocol testing.

    Perhaps this is a utility worthy of being in protocol.py?
    """
    def __init__(self, client, server, clientIO, serverIO):
        self.client = client
        self.server = server
        self.clientIO = clientIO
        self.serverIO = serverIO

    def pump(self):
        """Move data back and forth.

        Returns whether any data was moved.
        """
        self.clientIO.seek(0)
        self.serverIO.seek(0)
        cData = self.clientIO.read()
        sData = self.serverIO.read()
        self.clientIO.seek(0)
        self.serverIO.seek(0)
        self.clientIO.truncate()
        self.serverIO.truncate()
        for byte in cData:
            self.server.dataReceived(byte)
        for byte in sData:
            self.client.dataReceived(byte)
        if cData or sData:
            return 1
        else:
            return 0


def connectedServerAndClient():
    """Returns a 3-tuple: (client, server, pump)
    """
    c = pb.Broker()
    app = main.Application("pb-test")
    ident = passport.Identity("guest", app)
    ident.setPassword("guest")
    svc = DummyService("test", app)
    ident.addKeyForPerspective(svc.getPerspectiveNamed("any"))
    app.authorizer.addIdentity(ident)
    svr = pb.BrokerFactory(pb.AuthRoot(app))
    s = svr.buildProtocol(('127.0.0.1',))
    s.copyTags = {}

    cio = StringIO()
    sio = StringIO()
    c.makeConnection(protocol.FileWrapper(cio))
    s.makeConnection(protocol.FileWrapper(sio))
    pump = IOPump(c, s, cio, sio)
    # Challenge-response authentication:
    while pump.pump():
        pass
    return c, s, pump

class SimpleRemote(pb.Referenceable):
    def remote_thunk(self, arg):
        self.arg = arg
        return arg + 1

    def remote_knuth(self, arg):
        raise Exception()

class NestedRemote(pb.Referenceable):
    def remote_getSimple(self):
        return SimpleRemote()

class SimpleCopy(pb.Copyable):
    def __init__(self):
        self.x = 1
        self.y = {"Hello":"World"}
        self.z = ['test']

class SimpleLocalCopy(pb.RemoteCopy):
    def check(self):
        # checks based on above '__init__'
        assert self.x == 1
        assert self.y['Hello'] == 'World'
        assert self.z[0] == 'test'
        return 1

pb.setCopierForClass(str(SimpleCopy), SimpleLocalCopy)


class NestedCopy(pb.Referenceable):
    def remote_getCopy(self):
        return SimpleCopy()

class SimpleCache(pb.Cacheable):
    def __init___(self):
        self.x = 1
        self.y = {"Hello":"World"}
        self.z = ['test']

class NestedComplicatedCache(pb.Referenceable):
    def __init__(self):
        self.c = VeryVeryComplicatedCacheable()

    def remote_getCache(self):
        return self.c


class VeryVeryComplicatedCacheable(pb.Cacheable):
    def __init__(self):
        self.x = 1
        self.y = 2
        self.foo = 3

    def setFoo4(self):
        self.foo = 4
        self.observer.foo(4)

    def getStateToCacheAndObserveFor(self, perspective, observer):
        self.observer = observer
        return {"x": self.x,
                "y": self.y,
                "foo": self.foo}

class RatherBaroqueCache(pb.RemoteCache):
    def observe_foo(self, newFoo):
        self.foo = newFoo

    def checkFoo4(self):
        return (self.foo == 4)

    def check(self):
        # checks based on above '__init__'
        assert self.x == 1
        assert self.y == 2
        assert self.foo == 3
        return 1

pb.setCopierForClass(str(VeryVeryComplicatedCacheable), RatherBaroqueCache)

class SimpleLocalCache(pb.RemoteCache):
    def setCopyableState(self, state):
        self.__dict__.update(state)

    def checkMethod(self):
        return self.check

    def checkSelf(self):
        return self

    def check(self):
        # checks based on above '__init__'
        assert self.x == 1
        assert self.y['Hello'] == 'World'
        assert self.z[0] == 'test'
        return 1

pb.setCopierForClass(str(SimpleCache), SimpleLocalCache)

class NestedCache(pb.Referenceable):
    def __init__(self):
        self.x = SimpleCache()

    def remote_getCache(self):
        return [self.x,self.x]

    def remote_putCache(self, cache):
        return (self.x is cache)


class Observable(pb.Referenceable):
    def __init__(self):
        self.observers = []

    def remote_observe(self, obs):
        self.observers.append(obs)

    def remote_unobserve(self, obs):
        self.observers.remove(obs)

    def notify(self, obj):
        for observer in self.observers:
            observer.notify(self, obj)

class DeferredRemote(pb.Referenceable):
    def __init__(self):
        self.run = 0

    def runMe(self, arg):
        self.run = arg
        return arg + 1

    def dontRunMe(self, arg):
        print arg
        assert 0, "shouldn't have been run!"

    def remote_doItLater(self):
        d = defer.Deferred()
        d.addCallbacks(self.runMe, self.dontRunMe)
        self.d = d
        return d


class Observer(pb.Referenceable):
    notified = 0
    obj = None
    def remote_notify(self, other, obj):
        self.obj = obj
        self.notified = self.notified + 1
        other.unobserve(self)


class BrokerTestCase(unittest.TestCase):
    thunkResult = None

    def thunkErrorBad(self, error):
        assert 0, "This should cause a return value, not %s" % error

    def thunkResultGood(self, result):
        self.thunkResult = result

    def thunkErrorGood(self, tb):
        pass

    def thunkResultBad(self, result):
        assert 0, "This should cause an error, not %s" % result

    def testReference(self):
        c, s, pump = connectedServerAndClient()

        class X(pb.Referenceable):
            def remote_catch(self,arg):
                self.caught = arg

        class Y(pb.Referenceable):
            def remote_throw(self, a, b):
                a.catch(b)

        s.setNameForLocal("y", Y())
        y = c.remoteForName("y")
        x = X()
        z = X()
        y.throw(x, z)
        pump.pump()
        pump.pump()
        pump.pump()
        assert x.caught is z, "X should have caught Z"

        # make sure references to remote methods are equals
        self.assertEquals(y.throw, y.throw)

    def testResult(self):
        c, s, pump = connectedServerAndClient()
        for x, y in (c, s), (s, c):
            # test reflexivity
            foo = SimpleRemote()
            x.setNameForLocal("foo", foo)
            bar = y.remoteForName("foo")
            self.expectedThunkResult = 8
            bar.thunk(self.expectedThunkResult - 1).addCallbacks(self.thunkResultGood, self.thunkErrorBad)
            # Send question.
            pump.pump()
            # Send response.
            pump.pump()
            # Shouldn't require any more pumping than that...
            assert self.thunkResult == self.expectedThunkResult,\
                   "result wasn't received."

    def refcountResult(self, result):
        self.nestedRemote = result

    def testCopy(self):
        c, s, pump = connectedServerAndClient()
        foo = NestedCopy()
        s.setNameForLocal("foo", foo)
        x = c.remoteForName("foo")
        x.getCopy().addCallbacks(self.thunkResultGood, self.thunkErrorBad)
        pump.pump()
        pump.pump()
        assert self.thunkResult.check() == 1, "check failed"

    def testObserve(self):
        c, s, pump = connectedServerAndClient()

        # this is really testing the comparison between remote objects, to make
        # sure that you can *UN*observe when you have an observer architecture.
        a = Observable()
        b = Observer()
        s.setNameForLocal("a", a)
        ra = c.remoteForName("a")
        ra.observe(b)
        pump.pump()
        a.notify(1)
        pump.pump()
        pump.pump()
        a.notify(10)
        pump.pump()
        pump.pump()
        assert b.obj is not None, "didn't notify"
        assert b.obj == 1, 'notified too much'


    def testDefer(self):
        c, s, pump = connectedServerAndClient()
        d = DeferredRemote()
        s.setNameForLocal("d", d)
        e = c.remoteForName("d")
        pump.pump(); pump.pump()
        results = []
        e.doItLater().addCallback(results.append)
        pump.pump(); pump.pump()
        assert not d.run, "Deferred method run too early."
        d.d.callback(5)
        assert d.run == 5, "Deferred method run too late."
        pump.pump(); pump.pump()
        assert results[0] == 6, "Incorrect result."
        
    def testRefcount(self):
        c, s, pump = connectedServerAndClient()
        foo = NestedRemote()
        s.setNameForLocal("foo", foo)
        bar = c.remoteForName("foo")
        bar.getSimple().addCallbacks(self.refcountResult, self.thunkErrorBad)

        # send question
        pump.pump()
        # send response
        pump.pump()

        # delving into internal structures here, because GC is sort of
        # inherently internal.
        rluid = self.nestedRemote.luid
        assert s.localObjects.has_key(rluid), "Should have key."
        del self.nestedRemote
        # nudge the gc
        if sys.hexversion >= 0x2000000:
            import gc
            gc.collect()
        # try to nudge the GC even if we can't really
        pump.pump()
        pump.pump()
        pump.pump()
        assert not s.localObjects.has_key(rluid), "Should NOT have key."

    def testCache(self):
        c, s, pump = connectedServerAndClient()
        obj = NestedCache()
        obj2 = NestedComplicatedCache()
        vcc = obj2.c
        s.setNameForLocal("obj", obj)
        s.setNameForLocal("xxx", obj2)
        o2 = c.remoteForName("obj")
        o3 = c.remoteForName("xxx")
        coll = []
        o2.getCache().addCallback(coll.append)
        o2.getCache().addCallback(coll.append)
        complex = []
        o3.getCache().addCallback(complex.append)
        pump.pump() # ask for first cache
        pump.pump() # respond with it
        pump.pump() # ask for second cache
        pump.pump() # respond with it
        pump.pump() # just for good luck
        pump.pump()
        # `worst things first'
        assert complex[0].check()
        vcc.setFoo4()
        pump.pump(); pump.pump(); pump.pump()
        assert complex[0].checkFoo4(), "method was not called."
        assert len(coll) == 2
        cp = coll[0][0]
        assert cp.checkMethod().im_self is cp, "potential refcounting issue"
        assert cp.checkSelf() is cp, "other potential refcounting issue"
        # No longer need to do this...
        # assert cp.__class__ is pb.RemoteCacheProxy, "class was %s" % str(cp.__class__)
        # assert cp._RemoteCacheProxy__instance is coll[1][0]._RemoteCacheProxy__instance
        col2 = []
        o2.putCache(cp).addCallback(col2.append)
        # now, refcounting (similiar to testRefCount)
        luid = cp.luid
        assert s.remotelyCachedObjects.has_key(luid), "remote cache doesn't have it"
        del coll
        del cp
        # nudge the gc
        if sys.hexversion >= 0x2000000:
            import gc
            gc.collect()
        # try to nudge the GC even if we can't really
        pump.pump()
        pump.pump()
        pump.pump()
        pump.pump()
        pump.pump()
        # The GC is done with it.
        assert not s.remotelyCachedObjects.has_key(luid), "Server still had it after GC"
        assert not c.locallyCachedObjects.has_key(luid), "Client still had it after GC"
        # The objects were the same (testing lcache identity)
        assert col2[0]
        # test equality of references to methods
        self.assertEquals(o2.getCache, o2.getCache)

    def whatTheHell(self, obj):
        print '!?!?!?!?', repr(obj)

    def testViewPoint(self):
        c, s, pump = connectedServerAndClient()
        pump.pump()
        authRef = c.remoteForName("root")
        accum = []
        pb.logIn(authRef, None, "test", "guest", "guest", "any").addCallbacks(accum.append, self.whatTheHell)
        # ident = c.remoteForName("identity")
        # ident.attach("test", "any", None).addCallback(accum.append)
        pump.pump() # send call
        pump.pump() # get response
        while pump.pump(): # uh, do it more
            pass
        test = accum.pop() # okay, this should be our perspective...
        test.getDummyViewPoint().addCallback(accum.append)
        pump.pump() # send call
        pump.pump() # get response
        accum.pop().doNothing().addCallback(accum.append)
        pump.pump()
        pump.pump()
        assert accum.pop() == 'hello world!', 'oops...'

testCases = [BrokerTestCase]
