#! /usr/bin/python

import gc

from twisted.python import log
import sys
#log.startLogging(sys.stderr)

from zope.interface import implements, implementsOnly
from twisted.python import components, failure, reflect
from twisted.internet import reactor, defer
from twisted.trial import unittest

dr = unittest.deferredResult
de = unittest.deferredError

import schema, pb, flavors, tokens
from tokens import BananaError, Violation, INT, STRING, OPEN
from slicer import BananaFailure

class TestBroker(pb.Broker):
    def gotAnswer(self, results, req):
        self.answers.append((True, req, results))
    def gotError(self, f, req):
        self.answers.append((False, req, f))
    def freeRemoteReference(self, refID):
        pass

class TestReferenceUnslicer(unittest.TestCase):
    # OPEN(reference), INT(refid), [STR(interfacename), INT(version)]... CLOSE
    def setUp(self):
        self.broker = TestBroker()

    def newUnslicer(self):
        unslicer = flavors.ReferenceUnslicer()
        unslicer.broker = self.broker
        unslicer.opener = self.broker.rootUnslicer
        return unslicer

    def testReject(self):
        u = self.newUnslicer()
        self.failUnlessRaises(BananaError, u.checkToken, STRING, 10)
        u = self.newUnslicer()
        self.failUnlessRaises(BananaError, u.checkToken, OPEN, 0)

    def testNoInterfaces(self):
        u = self.newUnslicer()
        u.checkToken(INT, 0)
        u.receiveChild(12)
        rr1 = u.receiveClose()
        rr2 = self.broker.remoteReferences.get(12)
        self.failUnless(rr2)
        self.failUnless(isinstance(rr2, pb.RemoteReference))
        self.failUnlessEqual(rr2.broker, self.broker)
        self.failUnlessEqual(rr2.refID, 12)
        self.failUnlessEqual(rr2.interfaceNames, [])

    def testInterfaces(self):
        u = self.newUnslicer()
        u.checkToken(INT, 0)
        u.receiveChild(12)
        u.checkToken(OPEN, 9999)
        # pretend we did a u.doOpen("list") here
        interfaceNames = ["IBar", "IFoo"]
        u.receiveChild(interfaceNames)
        rr1 = u.receiveClose()
        rr2 = self.broker.remoteReferences.get(12)
        self.failUnless(rr2)
        self.failUnlessIdentical(rr1, rr2)
        self.failUnless(isinstance(rr2, pb.RemoteReference))
        self.failUnlessEqual(rr2.broker, self.broker)
        self.failUnlessEqual(rr2.refID, 12)
        self.failUnlessEqual(rr2.interfaceNames, interfaceNames)

class TestAnswer(unittest.TestCase):
    # OPEN(answer), INT(reqID), [answer], CLOSE
    def setUp(self):
        self.broker = TestBroker()
        self.broker.answers = []

    def newUnslicer(self):
        unslicer = pb.AnswerUnslicer()
        unslicer.broker = self.broker
        unslicer.opener = self.broker.rootUnslicer
        unslicer.protocol = self.broker
        return unslicer

    def makeRequest(self):
        req = pb.PendingRequest(defer.Deferred())

    def testAccept1(self):
        req = pb.PendingRequest(12)
        self.broker.addRequest(req)
        u = self.newUnslicer()
        u.checkToken(INT, 0)
        u.receiveChild(12) # causes broker.getRequest
        u.checkToken(STRING, 8)
        u.receiveChild("results")
        self.failIf(self.broker.answers)
        u.receiveClose() # causes broker.gotAnswer
        self.failUnlessEqual(self.broker.answers, [(True, req, "results")])

    def testAccept2(self):
        req = pb.PendingRequest(12)
        req.setConstraint(schema.makeConstraint(str))
        self.broker.addRequest(req)
        u = self.newUnslicer()
        u.checkToken(INT, 0)
        u.receiveChild(12) # causes broker.getRequest
        u.checkToken(STRING, 15)
        u.receiveChild("results")
        self.failIf(self.broker.answers)
        u.receiveClose() # causes broker.gotAnswer
        self.failUnlessEqual(self.broker.answers, [(True, req, "results")])


    def testReject1(self):
        # answer a non-existent request
        req = pb.PendingRequest(12)
        self.broker.addRequest(req)
        u = self.newUnslicer()
        u.checkToken(INT, 0)
        self.failUnlessRaises(Violation, u.receiveChild, 13)

    def testReject2(self):
        # answer a request with a result that violates the constraint
        req = pb.PendingRequest(12)
        req.setConstraint(schema.makeConstraint(int))
        self.broker.addRequest(req)
        u = self.newUnslicer()
        u.checkToken(INT, 0)
        u.receiveChild(12)
        self.failUnlessRaises(Violation, u.checkToken, STRING, 42)
        # this does not yet errback the request
        self.failIf(self.broker.answers)
        # it gets errbacked when banana reports the violation
        v = Violation("icky")
        v.setLocation("here")
        u.reportViolation(BananaFailure(v))
        self.failUnlessEqual(len(self.broker.answers), 1)
        err = self.broker.answers[0]
        self.failIf(err[0])
        self.failUnlessEqual(err[1], req)
        f = err[2]
        self.failUnless(f.check(Violation))

