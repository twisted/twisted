
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

"""Tests for Perspective Broker module.

TODO: update protocol level tests to use new connection API, leaving
only specific tests for old API.
"""

import sys, os

from cStringIO import StringIO

from twisted.trial import unittest
dR = unittest.deferredResult

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

class IOPump:
    """Utility to pump data between clients and servers for protocol testing.

    Perhaps this is a utility worthy of being in protocol.py?
    """
    def __init__(self, client, server, clientIO, serverIO):
        self.client = client
        self.server = server
        self.clientIO = clientIO
        self.serverIO = serverIO

    def flush(self):
        "Pump until there is no more input or output."
        reactor.iterate()
        while self.pump():
            reactor.iterate()
        reactor.iterate()


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
        self.client.transport._checkProducer()
        self.server.transport._checkProducer()
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
    auth = authorizer.DefaultAuthorizer()
    appl = Application("pb-test")
    auth.setServiceCollection(appl)
    ident = identity.Identity("guest", authorizer=auth)
    ident.setPassword("guest")
    svc = DummyService("test", appl, authorizer=auth)
    ident.addKeyForPerspective(svc.getPerspectiveNamed("any"))
    auth.addIdentity(ident)
    svr = pb.BrokerFactory(pb.AuthRoot(auth))
    s = svr.buildProtocol(('127.0.0.1',))
    s.copyTags = {}

    cio = StringIO()
    sio = StringIO()
    c.makeConnection(protocol.FileWrapper(cio))
    s.makeConnection(protocol.FileWrapper(sio))
    pump = IOPump(c, s, cio, sio)
    # Challenge-response authentication:
    pump.flush()
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

pb.setCopierForClass(SimpleCopy, SimpleLocalCopy)

class SimpleFactoryCopy(pb.Copyable):
    allIDs = {}
    def __init__(self, id):
        self.id = id
        SimpleFactoryCopy.allIDs[id] = self

def createFactoryCopy(state):
    id = state.get("id", None)
    if not id:
        raise "factory copy state has no 'id' member %s" % repr(state)
    if not SimpleFactoryCopy.allIDs.has_key(id):
        raise "factory class has no ID: %s" % SimpleFactoryCopy.allIDs
    inst = SimpleFactoryCopy.allIDs[id]
    if not inst:
        raise "factory method found no object with id"
    return inst

pb.setFactoryForClass(SimpleFactoryCopy, createFactoryCopy)

class NestedCopy(pb.Referenceable):
    def remote_getCopy(self):
        return SimpleCopy()

    def remote_getFactory(self, value):
        return SimpleFactoryCopy(value)
    
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
        self.observer.callRemote('foo',4)

    def getStateToCacheAndObserveFor(self, perspective, observer):
        self.observer = observer
        return {"x": self.x,
                "y": self.y,
                "foo": self.foo}

    def stoppedObserving(self, perspective, observer):
        log.msg("stopped observing")
        observer.callRemote("end")
        if observer == self.observer:
            self.observer = None

class RatherBaroqueCache(pb.RemoteCache):
    def observe_foo(self, newFoo):
        self.foo = newFoo

    def observe_end(self):
        log.msg("the end of things")

    def checkFoo4(self):
        return (self.foo == 4)

    def check(self):
        # checks based on above '__init__'
        assert self.x == 1
        assert self.y == 2
        assert self.foo == 3
        return 1

pb.setCopierForClass(VeryVeryComplicatedCacheable, RatherBaroqueCache)

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

pb.setCopierForClass(SimpleCache, SimpleLocalCache)

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
            observer.callRemote('notify', self, obj)

class DeferredRemote(pb.Referenceable):
    def __init__(self):
        self.run = 0

    def runMe(self, arg):
        self.run = arg
        return arg + 1

    def dontRunMe(self, arg):
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
        other.callRemote('unobserve',self)


