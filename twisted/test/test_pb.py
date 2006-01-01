
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Tests for Perspective Broker module.

TODO: update protocol level tests to use new connection API, leaving
only specific tests for old API.
"""

# issue1195 TODOs: replace pump.pump() with something involving Deferreds.
# Clean up warning suppression. Find a better replacement for the handful of
# reactor.callLater(0.1, ..) calls.

import sys, os, time

from cStringIO import StringIO
from zope.interface import implements

from twisted.trial import unittest
# module-level 'suppress' has special meaning to Trial, so import this under
# a different name
from twisted.trial.util import suppress as util_suppress

from twisted.spread import pb, util
from twisted.internet import protocol, main, error
from twisted.internet.app import Application
from twisted.internet.utils import suppressWarnings
from twisted.python import failure, log
from twisted.cred import identity, authorizer
from twisted.cred.error import UnauthorizedLogin
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
        """Pump until there is no more input or output. This does not run any
        timers, so don't use it with any code that calls reactor.callLater"""
        # failsafe timeout
        timeout = time.time() + 5
        while self.pump():
            if time.time() > timeout:
                return

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

_appSuppress = util_suppress(
    message="twisted.internet.app is deprecated, use twisted.application or the reactor instead.",
    category=DeprecationWarning)

_identitySuppress = util_suppress(
    message="Identities are deprecated, switch to credentialcheckers etc.",
    category=DeprecationWarning)

_authorizerSuppress = util_suppress(
    message="Authorizers are deprecated, switch to portals/realms/etc.",
    category=DeprecationWarning)

_credServiceSuppress = util_suppress(
    message="Cred services are deprecated, use realms instead.",
    category=DeprecationWarning)

_perspectiveSuppress = util_suppress(
    message="pb.Perspective is deprecated, please use pb.Avatar.",
    category=DeprecationWarning)

_loginBackendSuppress = util_suppress(
    message="Update your backend to use PBServerFactory, and then use login().",
    category=DeprecationWarning)

_pbServerFactorySuppress = util_suppress(
    message="This is deprecated. Use PBServerFactory.",
    category=DeprecationWarning)

_pbClientFactorySuppress = util_suppress(
    message="This is deprecated. Use PBClientFactory.",
    category=DeprecationWarning)


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
connectedServerAndClient = suppressWarnings(
    connectedServerAndClient,
    _authorizerSuppress,
    _appSuppress,
    _identitySuppress,
    _credServiceSuppress,
    _pbServerFactorySuppress,
    )

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

class NewStyleCopy(pb.Copyable, pb.RemoteCopy, object):
    def __init__(self, s):
        self.s = s
pb.setUnjellyableForClass(NewStyleCopy, NewStyleCopy)

class NewStyleCopy2(pb.Copyable, pb.RemoteCopy, object):
    allocated = 0
    initialized = 0
    value = 1
    def __new__(self):
        NewStyleCopy2.allocated += 1
        inst = object.__new__(self)
        inst.value = 2
        return inst
    def __init__(self):
        NewStyleCopy2.initialized += 1

pb.setUnjellyableForClass(NewStyleCopy2, NewStyleCopy2)

class Echoer(pb.Root):
    def remote_echo(self, st):
        return st