#from twisted.internet import interfaces
class Loopback:
#   implements(interfaces.ITransport)
    def write(self, data):
        try:
            # isolate exceptions
            self.peer.dataReceived(data)
        except Exception, e:
            f = failure.Failure()
            log.err(f)
            print "Loopback.write exception"
            self.loseConnection(f)

    def loseConnection(self, why="unknown"):
        self.protocol.connectionLost(why)
        self.peer.connectionLost(why)

class RIMyTarget(pb.RemoteInterface):
    # method constraints can be declared directly:
    add1 = schema.RemoteMethodSchema(_response=int, a=int, b=int)

    # or through their function definitions:
    def add(a=int, b=int): return int
    #add = schema.callable(add) # the metaclass makes this unnecessary
    # but it could be used for adding options or something
    def join(a=str, b=str, c=int): return str
    def getName(): return str
    disputed = schema.RemoteMethodSchema(_response=int, a=int)

class RIMyTarget2(pb.RemoteInterface):
    __remote_name__ = "RIMyTargetInterface2"
    sub = schema.RemoteMethodSchema(_response=int, a=int, b=int)

# just like RIMyTarget except for the return value of the disputed method
class RIMyTarget3(RIMyTarget):
    disputed = schema.RemoteMethodSchema(_response=str, a=int)

class Target(pb.Referenceable):
    implements(RIMyTarget)

    def __init__(self, name=None):
        self.calls = []
        self.name = name
    def getMethodSchema(self, methodname):
        return None
    def remote_add(self, a, b):
        self.calls.append((a,b))
        return a+b
    def remote_getName(self):
        return self.name
    def remote_disputed(self, a):
        return 24
    def remote_fail(self):
        raise ValueError("you asked me to fail")

class TargetWithoutInterfaces(Target):
    # undeclare the RIMyTarget interface
    implementsOnly()

class BrokenTarget(pb.Referenceable):
    implements(RIMyTarget)

    def remote_add(self, a, b):
        return "error"

class IFoo(components.Interface):
    # non-remote Interface
    pass

class Target2(Target):
    implements(RIMyTarget, IFoo, RIMyTarget2)

class TargetMixin:

    def setupBrokers(self):
        self.targetBroker = pb.LoggingBroker()
        self.callingBroker = pb.LoggingBroker()
        self.targetTransport = Loopback()
        self.targetTransport.peer = self.callingBroker
        self.targetBroker.transport = self.targetTransport
        self.targetTransport.protocol = self.targetBroker
        self.callingTransport = Loopback()
        self.callingTransport.peer = self.targetBroker
        self.callingBroker.transport = self.callingTransport
        self.callingTransport.protocol = self.callingBroker
        self.targetBroker.connectionMade()
        self.callingBroker.connectionMade()

    def setupTarget(self, target):
        puid = target.processUniqueID()
        clid, firstTime = self.targetBroker.getCLID(puid, target)
        rr = self.callingBroker.registerRemoteReference(clid)
        return rr, target

    def setupTarget2(self, target):
        # with interfaces
        puid = target.processUniqueID()
        clid, firstTime = self.targetBroker.getCLID(puid, target)
        ilist = pb.getRemoteInterfaceNames(target)
        rr = self.callingBroker.registerRemoteReference(clid, ilist)
        return rr, target

    def setupTarget3(self, target, senderInterfaceNames):
        # with mismatched interfaces
        puid = target.processUniqueID()
        clid, firstTime = self.targetBroker.getCLID(puid, target)
        rRR = self.callingBroker.registerRemoteReference
        rr = rRR(clid, senderInterfaceNames)
        return rr, target