class BrokerTestCase(unittest.TestCase):
    thunkResult = None

    def tearDown(self):
        import os
        try:
            os.unlink('None-None-TESTING.pub') # from RemotePublished.getFileName
        except OSError:
            pass

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
                a.callRemote('catch', b)

        s.setNameForLocal("y", Y())
        y = c.remoteForName("y")
        x = X()
        z = X()
        y.callRemote('throw', x, z)
        pump.pump()
        pump.pump()
        pump.pump()
        assert x.caught is z, "X should have caught Z"

        # make sure references to remote methods are equals
        self.assertEquals(y.remoteMethod('throw'), y.remoteMethod('throw'))

    def testResult(self):
        c, s, pump = connectedServerAndClient()
        for x, y in (c, s), (s, c):
            # test reflexivity
            foo = SimpleRemote()
            x.setNameForLocal("foo", foo)
            bar = y.remoteForName("foo")
            self.expectedThunkResult = 8
            bar.callRemote('thunk',self.expectedThunkResult - 1).addCallbacks(self.thunkResultGood, self.thunkErrorBad)
            # Send question.
            pump.pump()
            # Send response.
            pump.pump()
            # Shouldn't require any more pumping than that...
            assert self.thunkResult == self.expectedThunkResult,\
                   "result wasn't received."

    def refcountResult(self, result):
        self.nestedRemote = result

    def testTooManyRefs(self):
        l = []
        e = []
        c, s, pump = connectedServerAndClient()
        foo = NestedRemote()
        s.setNameForLocal("foo", foo)
        x = c.remoteForName("foo")
        for igno in xrange(pb.MAX_BROKER_REFS + 10):
            if s.transport.closed or c.transport.closed:
                break
            x.callRemote("getSimple").addCallbacks(l.append, e.append)
            pump.pump()
        expected = (pb.MAX_BROKER_REFS - 1)
        assert s.transport.closed, "transport was not closed"
        assert len(l) == expected, "expected %s got %s" % (expected, len(l))

    def testCopy(self):
        c, s, pump = connectedServerAndClient()
        foo = NestedCopy()
        s.setNameForLocal("foo", foo)
        x = c.remoteForName("foo")
        x.callRemote('getCopy').addCallbacks(self.thunkResultGood, self.thunkErrorBad)
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
        ra.callRemote('observe',b)
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
        e.callRemote('doItLater').addCallback(results.append)
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
        bar.callRemote('getSimple').addCallbacks(self.refcountResult, self.thunkErrorBad)

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
        if sys.hexversion >= 0x2000000 and os.name != "java":
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
        o2.callRemote("getCache").addCallback(coll.append).addErrback(coll.append)
        o2.callRemote("getCache").addCallback(coll.append).addErrback(coll.append)
        complex = []
        o3.callRemote("getCache").addCallback(complex.append)
        o3.callRemote("getCache").addCallback(complex.append)
        pump.flush()
        # `worst things first'
        assert complex[0].check()
        vcc.setFoo4()
        pump.flush()
        assert complex[0].checkFoo4(), "method was not called."
        assert len(coll) == 2
        cp = coll[0][0]
        assert cp.checkMethod().im_self is cp, "potential refcounting issue"
        assert cp.checkSelf() is cp, "other potential refcounting issue"
        col2 = []
        o2.callRemote('putCache',cp).addCallback(col2.append)
        pump.flush()
        # The objects were the same (testing lcache identity)
        assert col2[0]
        # test equality of references to methods
        self.assertEquals(o2.remoteMethod("getCache"), o2.remoteMethod("getCache"))

        # now, refcounting (similiar to testRefCount)
        luid = cp.luid
        baroqueLuid = complex[0].luid
        assert s.remotelyCachedObjects.has_key(luid), "remote cache doesn't have it"
        del coll
        del cp
        pump.flush()
        del complex
        del col2
        # extra nudge...
        pump.flush()
        # del vcc.observer
        # nudge the gc
        if sys.hexversion >= 0x2000000 and os.name != "java":
            import gc
            gc.collect()
        # try to nudge the GC even if we can't really
        pump.flush()
        # The GC is done with it.
        assert not s.remotelyCachedObjects.has_key(luid), "Server still had it after GC"
        assert not c.locallyCachedObjects.has_key(luid), "Client still had it after GC"
        assert not s.remotelyCachedObjects.has_key(baroqueLuid), "Server still had complex after GC"
        assert not c.locallyCachedObjects.has_key(baroqueLuid), "Client still had complex after GC"
        assert vcc.observer is None, "observer was not removed"

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
        pump.flush()
        pump.flush()
        pump.flush()
        
        test = accum.pop() # okay, this should be our perspective...
        test.callRemote('getDummyViewPoint').addCallback(accum.append)
        pump.flush()
        accum.pop().callRemote('doNothing').addCallback(accum.append)
        pump.flush()
        assert accum.pop() == 'hello world!', 'oops...'

    def testPublishable(self):
        import os
        try:
            os.unlink('None-None-TESTING.pub') # from RemotePublished.getFileName
        except OSError:
            pass # Sometimes it's not there.
        c, s, pump = connectedServerAndClient()
        foo = GetPublisher()
        # foo.pub.timestamp = 1.0
        s.setNameForLocal("foo", foo)
        bar = c.remoteForName("foo")
        accum = []
        bar.callRemote('getPub').addCallbacks(accum.append, self.thunkErrorBad)
        pump.flush()
        obj = accum.pop()
        self.assertEquals(obj.activateCalled, 1)
        self.assertEquals(obj.isActivated, 1)
        self.assertEquals(obj.yayIGotPublished, 1)
        self.assertEquals(obj._wasCleanWhenLoaded, 0) # timestamp's dirty, we don't have a cache file
        c, s, pump = connectedServerAndClient()
        s.setNameForLocal("foo", foo)
        bar = c.remoteForName("foo")
        bar.callRemote('getPub').addCallbacks(accum.append, self.thunkErrorBad)
        pump.flush()
        obj = accum.pop()
        self.assertEquals(obj._wasCleanWhenLoaded, 1) # timestamp's clean, our cache file is up-to-date

    def gotCopy(self, val):
        self.thunkResult = val.id
        
    def testFactoryCopy(self):
        c, s, pump = connectedServerAndClient()
        ID = 99
        obj = NestedCopy()
        s.setNameForLocal("foo", obj)
        x = c.remoteForName("foo")
        x.callRemote('getFactory', ID).addCallbacks(self.gotCopy, self.thunkResultBad)
        pump.pump()
        pump.pump()
        pump.pump()
        assert self.thunkResult == ID, "ID not correct on factory object %s" % self.thunkResult

