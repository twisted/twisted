"""Tests for ProtoBroker module.
"""

import sys

from cStringIO import StringIO

from pyunit import unittest

from twisted.spread import pb
from twisted.python import authenticator
from twisted.protocols import protocol
from twisted.internet import passport, main

class Dummy(pb.Proxied):
    def proxy_doNothing(self, user):
        if isinstance(user, DummyPerspective):
            return 'hello world!'
        else:
            return 'goodbye, cruel world!'

class DummyPerspective(pb.Perspective):
    def perspective_getDummyProxy(self):
        return Dummy()

class DummyService(pb.Service):
    """A dummy PB service to test with.
    """
    def getPerspectiveNamed(self, user):
        """
        """
        # Note: I don't need to go back and forth between identity and
        # perspective here, so I _never_ need to specify identityName.
        return DummyPerspective("any", self)

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
    ident.addKeyFor(svc.getPerspectiveNamed("any"))
    app.authorizer.addIdentity(ident)
    svr = pb.BrokerFactory(app)
    s = svr.buildProtocol(('127.0.0.1',))
    c.requestIdentity("guest", "guest")
    s.copyTags = {}
    
    cio = StringIO()
    sio = StringIO()
    c.makeConnection(protocol.FileWrapper(cio))
    s.makeConnection(protocol.FileWrapper(sio), authenticator.Authenticator())
    pump = IOPump(c, s, cio, sio)
    # Challenge-response authentication:
    while pump.pump():
        pass
    return c, s, pump
    
class SimpleRemote(pb.Referenced):
    def remote_thunk(self, arg):
        self.arg = arg
        return arg + 1

    def remote_knuth(self, arg):
        raise Exception()

class NestedRemote(pb.Referenced):
    def remote_getSimple(self):
        return SimpleRemote()

class SimpleCopy(pb.Copied):
    def __init__(self):
        self.x = 1
        self.y = {"Hello":"World"}
        self.z = ['test']

class SimpleLocalCopy:
    def setCopiedState(self, state):
        self.__dict__.update(state)

    def check(self):
        # checks based on above '__init__'
        assert self.x == 1
        assert self.y['Hello'] == 'World'
        assert self.z[0] == 'test'
        return 1

pb.setCopierForClass(str(SimpleCopy), SimpleLocalCopy)
    

class NestedCopy(pb.Referenced):
    def remote_getCopy(self):
        return SimpleCopy()

class SimpleCache(pb.Cached):
    def __init___(self):
        self.x = 1
        self.y = {"Hello":"World"}
        self.z = ['test']

class NestedComplicatedCache(pb.Referenced):
    def __init__(self):
        self.c = VeryVeryComplicatedCached()

    def remote_getCache(self):
        return self.c
    

class VeryVeryComplicatedCached(pb.Cached):
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

class RatherBaroqueCache(pb.Cache):
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

pb.setCopierForClass(str(VeryVeryComplicatedCached), RatherBaroqueCache)

class SimpleLocalCache:
    def setCopiedState(self, state):
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

class NestedCache(pb.Referenced):
    def __init__(self):
        self.x = SimpleCache()
        
    def remote_getCache(self):
        return [self.x,self.x]
    
    def remote_putCache(self, cache):
        return (self.x is cache)
        

class Observable(pb.Referenced):
    def __init__(self):
        self.observers = []
        
    def remote_observe(self, obs):
        self.observers.append(obs)

    def remote_unobserve(self, obs):
        self.observers.remove(obs)

    def notify(self, obj):
        for observer in self.observers:
            observer.notify(self, obj)


class Observer(pb.Referenced):
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
        
        class X(pb.Referenced):
            def remote_catch(self,arg):
                self.caught = arg

        class Y(pb.Referenced):
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


    def testResult(self):
        c, s, pump = connectedServerAndClient()
        for x, y in (c, s), (s, c):
            # test reflexivity
            foo = SimpleRemote()
            x.setNameForLocal("foo", foo)
            bar = y.remoteForName("foo")
            self.expectedThunkResult = 8
            bar.thunk(self.expectedThunkResult - 1,
                      pbcallback=self.thunkResultGood,
                      pberrback=self.thunkErrorBad)
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
        x.getCopy(pbcallback=self.thunkResultGood,
                  pberrback=self.thunkErrorBad)
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
        

    def testRefcount(self):
        c, s, pump = connectedServerAndClient()
        foo = NestedRemote()
        s.setNameForLocal("foo", foo)
        bar = c.remoteForName("foo")
        bar.getSimple(pbcallback=self.refcountResult,
                      pberrback = self.thunkErrorBad)

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
        o2.getCache(pbcallback=coll.append)
        o2.getCache(pbcallback=coll.append)
        complex = []
        o3.getCache(pbcallback=complex.append)
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
        assert complex[0].checkFoo4()
        assert len(coll) == 2
        cp = coll[0][0]
        assert cp.checkMethod().im_self is cp, "potential refcounting issue"
        assert cp.checkSelf() is cp, "other potential refcounting issue"
        assert cp.__class__ is pb.CacheProxy, "class was %s" % str(cp.__class__)
        assert cp._CacheProxy__instance is coll[1][0]._CacheProxy__instance
        col2 = []
        o2.putCache(cp, pbcallback = col2.append)
        # now, refcounting (similiar to testRefCount)
        luid = cp._CacheProxy__luid
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
        assert not s.remotelyCachedObjects.has_key(luid)
        # The objects were the same (testing lcache identity)
        assert col2[0]

    def testProxy(self):
        c, s, pump = connectedServerAndClient()
        pump.pump()
        ident = c.remoteForName("identity")
        accum = []
        ident.attach("test", None, pbcallback=accum.append)
        pump.pump() # send call
        pump.pump() # get response
        test = accum.pop() # okay, this should be our perspective...
        test.getDummyProxy(pbcallback=accum.append)
        pump.pump() # send call
        pump.pump() # get response
        accum.pop().doNothing(pbcallback=accum.append)
        pump.pump()
        pump.pump()
        assert accum.pop() == 'hello world!', 'oops...'

testCases = [BrokerTestCase]