class TestInterface(unittest.TestCase, TargetMixin):

    def testTypes(self):
        self.failUnless(isinstance(RIMyTarget, flavors.RemoteInterfaceClass))
        self.failUnless(isinstance(RIMyTarget2, flavors.RemoteInterfaceClass))
        self.failUnless(isinstance(RIMyTarget3, flavors.RemoteInterfaceClass))

    def testRegister(self):
        reg = pb.RemoteInterfaceRegistry
        self.failUnlessEqual(reg["RIMyTarget"], RIMyTarget)
        self.failUnlessEqual(reg["RIMyTargetInterface2"], RIMyTarget2)

    def testDuplicateRegistry(self):
        try:
            class RIMyTarget(pb.RemoteInterface):
                def foo(bar=int): return int
        except flavors.DuplicateRemoteInterfaceError:
            pass
        else:
            self.fail("duplicate registration not caught")

    def testInterface1(self):
        # verify that we extract the right interfaces from a local object.
        # also check that the registry stuff works.
        self.setupBrokers()
        rr, target = self.setupTarget(Target())
        ilist = pb.getRemoteInterfaces(target)
        self.failUnlessEqual(ilist, [RIMyTarget])
        inames = pb.getRemoteInterfaceNames(target)
        self.failUnlessEqual(inames, ["RIMyTarget"])
        self.failUnlessIdentical(pb.RemoteInterfaceRegistry["RIMyTarget"],
                                 RIMyTarget)
        
        rr, target = self.setupTarget(Target2())
        ilist = pb.getRemoteInterfaceNames(target)
        self.failUnlessEqual(ilist, ["RIMyTarget",
                                     "RIMyTargetInterface2"])
        self.failUnlessIdentical(\
            pb.RemoteInterfaceRegistry["RIMyTargetInterface2"], RIMyTarget2)


    def testInterface2(self):
        # verify that a RemoteReferenceSchema created with a given set of
        # Interfaces behaves correctly
        t = Target()
        ilist = pb.getRemoteInterfaces(t)
        inames = pb.getRemoteInterfaceNames(t)
        s = t.getSchema()
        methods = s.getMethods()
        methods.sort()
        self.failUnlessEqual(methods,
                             ["add", "add1", "disputed", "getName", "join"])

        # 'add' is defined with 'def'
        s1 = s.getMethodSchema("add")
        self.failUnless(isinstance(s1, schema.RemoteMethodSchema))
        ok, s2 = s1.getArgConstraint("a")
        self.failUnless(ok)
        self.failUnless(isinstance(s2, schema.IntegerConstraint))
        self.failUnless(s2.checkObject(12) == None)
        self.failUnlessRaises(schema.Violation, s2.checkObject, "string")
        s3 = s1.getResponseConstraint()
        self.failUnless(isinstance(s3, schema.IntegerConstraint))

        # 'add1' is defined as a class attribute
        s1 = s.getMethodSchema("add1")
        self.failUnless(isinstance(s1, schema.RemoteMethodSchema))
        ok, s2 = s1.getArgConstraint("a")
        self.failUnless(ok)
        self.failUnless(isinstance(s2, schema.IntegerConstraint))
        self.failUnless(s2.checkObject(12) == None)
        self.failUnlessRaises(schema.Violation, s2.checkObject, "string")
        s3 = s1.getResponseConstraint()
        self.failUnless(isinstance(s3, schema.IntegerConstraint))

        s1 = s.getMethodSchema("join")
        self.failUnless(isinstance(s1.getArgConstraint("a")[1],
                                   schema.StringConstraint))
        self.failUnless(isinstance(s1.getArgConstraint("c")[1],
                                   schema.IntegerConstraint))
        s3 = s.getMethodSchema("join").getResponseConstraint()
        self.failUnless(isinstance(s3, schema.StringConstraint))

        s1 = s.getMethodSchema("disputed")
        self.failUnless(isinstance(s1.getArgConstraint("a")[1],
                                   schema.IntegerConstraint))
        s3 = s1.getResponseConstraint()
        self.failUnless(isinstance(s3, schema.IntegerConstraint))


    def testInterface3(self):
        t = TargetWithoutInterfaces()
        ilist = pb.getRemoteInterfaces(t)
        self.failIf(ilist)