from twisted.spread.util import Pager, StringPager, FilePager, getAllPages

bigString = "helloworld" * 50

callbackArgs = None
callbackKeyword = None

def finishedCallback(*args, **kw):
    global callbackArgs, callbackKeyword
    callbackArgs = args
    callbackKeyword = kw

class Pagerizer(pb.Referenceable):
    def __init__(self, callback, *args, **kw):
        self.callback, self.args, self.kw = callback, args, kw

    def remote_getPages(self, collector):
        StringPager(collector, bigString, 100, self.callback, *self.args, **self.kw)
        self.args = self.kw = None

class FilePagerizer(pb.Referenceable):
    def __init__(self, filename, callback, *args, **kw):
        self.filename = filename
        self.callback, self.args, self.kw = callback, args, kw

    def remote_getPages(self, collector):
        FilePager(collector, file(self.filename), self.callback, *self.args, **self.kw)
        self.args = self.kw = None
        

class PagingTestCase(unittest.TestCase):
    def setUpClass(self):
        self.filename = self.mktemp()
        fd = file(self.filename, 'w')
        fd.write(bigString)
        fd.close()

    def tearDownClass(self):
        os.remove(self.filename)

    def testPagingWithCallback(self):
        c, s, pump = connectedServerAndClient()
        s.setNameForLocal("foo", Pagerizer(finishedCallback, 'hello', value = 10))
        x = c.remoteForName("foo")
        l = []
        getAllPages(x, "getPages").addCallback(l.append)
        while not l:
            pump.pump()
        assert ''.join(l[0]) == bigString, "Pages received not equal to pages sent!"
        assert callbackArgs == ('hello',), "Completed callback not invoked"
        assert callbackKeyword == {'value': 10}, "Completed callback not invoked"

    def testPagingWithoutCallback(self):
        c, s, pump = connectedServerAndClient()
        s.setNameForLocal("foo", Pagerizer(None))
        x = c.remoteForName("foo")
        l = []
        getAllPages(x, "getPages").addCallback(l.append)
        while not l:
            pump.pump()
        assert ''.join(l[0]) == bigString, "Pages received not equal to pages sent!"

    def testFilePagingWithCallback(self):
        c, s, pump = connectedServerAndClient()
        s.setNameForLocal("bar", FilePagerizer(self.filename, finishedCallback,
                                               'frodo', value = 9))
        x = c.remoteForName("bar")
        l = []
        getAllPages(x, "getPages").addCallback(l.append)
        while not l:
            pump.pump()
        assert ''.join(l[0]) == bigString, "Pages received not equal to pages sent!"
        assert callbackArgs == ('frodo',), "Completed callback not invoked"
        assert callbackKeyword == {'value': 9}, "Completed callback not invoked"

    def testFilePagingWithoutCallback(self):
        c, s, pump = connectedServerAndClient()
        s.setNameForLocal("bar", FilePagerizer(self.filename, None))
        x = c.remoteForName("bar")
        l = []
        getAllPages(x, "getPages").addCallback(l.append)
        while not l:
            pump.pump()
        assert ''.join(l[0]) == bigString, "Pages received not equal to pages sent!"