class NewStyleTestCase(unittest.TestCase):
    ref = None
    
    def tearDown(self):
        if self.ref:
            self.ref.broker.transport.loseConnection()
        return self.server.stopListening()

    def testNewStyle(self):
        self.server = reactor.listenTCP(0, pb.PBServerFactory(Echoer()))
        f = pb.PBClientFactory()
        reactor.connectTCP("localhost", self.server.getHost().port, f)
        d = f.getRootObject()
        d.addCallback(self._testNewStyle_1)
        return d
    def _testNewStyle_1(self, ref):
        self.ref = ref
        orig = NewStyleCopy("value")
        d = ref.callRemote("echo", orig)
        d.addCallback(self._testNewStyle_2, orig)
        return d
    def _testNewStyle_2(self, res, orig):
        self.failUnless(isinstance(res, NewStyleCopy))
        self.failUnlessEqual(res.s, "value")
        self.failIf(res is orig) # no cheating :)

    def testAlloc(self):
        self.server = reactor.listenTCP(0, pb.PBServerFactory(Echoer()))
        f = pb.PBClientFactory()
        reactor.connectTCP("localhost", self.server.getHost().port, f)
        d = f.getRootObject()
        d.addCallback(self._testAlloc_1)
        return d
    def _testAlloc_1(self, ref):
        self.ref = ref
        orig = NewStyleCopy2()
        self.failUnlessEqual(NewStyleCopy2.allocated, 1)
        self.failUnlessEqual(NewStyleCopy2.initialized, 1)
        d = ref.callRemote("echo", orig)
        # sending the object creates a second one on the far side
        d.addCallback(self._testAlloc_2, orig)
        return d
    def _testAlloc_2(self, res, orig):
        # receiving the response creates a third one on the way back
        self.failUnless(isinstance(res, NewStyleCopy2))
        self.failUnlessEqual(res.value, 2)
        self.failUnlessEqual(NewStyleCopy2.allocated, 3)
        self.failUnlessEqual(NewStyleCopy2.initialized, 1)
        self.failIf(res is orig) # no cheating :)


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
    testViewPoint.suppress = [_pbClientFactorySuppress, _perspectiveSuppress]


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
        o = LocalRemoteTest()
        d = o.callRemote("add", 2, y=4)
        self.assert_(isinstance(d, defer.Deferred))
        d.addCallback(self.assertEquals, 6)
        return d

    def testAsyncFail(self):
        l = []
        o = LocalRemoteTest()
        d = o.callRemote("fail")
        d.addCallbacks(lambda res: self.fail("supposed to fail"),
                       lambda f: self.assert_(isinstance(f, failure.Failure)))
        return d

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
        self.refs = [] # these will be .broker.transport.loseConnection()'ed
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
        self.portno = self.port.getHost().port
    setUp = suppressWarnings(setUp,
        _authorizerSuppress,
        _appSuppress,
        _identitySuppress,
        _credServiceSuppress,
        _loginBackendSuppress)


    def tearDown(self):
        for r in self.refs:
            r.broker.transport.loseConnection()
        return self.port.stopListening()

    def addRef(self, ref):
        self.refs.append(ref)
        return ref

    def _checkRootObject(self, root):
        d = root.callRemote("username", "guest")
        d.addCallback(self._checkRootObject_2)
        return d
    def _checkRootObject_2(self, challenge):
        self.assertEquals(len(challenge), 2)
        self.assert_(isinstance(challenge[1], pb.RemoteReference))

    def _checkIsRemoteReference(self, r):
        self.assert_(isinstance(r, pb.RemoteReference))
        return r

    # tests for *really* deprecated APIs:
    def testGetObjectAt(self):
        d = pb.getObjectAt("127.0.0.1", self.portno)
        d.addCallback(self.addRef)
        d.addCallback(self._checkRootObject)
        return d
    testGetObjectAt.suppress = [_pbClientFactorySuppress]

                          
    def testConnect(self):
        d = pb.connect("127.0.0.1", self.portno, "guest", "guest", "test",
                       perspectiveName="any")
        d.addCallback(self.addRef)
        d.addCallback(self._checkIsRemoteReference)
        return d
    testConnect.suppress = [_pbClientFactorySuppress,
                            _pbServerFactorySuppress,
                            _loginBackendSuppress,
                            _perspectiveSuppress]



    def testIdentityConnector(self):
        dl = []
        iConnector = pb.IdentityConnector("127.0.0.1", self.portno,
                                          "guest", "guest")
        d1 = iConnector.requestService("test", perspectiveName="any")
        d1.addCallback(self._checkIsRemoteReference)
        dl.append(d1)
        d2 = iConnector.requestService("test", perspectiveName="any")
        d2.addCallback(self._checkIsRemoteReference)
        dl.append(d2)
        d3 = defer.DeferredList(dl)
        d3.addCallback(lambda res: iConnector.disconnect())
        return d3
    testIdentityConnector.suppress = [_pbServerFactorySuppress,
                                      _pbClientFactorySuppress,
                                      _perspectiveSuppress]


    # tests for new, shiny API, although getPerspective stuff is also
    # deprecated:
    def testGoodGetObject(self):
        # we test getting both before and after connection
        factory = pb.PBClientFactory()
        d = factory.getRootObject()
        reactor.connectTCP("127.0.0.1", self.portno, factory)
        d.addCallback(self.addRef)
        d.addCallback(self._checkRootObject)
        d.addCallback(self._testGoodGetObject_1, factory)
        return d


    def _testGoodGetObject_1(self, res, factory):
        d = factory.getRootObject()
        d.addCallback(self.addRef)
        d.addCallback(self._checkRootObject)
        return d


    def testGoodPerspective(self):
        # we test getting both before and after connection
        factory = pb.PBClientFactory()
        d = factory.getPerspective("guest", "guest", "test",
                                   perspectiveName="any")
        reactor.connectTCP("127.0.0.1", self.portno, factory)
        d.addCallback(self.addRef)
        d.addCallback(self._checkIsRemoteReference)
        d.addCallback(self._testGoodPerspective_1, factory)
        return d


    def _testGoodPerspective_1(self, res, factory):
        d = factory.getPerspective("guest", "guest", "test",
                                   perspectiveName="any")
        d.addCallback(self.addRef)
        d.addCallback(self._checkIsRemoteReference)
        return d
    testGoodPerspective.suppress = [_perspectiveSuppress,
                                    _loginBackendSuppress]


    def testGoodFailedConnect(self):
        factory = pb.PBClientFactory()
        d = factory.getPerspective("guest", "guest", "test",
                                   perspectiveName="any")
        reactor.connectTCP("127.0.0.1", 69, factory)
        return self.assertFailure(d, error.ConnectError)
    testGoodFailedConnect.suppress = [_loginBackendSuppress]


    def testDisconnect(self):
        factory = pb.PBClientFactory()
        d = factory.getPerspective("guest", "guest", "test",
                                   perspectiveName="any")
        reactor.connectTCP("127.0.0.1", self.portno, factory)
        d.addCallback(self._testDisconnect_1, factory)
        return d
    def _testDisconnect_1(self, p, factory):
        d = p.callRemote("getDummyViewPoint") # just to check it's working
        d.addCallback(self._testDisconnect_2, p, factory)
        return d
    def _testDisconnect_2(self, res, p, factory):
        factory.disconnect()
        d = defer.Deferred()

        # TODO: clunky, but it works
        
        # XXX no it doesn't, it's a race-condition.  This should be using
        # notifyOnDisconnect to be *sure* it's gone.

        reactor.callLater(0.1, d.callback, p)
        #reactor.iterate(); reactor.iterate(); reactor.iterate()
        d.addCallback(self._testDisconnect_3)
        return d
    def _testDisconnect_3(self, p):
        self.assertRaises(pb.DeadReferenceError,
                          p.callRemote, "getDummyViewPoint")
    testDisconnect.suppress = [_perspectiveSuppress,
                               _loginBackendSuppress]


    def testEmptyPerspective(self):
        factory = pb.PBClientFactory()
        d = factory.getPerspective("foo", "foo", "test")
        reactor.connectTCP("127.0.0.1", self.portno, factory)
        d.addCallback(self._checkIsRemoteReference)
        d.addCallback(self.addRef)
        return d
    testEmptyPerspective.suppress = [_perspectiveSuppress,
                                     _loginBackendSuppress,
                                     _pbServerFactorySuppress]

    def testReconnect(self):
        factory = ReconnectOnce()
        l = []
        d1 = defer.Deferred()

        def disconnected(p):
            d2 = factory.getPerspective("guest", "guest", "test",
                                        perspectiveName="any")
            d2.addCallback(d1.callback)

        d = factory.getPerspective("guest", "guest", "test",
                                   perspectiveName="any")
        reactor.connectTCP("127.0.0.1", self.portno, factory)
        d.addCallback(self._checkIsRemoteReference)
        d.addCallback(lambda p: p.notifyOnDisconnect(disconnected))
        d.addCallback(lambda res: factory.disconnect())
        d1.addCallback(self._checkIsRemoteReference)
        d1.addCallback(lambda res: factory.disconnect())
        return d1
    testReconnect.suppress = [_pbServerFactorySuppress,
                              _loginBackendSuppress,
                              _perspectiveSuppress]

    def testImmediateClose(self):
        cc = protocol.ClientCreator(reactor, protocol.Protocol)
        d = cc.connectTCP("127.0.0.1", self.portno)
        d.addCallback(lambda p: p.transport.loseConnection())
        d = defer.Deferred()
        # clunky, but it works
        reactor.callLater(0.1, d.callback, None)
        return d


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

    implements(pb.IPerspective)

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
        self.portno = self.port.getHost().port

    def tearDown(self):
        return self.port.stopListening()
    
    def testLoginLogout(self):
        factory = pb.PBClientFactory()
        # NOTE: real code probably won't need anything where we have the
        # "BRAINS!" argument, passing None is fine. We just do it here to
        # test that it is being passed. It is used to give additional info to
        # the realm to aid perspective creation, if you don't need that,
        # ignore it.
        d = factory.login(credentials.UsernamePassword("user", "pass"),
                          "BRAINS!")
        reactor.connectTCP("127.0.0.1", self.portno, factory)
        d.addCallback(self._testLoginLogout_1, factory)
        return d
    def _testLoginLogout_1(self, p, factory):
        self.assertEquals(self.realm.p.loggedIn, 1)
        self.assert_(isinstance(p, pb.RemoteReference))
        factory.disconnect()
        d = defer.Deferred()
        reactor.callLater(0.1, d.callback, None)
        d.addCallback(lambda res: self.assertEquals(self.realm.p.loggedOut, 1))
        return d


    def testBadLogin(self):
        d = defer.succeed(None)
        for username, password in [("nosuchuser", "pass"),
                                   ("user", "wrongpass")]:
            d.addCallback(self._testBadLogin_once, username, password)
        d.addBoth(lambda res: log.flushErrors(UnauthorizedLogin))
        return d

    def _testBadLogin_once(self, res, username, password):
        factory = pb.PBClientFactory()
        creds = credentials.UsernamePassword(username, password)
        d = factory.login(creds, "BRAINS!")
        c = reactor.connectTCP("127.0.0.1", self.portno, factory)
        d.addCallbacks(lambda res: self.fail("should have failed"),
                       lambda f: f.trap(UnauthorizedLogin))
        d.addCallback(lambda res: factory.disconnect())
        return d


    def testView(self):
        factory = pb.PBClientFactory()
        d = factory.login(credentials.UsernamePassword("user", "pass"),
                          "BRAINS!")
        reactor.connectTCP("127.0.0.1", self.portno, factory)
        d.addCallback(lambda p: p.callRemote("getViewPoint"))
        d.addCallback(lambda v: v.callRemote("check"))
        d.addCallback(self.assertEquals, True)
        d.addCallback(lambda res: factory.disconnect())
        return d

class NonSubclassingPerspective:
    implements(pb.IPerspective)

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
        self.portno = self.port.getHost().port

    def tearDown(self):
        self.port.stopListening()

    def testNSP(self):
        factory = pb.PBClientFactory()
        d = factory.login(credentials.UsernamePassword('user', 'pass'),
                          "BRAINS!")
        reactor.connectTCP('127.0.0.1', self.portno, factory)
        d.addCallback(lambda p: p.callRemote('ANYTHING', 'here', bar='baz'))
        d.addCallback(self.assertEquals, 
                      ('ANYTHING', ('here',), {'bar': 'baz'}))
        d.addCallback(lambda res: factory.disconnect())
        return d