class Unsendable:
    pass

class TestCall(unittest.TestCase, TargetMixin):
    def setUp(self):
        self.setupBrokers()

    def testCall1(self):
        # this is done without interfaces
        rr, target = self.setupTarget(TargetWithoutInterfaces())
        d = rr.callRemote("add", a=1, b=2)
        self.failUnlessEqual(target.calls, [(1,2)])
        r = unittest.deferredResult(d)
        self.failUnlessEqual(r, 3)

        # the caller still holds the RemoteReference
        self.failUnless(self.callingBroker.remoteReferences.has_key(1))

        # release the RemoteReference. This does two things: 1) the
        # callingBroker will forget about it. 2) they will send a decref to
        # the targetBroker so *they* can forget about it.
        del rr # this fires a DecRef
        gc.collect() # make sure

        self.failIf(self.callingBroker.remoteReferences.has_key(1))
        self.failIf(self.targetBroker.localObjects.has_key(1))

    def testFail1(self):
        # this is done without interfaces
        rr, target = self.setupTarget(TargetWithoutInterfaces())
        d = rr.callRemote("fail")
        self.failIf(target.calls)
        f = unittest.deferredError(d, 2)
        self.failUnless(isinstance(f, pb.CopiedFailure))
        self.failUnless(f.check(ValueError),
                        "wrong exception type: %s" % f)
        self.failUnless("you asked me to fail" in f.value)

    def testFail2(self):
        # this is done without interfaces
        rr, target = self.setupTarget(TargetWithoutInterfaces())
        d = rr.callRemote("add", a=1, b=2, c=3)
        # add() does not take a 'c' argument, so we get a TypeError here
        self.failIf(target.calls)
        f = unittest.deferredError(d, 2)
        self.failUnless(f.check(TypeError),
                        "wrong exception type: %s" % f.type)
        self.failUnless("remote_add() got an unexpected keyword argument 'c'"
                        in f.value)

    def testCall2(self):
        # use interfaces this time
        rr, target = self.setupTarget2(Target())
        d = rr.callRemote("add", 3, 4) # enforces schemas on both ends
        r = unittest.deferredResult(d, 2)
        self.failUnlessEqual(r, 7)

    def testFailLocalArgConstraint(self):
        # we violate the interface, and the sender should catch it
        rr, target = self.setupTarget2(Target())
        d = rr.callRemote("add", a=1, b=2, c=3)
        self.failIf(target.calls)
        f = unittest.deferredError(d, 2)
        self.failUnless(f.check(Violation))
        self.failUnless("unknown argument 'c'" in f.value)

    def testFailLocalArgConstraint2(self):
        # we violate the interface, and the sender should catch it
        rr, target = self.setupTarget2(Target())
        d = rr.callRemote("add", a=1, b="two")
        self.failIf(target.calls)
        f = unittest.deferredError(d, 2)
        self.failUnless(f.check(Violation))
        self.failUnless("not a number" in f.value)

    def testFailRemoteArgConstraint(self):
        # the brokers disagree about the Interfaces, so the sender thinks
        # they're ok but the recipient catches the violation
        rr, target = self.setupTarget3(Target(), ["RIMyTarget2"])
        d = rr.callRemote("sub", a=1, b=2)
        # RIMyTarget2 has a 'sub' method. But RIMyTarget (the real
        # interface) does not.
        self.failIf(target.calls)
        f = unittest.deferredError(d, 2)
        self.failUnless(f.check(Violation))
        self.failUnless("method 'sub' not defined in any RemoteInterface"
                        in f.value)

    def testFailRemoteReturnConstraint(self):
        rr, target = self.setupTarget2(BrokenTarget())
        d = rr.callRemote("add", 3, 4) # violates return constraint
        f = unittest.deferredError(d, 2)
        self.failUnless(f.check(Violation))
        self.failUnless("in outbound method results" in f.value)

    def testFailLocalReturnConstraint(self):
        rr, target = self.setupTarget3(Target(), ["RIMyTarget3"])
        d = rr.callRemote("disputed", a=1)
        # RIMyTarget.disputed returns an int, but the local side believes it
        # uses RIMyTarget3 which returns a string. This should be rejected
        # by the local side when the response comes back
        self.failIf(target.calls)
        f = unittest.deferredError(d, 2)
        self.failUnless(f.check(Violation))
        self.failUnless("INT token rejected by StringConstraint in inbound method results" in f.value)

    def defer(self, arg):
        rr, target = self.setupTarget(HelperTarget())
        d = rr.callRemote("defer", obj=arg)
        res = dr(d)
        return res

    def testDefer(self):
        res = self.defer(12)
        self.failUnlessEqual(res, 12)

    def testDisconnect1(self):
        rr, target = self.setupTarget(HelperTarget())
        d = rr.callRemote("hang")
        rr.broker.transport.loseConnection(RuntimeError("lost connection"))
        why = de(d)
        self.failUnless(why.check(RuntimeError))

    def disconnected(self):
        self.lost = 1

    def testDisconnect2(self):
        rr, target = self.setupTarget(HelperTarget())
        self.lost = 0
        rr.notifyOnDisconnect(self.disconnected)
        rr.broker.transport.loseConnection("lost")
        self.failUnless(self.lost)

    def testDisconnect3(self):
        rr, target = self.setupTarget(HelperTarget())
        self.lost = 0
        rr.notifyOnDisconnect(self.disconnected)
        rr.dontNotifyOnDisconnect(self.disconnected)
        rr.broker.transport.loseConnection("lost")
        self.failIf(self.lost)

    def testUnsendable(self):
        rr, target = self.setupTarget(HelperTarget())
        d = rr.callRemote("set", obj=Unsendable())
        why = de(d)
        self.failUnless(why.check(Violation))
        self.failUnless("cannot serialize" in why.value.args[0])