from twisted.spread import publish

class DumbPublishable(publish.Publishable):
    def getStateToPublish(self):
        return {"yayIGotPublished": 1}

class DumbPub(publish.RemotePublished):
    def activated(self):
        self.activateCalled = 1

class GetPublisher(pb.Referenceable):
    def __init__(self):
        self.pub = DumbPublishable("TESTING")
    def remote_getPub(self):
        return self.pub


pb.setCopierForClass(DumbPublishable, DumbPub)

class DisconnectionTestCase(unittest.TestCase):
    """Test disconnection callbacks."""
    
    def error(self, *args):
        raise RuntimeError, "I shouldn't have been called: %s" % args
    
    def gotDisconnected(self):
        """Called on broker disconnect."""
        self.gotCallback = 1
    
    def objectDisconnected(self, o):
        """Called on RemoteReference disconnect."""
        self.assertEquals(o, self.remoteObject)
        self.objectCallback = 1

    def testBadSerialization(self):
        c, s, pump = connectedServerAndClient()
        pump.pump()
        s.setNameForLocal("o", BadCopySet())
        g = c.remoteForName("o")
        l = []
        g.callRemote("setBadCopy", BadCopyable()).addErrback(l.append)
        reactor.iterate()
        pump.flush()
        self.assertEquals(len(l), 1)

    def testDisconnection(self):
        c, s, pump = connectedServerAndClient()
        pump.pump()
        s.setNameForLocal("o", SimpleRemote())
        
        # get a client reference to server object
        r = c.remoteForName("o")
        pump.pump()
        pump.pump()
        pump.pump()
        
        # register and then unregister disconnect callbacks
        # making sure they get unregistered
        c.notifyOnDisconnect(self.error)
        self.assert_(self.error in c.disconnects)
        c.dontNotifyOnDisconnect(self.error)
        self.assert_(not (self.error in c.disconnects))
        
        r.notifyOnDisconnect(self.error)
        self.assert_(r._disconnected in c.disconnects)
        self.assert_(self.error in r.disconnectCallbacks)
        r.dontNotifyOnDisconnect(self.error)
        self.assert_(not (r._disconnected in c.disconnects))
        self.assert_(not (self.error in r.disconnectCallbacks))
        
        # register disconnect callbacks
        c.notifyOnDisconnect(self.gotDisconnected)
        r.notifyOnDisconnect(self.objectDisconnected)
        self.remoteObject = r
        
        # disconnect
        c.connectionLost(failure.Failure(main.CONNECTION_DONE))
        self.assert_(self.gotCallback)
        self.assert_(self.objectCallback)

class FreakOut(Exception):
    pass

class BadCopyable(pb.Copyable):
    def getStateToCopyFor(self, p):
        raise FreakOut

class BadCopySet(pb.Referenceable):
    def remote_setBadCopy(self, bc):
        return None

class LocalRemoteTest(util.LocalAsRemote):
    reportAllTracebacks = 0

    def sync_add1(self, x):
        return x + 1

    def async_add(self, x=0, y=1):
        return x + y

    def async_fail(self):
        raise RuntimeError