class MyCopyable1(pb.Copyable):
    # the getTypeToCopy name will be the fully-qualified class name, which
    # will depend upon how you first import this
    pass
class MyRemoteCopy1(pb.RemoteCopy):
    pass
#print "MyCopyable1:", reflect.qual(MyCopyable1)
pb.registerRemoteCopy(reflect.qual(MyCopyable1), MyRemoteCopy1)

class MyCopyable2(pb.Copyable):
    def getTypeToCopy(self):
        return "MyCopyable2name"
    def getStateToCopy(self):
        return {"a": 1, "b": self.b}
class MyRemoteCopy2(pb.RemoteCopy):
    def setCopyableState(self, state):
        self.c = 1
        self.d = state["b"]
pb.registerRemoteCopy("MyCopyable2name", MyRemoteCopy2)


class MyCopyable3(MyCopyable2):
    def getTypeToCopy(self):
        return "MyCopyable3name"
    def getAlternateCopyableState(self):
        return {"e": 2}

class MyCopyable3Slicer(flavors.CopyableSlicer):
    def slice(self, streamable, banana):
        yield 'copyable'
        yield self.obj.getTypeToCopy()
        state = self.obj.getAlternateCopyableState()
        for k,v in state.iteritems():
            yield k
            yield v

class MyRemoteCopy3(pb.RemoteCopy):
    pass
class MyRemoteCopy3Unslicer(flavors.RemoteCopyUnslicer):
    def __init__(self):
        self.factory = MyRemoteCopy3
        self.schema = None
    def receiveClose(self):
        obj = flavors.RemoteCopyUnslicer.receiveClose(self)
        obj.f = "yes"
        return obj

# register MyCopyable3Slicer as an ISlicer adapter for MyCopyable3, so we
# can verify that it overrides the inherited CopyableSlicer behavior. We
# also register an Unslicer to create the results.
components.registerAdapter(MyCopyable3Slicer, MyCopyable3, tokens.ISlicer)
pb.registerRemoteCopy("MyCopyable3name", MyRemoteCopy3Unslicer)

class RIHelper(pb.RemoteInterface):
    def set(obj=schema.Any()): return bool
    def get(): return schema.Any()
    def echo(obj=schema.Any()): return schema.Any()
    def defer(obj=schema.Any()): return schema.Any()
    def hang(): return schema.Any()

class HelperTarget(pb.Referenceable):
    implements(RIHelper)
    def remote_set(self, obj):
        self.obj = obj
        return True
    def remote_get(self):
        return self.obj
    def remote_echo(self, obj):
        self.obj = obj
        return obj
    def remote_defer(self, obj):
        d = defer.Deferred()
        reactor.callLater(1, d.callback, obj)
        return d
    def remote_hang(self):
        self.d = defer.Deferred()
        return self.d

class TestCopyable(unittest.TestCase, TargetMixin):

    def setUp(self):
        self.setupBrokers()
        if 0:
            print
            self.callingBroker.doLog = "TX"
            self.targetBroker.doLog = " rx"

    def send(self, arg):
        rr, target = self.setupTarget(HelperTarget())
        d = rr.callRemote("set", obj=arg)
        self.failUnless(dr(d))
        return target.obj

    def testCopy0(self):
        res = self.send(1)
        self.failUnlessEqual(res, 1)

    def testFailure1(self):
        self.callingBroker.unsafeTracebacks = True
        try:
            raise RuntimeError("message here")
        except:
            f0 = failure.Failure()
        f = self.send(f0)
        #print "CopiedFailure is:", f
        #print f.__dict__
        self.failUnlessEqual(f.type, "exceptions.RuntimeError")
        self.failUnlessEqual(f.value, "message here")
        self.failUnlessEqual(f.frames, [])
        self.failUnlessEqual(f.tb, None)
        self.failUnlessEqual(f.stack, [])
        # there should be a traceback
        self.failUnless(f.traceback.find("raise RuntimeError") != -1)

    def testFailure2(self):
        self.callingBroker.unsafeTracebacks = False
        try:
            raise RuntimeError("message here")
        except:
            f0 = failure.Failure()
        f = self.send(f0)
        #print "CopiedFailure is:", f
        #print f.__dict__
        self.failUnlessEqual(f.type, "exceptions.RuntimeError")
        self.failUnlessEqual(f.value, "message here")
        self.failUnlessEqual(f.frames, [])
        self.failUnlessEqual(f.tb, None)
        self.failUnlessEqual(f.stack, [])
        # there should not be a traceback
        self.failUnlessEqual(f.traceback, "Traceback unavailable\n")
        
    def testCopy1(self):
        obj = MyCopyable1() # just copies the dict
        obj.a = 12
        obj.b = "foo"
        res = self.send(obj)
        self.failUnless(isinstance(res, MyRemoteCopy1))
        self.failUnlessEqual(res.a, 12)
        self.failUnlessEqual(res.b, "foo")

    def testCopy2(self):
        obj = MyCopyable2() # has a custom getStateToCopy
        obj.a = 12 # ignored
        obj.b = "foo"
        res = self.send(obj)
        self.failUnless(isinstance(res, MyRemoteCopy2))
        self.failUnlessEqual(res.c, 1)
        self.failUnlessEqual(res.d, "foo")
        self.failIf(hasattr(res, "a"))

    def testCopy3(self):
        obj = MyCopyable3() # has a custom Slicer
        obj.a = 12 # ignored
        obj.b = "foo" # ignored
        res = self.send(obj)
        self.failUnless(isinstance(res, MyRemoteCopy3))
        self.failUnlessEqual(res.e, 2)
        self.failUnlessEqual(res.f, "yes")
        self.failIf(hasattr(res, "a"))


# test how a Referenceable gets transformed into a RemoteReference as it
# crosses the wire, then verify that it gets transformed back into the
# original Referenceable when it comes back