class SpreadUtilTestCase(unittest.TestCase):
    """Tests for twisted.spread.util"""
    
    def testSync(self):
        o = LocalRemoteTest()
        self.assertEquals(o.callRemote("add1", 2), 3)
    
    def testAsync(self):
        l = []
        o = LocalRemoteTest()
        d = o.callRemote("add", 2, y=4)
        self.assert_(isinstance(d, defer.Deferred))
        d.addCallback(l.append)
        reactor.iterate()
        self.assertEquals(l, [6])
    
    def testAsyncFail(self):
        l = []
        o = LocalRemoteTest()
        d = o.callRemote("fail")
        d.addErrback(l.append)
        reactor.iterate()
        self.assertEquals(len(l), 1)
        self.assert_(isinstance(l[0], failure.Failure))
    
    def testRemoteMethod(self):
        o = LocalRemoteTest()
        m = o.remoteMethod("add1")
        self.assertEquals(m(3), 4)


class ReconnectOnce(pb.PBClientFactory):

    reconnected = 0
    
    def clientConnectionLost(self, connector, reason):
        pb.PBClientFactory.clientConnectionLost(self, connector, reason,
                                                reconnecting=(not self.reconnected))
        if not self.reconnected:
            self.reconnected = 1
            connector.connect()


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
    
    # tests for *really* deprecated APIs:
    def testGetObjectAt(self):
        root = dR(pb.getObjectAt("127.0.0.1", self.portno))
        self._checkRootObject(root)
        root.broker.transport.loseConnection()
                       
    def testConnect(self):
        p = dR(pb.connect("127.0.0.1", self.portno, "guest", "guest", "test",
                          perspectiveName="any"))
        self.assert_(isinstance(p, pb.RemoteReference))
        p.broker.transport.loseConnection()

    def testIdentityConnector(self):
        iConnector = pb.IdentityConnector("127.0.0.1", self.portno, "guest", "guest")
        p1 = dR(iConnector.requestService("test", perspectiveName="any"))
        p2 = dR(iConnector.requestService("test", perspectiveName="any"))
        self.assert_(isinstance(p1, pb.RemoteReference))
        self.assert_(isinstance(p2, pb.RemoteReference))
        iConnector.disconnect()

    # tests for new, shiny API, although getPerspective stuff is also deprecated:
    def testGoodGetObject(self):
        # we test getting both before and after connection
        factory = pb.PBClientFactory()
        d = factory.getRootObject()
        reactor.connectTCP("127.0.0.1", self.portno, factory)
        root = dR(d)
        self._checkRootObject(root)
        root = dR(factory.getRootObject())
        self._checkRootObject(root)
        root.broker.transport.loseConnection()
    
    def testGoodPerspective(self):
        # we test getting both before and after connection
        factory = pb.PBClientFactory()
        d = factory.getPerspective("guest", "guest", "test", perspectiveName="any")
        reactor.connectTCP("127.0.0.1", self.portno, factory)
        p = dR(d)
        self.assert_(isinstance(p, pb.RemoteReference))
        d = factory.getPerspective("guest", "guest", "test", perspectiveName="any")
        p = dR(d)
        self.assert_(isinstance(p, pb.RemoteReference))
        p.broker.transport.loseConnection()
    
    def testGoodFailedConnect(self):
        factory = pb.PBClientFactory()
        d = factory.getPerspective("guest", "guest", "test", perspectiveName="any")
        reactor.connectTCP("127.0.0.1", 69, factory)
        f = unittest.deferredError(d)
        from twisted.internet import error
        f.trap(error.ConnectError)

    def testDisconnect(self):
        factory = pb.PBClientFactory()
        d = factory.getPerspective("guest", "guest", "test", perspectiveName="any")
        reactor.connectTCP("127.0.0.1", self.portno, factory)
        p = dR(d)
        d = dR(p.callRemote("getDummyViewPoint")) # just to check it's working
        factory.disconnect()
        reactor.iterate(); reactor.iterate(); reactor.iterate()
        self.assertRaises(pb.DeadReferenceError, p.callRemote, "getDummyViewPoint")

    def testEmptyPerspective(self):
        factory = pb.PBClientFactory()
        d = factory.getPerspective("foo", "foo", "test")
        reactor.connectTCP("127.0.0.1", self.portno, factory)
        p = dR(d)
        self.assert_(isinstance(p, pb.RemoteReference))
        p.broker.transport.loseConnection()

    def testReconnect(self):
        factory = ReconnectOnce()
        l = []
        def disconnected(p):
            self.assertEquals(l, [])
            l.append(factory.getPerspective("guest", "guest", "test", perspectiveName="any"))
        d = factory.getPerspective("guest", "guest", "test", perspectiveName="any")
        reactor.connectTCP("127.0.0.1", self.portno, factory)
        p = dR(d)
        self.assert_(isinstance(p, pb.RemoteReference))
        p.notifyOnDisconnect(disconnected)
        factory.disconnect()
        while not l:
            reactor.iterate()
        p = dR(l[0])
        self.assert_(isinstance(p, pb.RemoteReference))
        factory.disconnect()

    def testImmediateClose(self):
        from twisted.internet import protocol
        p = dR(protocol.ClientCreator(reactor, protocol.Protocol
                                      ).connectTCP("127.0.0.1", self.portno))
        p.transport.loseConnection()
        reactor.iterate(); reactor.iterate()


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

class MyPerspective(pb.Avatar):

    __implements__ = pb.IPerspective,

    loggedIn = loggedOut = False

    def __init__(self):
        pass
    
    def perspective_getViewPoint(self):
        return MyView()

    def logout(self):
        self.loggedOut = 1

class MyView(pb.Viewable):

    def view_check(self, user):
        return isinstance(user, MyPerspective)


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
    
    def testLoginLogout(self):
        factory = pb.PBClientFactory()
        # NOTE: real code probably won't need anything where we have the "BRAINS!"
        # argument, passing None is fine. We just do it here to test that it is
        # being passed. It is used to give additional info to the realm to aid
        # perspective creation, if you don't need that, ignore it.
        d = factory.login(credentials.UsernamePassword("user", "pass"), "BRAINS!")
        reactor.connectTCP("127.0.0.1", self.portno, factory)
        p = dR(d)
        self.assertEquals(self.realm.p.loggedIn, 1)
        self.assert_(isinstance(p, pb.RemoteReference))
        factory.disconnect()        
        for i in range(5):
            reactor.iterate()
        self.assertEquals(self.realm.p.loggedOut, 1)

    def testBadLogin(self):
        factory = pb.PBClientFactory()
        for username, password in [("nosuchuser", "pass"), ("user", "wrongpass")]:
            d = factory.login(credentials.UsernamePassword("user1", "pass"), "BRAINS!")
            c = reactor.connectTCP("127.0.0.1", self.portno, factory)
            p = unittest.deferredError(d)
            self.failUnless(p.check("twisted.cred.error.UnauthorizedLogin"))
            c.disconnect()
            reactor.iterate()
            reactor.iterate()
            reactor.iterate()
        from twisted.cred.error import UnauthorizedLogin
        log.flushErrors(UnauthorizedLogin)
    
    def testView(self):
        factory = pb.PBClientFactory()
        d = factory.login(credentials.UsernamePassword("user", "pass"), "BRAINS!")
        reactor.connectTCP("127.0.0.1", self.portno, factory)
        p = dR(d)
        v = dR(p.callRemote("getViewPoint"))
        self.assertEquals(dR(v.callRemote("check")), 1)
        factory.disconnect()

class NonSubclassingPerspective:
    __implements__ = pb.IPerspective,

    # IPerspective implementation
    def perspectiveMessageReceived(self, broker, message, args, kwargs):
        args = broker.unserialize(args, self)
        kwargs = broker.unserialize(kwargs, self)
        return broker.serialize((message, args, kwargs))

    # Methods required by MyRealm
    def logout(self):
        self.loggedOut = True
    
class NSPTestCase(unittest.TestCase):
    def setUp(self):
        self.realm = MyRealm()
        self.realm.p = NonSubclassingPerspective()
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


    def testNSP(self):
        factory = pb.PBClientFactory()
        d = factory.login(credentials.UsernamePassword('user', 'pass'), "BRAINS!")
        reactor.connectTCP('127.0.0.1', self.portno, factory)
        p = dR(d)
        self.assertEquals(dR(p.callRemote('ANYTHING', 'here', bar='baz')),
                          ('ANYTHING', ('here',), {'bar': 'baz'}))
        factory.disconnect()