class TestReferenceable(unittest.TestCase, TargetMixin):

    def setUp(self):
        self.setupBrokers()
        if 0:
            print
            self.callingBroker.doLog = "TX"
            self.targetBroker.doLog = " rx"

    def send(self, arg):
        rr, target = self.setupTarget(HelperTarget())
        d = rr.callRemote("set", obj=arg)
        self.failUnless(dr(d))
        return target.obj

    def echo(self, arg):
        rr, target = self.setupTarget(HelperTarget())
        d = rr.callRemote("echo", obj=arg)
        res = dr(d)
        return res

    def testRef1(self):
        # Referenceables turn into RemoteReferences
        r = Target()
        res = self.send(r)
        self.failUnless(isinstance(res, pb.RemoteReference))
        self.failUnlessEqual(res.broker, self.targetBroker)
        self.failUnless(type(res.refID) is int)
        self.failUnless(self.callingBroker.getReferenceable(res.refID) is r)
        self.failUnlessEqual(res.interfaceNames, ['RIMyTarget'])

    def testRef2(self):
        # sending a Referenceable over the wire multiple times should result
        # in equivalent RemoteReferences
        r = Target()
        res1 = self.send(r)
        res2 = self.send(r)
        self.failUnless(res1 == res2)
        self.failUnless(res1 is res2) # newpb does this, oldpb didn't

    def testRef3(self):
        # those RemoteReferences can be used to invoke methods on the sender.
        # 'r' lives on side A. The anonymous target lives on side B. From
        # side A we invoke B.set(r), and we get the matching RemoteReference
        # 'rr' which lives on side B. Then we use 'rr' to invoke r.getName
        # from side A.
        r = Target()
        r.name = "ernie"
        rr = self.send(r)
        res = dr(rr.callRemote("getName"))
        self.failUnlessEqual(res, "ernie")

    def testRef4(self):
        # Referenceables survive round-trips
        r = Target()
        res = self.echo(r)
        self.failUnlessIdentical(res, r)

    def testRemoteRef1(self):
        # known URLRemoteReferences turn into Referenceables
        root = Target()
        rr, target = self.setupTarget(HelperTarget())
        self.targetBroker.factory = pb.PBServerFactory(root)
        urlRRef = self.callingBroker.remoteReferenceForName("", [])
        # urlRRef points at root
        d = rr.callRemote("set", obj=urlRRef)
        self.failUnless(dr(d))

        self.failUnlessIdentical(target.obj, root)

    def testRemoteRef2(self):
        # unknown URLRemoteReferences are errors
        root = Target()
        rr, target = self.setupTarget(HelperTarget())
        self.targetBroker.factory = pb.PBServerFactory(root)
        urlRRef = self.callingBroker.remoteReferenceForName("bogus", [])
        # urlRRef points at nothing
        d = rr.callRemote("set", obj=urlRRef)
        f = de(d)
        #print f
        #self.failUnlessEqual(f.type, tokens.Violation)
        self.failUnless(f.value.find("unknown clid 'bogus'") != -1)


class TestFactory(unittest.TestCase):

    def testGet1(self):
        t = Target()
        s = pb.PBServerFactory(t)
        port = reactor.listenTCP(0, s, interface="127.0.0.1")
        portnum = port.getHost().port
        d = pb.getRemoteURL_TCP("localhost", portnum, "", RIMyTarget)
        rr = dr(d)
        d = rr.callRemote("add", a=1, b=2)
        res = dr(d)
        self.failUnlessEqual(res, 3)

    def testGet2(self):
        # multiple RemoteInterfaces
        t = Target()
        s = pb.PBServerFactory(t)
        port = reactor.listenTCP(0, s, interface="127.0.0.1")
        portnum = port.getHost().port
        d = pb.getRemoteURL_TCP("localhost", portnum, "",
                                RIMyTarget, RIHelper)
        rr = dr(d)
        d = rr.callRemote("add", a=1, b=2)
        res = dr(d)
        self.failUnlessEqual(res, 3)

    def testCall1(self):
        # callRemoteURL
        t = Target()
        s = pb.PBServerFactory(t)
        port = reactor.listenTCP(0, s, interface="127.0.0.1")
        portnum = port.getHost().port
        d = pb.callRemoteURL_TCP("localhost", portnum, "",
                                 RIMyTarget, "add", a=1, b=2)
        res = dr(d)
        self.failUnlessEqual(res, 3)

    def testError(self):
        t = Target()
        s = pb.PBServerFactory(t)
        port = reactor.listenTCP(0, s, interface="127.0.0.1")
        portnum = port.getHost().port
        d = pb.callRemoteURL_TCP("localhost", portnum, "",
                                 RIMyTarget, "missing", a=1, b=2)
        f = de(d)
        # interesting. the Violation is local, so f.type is the actual
        # tokens.Violation class (rather than just a string). If the failure
        # is caught by the far side, I think we get a string. TODO: not sure
        # how I feel about that being different.
        self.failUnlessEqual(f.type, tokens.Violation)
        # likewise, f.value is a Violation instance, not a string 
        #self.failUnless(f.value.find("method 'missing' not defined") != -1)
        self.failUnless(f.value.args[0].find("method 'missing' not defined") != -1)

    def testCall2(self):
        t = Target("fred")
        t2 = Target2("gabriel")
        s = pb.PBServerFactory(t)
        s.registerReferenceable("two", t2)
        port = reactor.listenTCP(0, s, interface="127.0.0.1")
        portnum = port.getHost().port
        d = pb.callRemoteURL_TCP("localhost", portnum, "two",
                                 RIMyTarget, "getName")
        res = dr(d)
        self.failUnlessEqual(res, "gabriel")

class ThreeWayHelper:
    passed = False

    def start(self):
        d = pb.getRemoteURL_TCP("localhost", self.portnum1, "", RIHelper)
        d.addCallback(self.step2)
        d.addErrback(self.err)
        return d

    def step2(self, remote1):
        # .remote1 is our RRef to server1's "t1" HelperTarget
        self.remote1 = remote1
        d = pb.getRemoteURL_TCP("localhost", self.portnum2, "", RIHelper)
        d.addCallback(self.step3)
        return d

    def step3(self, remote2):
        # and .remote2 is our RRef to server2's "t2" helper target
        self.remote2 = remote2
        # sending a RemoteReference back to its source should be ok
        d = self.remote1.callRemote("set", self.remote1)
        d.addCallback(self.step4)
        return d

    def step4(self, res):
        assert self.target1.obj is self.target1
        # but sending one to someone else is not
        d = self.remote2.callRemote("set", self.remote1)
        d.addCallback(self.step5_callback)
        d.addErrback(self.step5_errback)
        return d

    def step5_callback(self, res):
        why = unittest.FailTest("sending a 3rd-party reference did not fail")
        self.err(failure.Failure(why))
        return None

    def step5_errback(self, why):
        bad = None
        if why.type != tokens.Violation:
            bad = "%s failure should be a Violation" % why.type
        elif why.value.args[0].find("RemoteReferences can only be sent back to their home Broker") == -1:
            bad = "wrong error message: '%s'" % why.value.args[0]
        if bad:
            why = unittest.FailTest(bad)
            self.passed = failure.Failure(why)
        else:
            self.passed = True

    def err(self, why):
        self.passed = why

class Test3Way(unittest.TestCase):
    def setUp(self):
        self.ports = []

    def tearDown(self):
        for p in self.ports:
            dr(p.stopListening())

    def test3Way(self):
        helper = ThreeWayHelper()

        t1 = HelperTarget()
        s1 = pb.PBServerFactory(t1)
        port1 = reactor.listenTCP(0, s1, interface="127.0.0.1")
        self.ports.append(port1)
        helper.portnum1 = port1.getHost().port
        helper.target1 = t1

        t2 = HelperTarget()
        s2 = pb.PBServerFactory(t2)
        port2 = reactor.listenTCP(0, s2, interface="127.0.0.1")
        self.ports.append(port2)
        helper.portnum2 = port2.getHost().port


        d = helper.start()
        res = dr(d)

        if helper.passed != True:
            # should be a Failure instance
            helper.passed.raiseException()

# TODO: tests to port from oldpb suite
# testTooManyRefs: sending pb.MAX_BROKER_REFS across the wire should die
# testFactoryCopy?

# tests which aren't relevant right now but which might be once we port the
# corresponding functionality:
#
# testObserve, testCache (pb.Cacheable)
# testViewPoint
# testPublishable (spread.publish??)
# SpreadUtilTestCase (spread.util)
# NewCredTestCase

# tests which aren't relevant and aren't like to ever be
#
# PagingTestCase
# ConnectionTestCase (oldcred)
# NSPTestCase
