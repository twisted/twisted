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

def getRemoteInterfaceNames(obj):
    return [i.__remote_name__ for i in flavors.getRemoteInterfaces(obj)]

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

# For some tests, we want the two sides of the connection to disagree about
# the contents of the RemoteInterface they are using. This is remarkably
# difficult to accomplish within a single process. We do it by creating
# something that behaves just barely enough like a RemoteInterface to work.
class FakeTarget(dict):
    pass
RIMyTarget3 = FakeTarget()
RIMyTarget3.__remote_name__ = RIMyTarget.__remote_name__

RIMyTarget3['disputed'] = schema.RemoteMethodSchema(_response=int, a=str)
RIMyTarget3['disputed'].name = "disputed"
RIMyTarget3['disputed'].interface = RIMyTarget3

RIMyTarget3['disputed2'] = schema.RemoteMethodSchema(_response=str, a=int)
RIMyTarget3['disputed2'].name = "disputed"
RIMyTarget3['disputed2'].interface = RIMyTarget3

RIMyTarget3['sub'] = schema.RemoteMethodSchema(_response=int, a=int, b=int)
RIMyTarget3['sub'].name = "sub"
RIMyTarget3['sub'].interface = RIMyTarget3

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
    remote_add1 = remote_add
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

    def setupTarget(self, target, txInterfaces=False):
        # txInterfaces controls what interfaces the sender uses
        #  False: sender doesn't know about any interfaces
        #  True: sender gets the actual interface list from the target
        #  (list): sender uses an artificial interface list
        puid = target.processUniqueID()
        clid, firstTime = self.targetBroker.getCLID(puid, target)
        if txInterfaces is False:
            ilist = []
        elif txInterfaces is True:
            ilist = getRemoteInterfaceNames(target)
        else:
            ilist = txInterfaces
        rr = self.callingBroker.registerRemoteReference(clid, ilist)
        return rr, target


class TestInterface(unittest.TestCase, TargetMixin):

    def testTypes(self):
        self.failUnless(isinstance(RIMyTarget, flavors.RemoteInterfaceClass))
        self.failUnless(isinstance(RIMyTarget2, flavors.RemoteInterfaceClass))

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
        inames = getRemoteInterfaceNames(target)
        self.failUnlessEqual(inames, ["RIMyTarget"])
        self.failUnlessIdentical(pb.RemoteInterfaceRegistry["RIMyTarget"],
                                 RIMyTarget)
        
        rr, target = self.setupTarget(Target2())
        ilist = getRemoteInterfaceNames(target)
        self.failUnlessEqual(ilist, ["RIMyTarget",
                                     "RIMyTargetInterface2"])
        self.failUnlessIdentical(\
            pb.RemoteInterfaceRegistry["RIMyTargetInterface2"], RIMyTarget2)


    def testInterface2(self):
        # verify that RemoteInterfaces have the right attributes
        t = Target()
        ilist = pb.getRemoteInterfaces(t)
        self.failUnlessEqual(ilist, [RIMyTarget])

        # 'add' is defined with 'def'
        s1 = RIMyTarget['add']
        self.failUnless(isinstance(s1, schema.RemoteMethodSchema))
        ok, s2 = s1.getArgConstraint("a")
        self.failUnless(ok)
        self.failUnless(isinstance(s2, schema.IntegerConstraint))
        self.failUnless(s2.checkObject(12) == None)
        self.failUnlessRaises(schema.Violation, s2.checkObject, "string")
        s3 = s1.getResponseConstraint()
        self.failUnless(isinstance(s3, schema.IntegerConstraint))

        # 'add1' is defined as a class attribute
        s1 = RIMyTarget['add1']
        self.failUnless(isinstance(s1, schema.RemoteMethodSchema))
        ok, s2 = s1.getArgConstraint("a")
        self.failUnless(ok)
        self.failUnless(isinstance(s2, schema.IntegerConstraint))
        self.failUnless(s2.checkObject(12) == None)
        self.failUnlessRaises(schema.Violation, s2.checkObject, "string")
        s3 = s1.getResponseConstraint()
        self.failUnless(isinstance(s3, schema.IntegerConstraint))

        s1 = RIMyTarget['join']
        self.failUnless(isinstance(s1.getArgConstraint("a")[1],
                                   schema.StringConstraint))
        self.failUnless(isinstance(s1.getArgConstraint("c")[1],
                                   schema.IntegerConstraint))
        s3 = RIMyTarget['join'].getResponseConstraint()
        self.failUnless(isinstance(s3, schema.StringConstraint))

        s1 = RIMyTarget['disputed']
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
        r = dr(d)
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
        f = de(d, 2)
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
        f = de(d, 2)
        self.failUnless(f.check(TypeError),
                        "wrong exception type: %s" % f.type)
        self.failUnless("remote_add() got an unexpected keyword argument 'c'"
                        in f.value)

    def testFail3(self):
        # this is done without interfaces
        rr, target = self.setupTarget(TargetWithoutInterfaces())
        d = rr.callRemote("bogus", a=1, b=2)
        # the target does not have .bogus method, so we get an AttributeError
        self.failIf(target.calls)
        f = de(d, 2)
        self.failUnless(f.check(AttributeError),
                        "wrong exception type: %s" % f.type)
        self.failUnless("'TargetWithoutInterfaces' object has no " \
                        + "attribute 'remote_bogus'" in str(f))

    def testCall2(self):
        # server end uses an interface this time
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote("add", a=3, b=4) # enforces schemas on receipt
        r = dr(d, 2)
        self.failUnlessEqual(r, 7)

    def testCall3(self):
        # use interface on both sides
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote(RIMyTarget['add'], 3, 4) # enforces schemas
        r = dr(d, 2)
        self.failUnlessEqual(r, 7)

    def testCall4(self):
        # call through a manually-defined RemoteMethodSchema
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote(RIMyTarget['add1'], 3, 4)
        r = dr(d, 2)
        self.failUnlessEqual(r, 7)

    def testFailWrongInterfaceRemote(self):
        # we send a method in an interface that they don't support. This is
        # caught at the far end, because we don't have an interface list from
        # them.
        rr, target = self.setupTarget(Target())
        d = rr.callRemote(RIMyTarget2['sub'], 3, 4) # doesn't offer RIMyTarget2
        f = de(d)
        self.failUnless(f.check(Violation))
        self.failUnless("does not implement RIMyTargetInterface2" in str(f))

    def testFailWrongInterfaceLocal(self):
        # we send a method in an interface that we know they don't support
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote(RIMyTarget2['sub'], 3, 4) # doesn't offer RIMyTarget2
        f = de(d)
        self.failUnless(f.check(Violation))
        self.failUnless("does not offer RIMyTargetInterface2" in str(f))

    def testFailWrongMethodRemote(self):
        # if the target doesn't specify any remote interfaces, then the
        # calling side shouldn't try to do any checking. The problem is
        # caught on the target side.
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote("bogus") # RIMyTarget2 doesn't .bogus()
        f = de(d)
        self.failUnless(f.check(Violation))
        self.failUnless("method 'bogus' not defined in any of ['RIMyTarget']"
                        in str(f))

    def testFailWrongMethodRemote2(self):
        # call a method which doesn't actually exist. The sender thinks
        # they're ok but the recipient catches the violation
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote(RIMyTarget3['sub'], a=1, b=1)
        # RIMyTarget2 has a 'sub' method, but RIMyTarget (the real interface)
        # does not
        self.failIf(target.calls)
        f = de(d, 2)
        self.failUnless(f.check(Violation))
        self.failUnless("method 'sub' not defined in RIMyTarget" in f.value)

    def testFailWrongArgsLocal1(self):
        # we violate the interface (extra arg), and the sender should catch it
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote(RIMyTarget["add"], a=1, b=2, c=3)
        self.failIf(target.calls)
        f = de(d, 2)
        self.failUnless(f.check(Violation))
        self.failUnless("unknown argument 'c'" in f.value)

    def testFailWrongArgsLocal2(self):
        # we violate the interface (bad arg), and the sender should catch it
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote(RIMyTarget["add"], a=1, b="two")
        self.failIf(target.calls)
        f = de(d, 2)
        self.failUnless(f.check(Violation))
        self.failUnless("not a number" in f.value)

    def testFailWrongArgsRemote1(self):
        # the brokers disagree about the Interfaces, so the sender thinks
        # they're ok but the recipient catches the violation
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote(RIMyTarget3['disputed'], a="foo")
        # RIMyTarget3['disputed'] takes a string. But RIMyTarget (the real
        # interface) takes an int.
        self.failIf(target.calls)
        f = de(d, 2)
        self.failUnless(f.check(Violation))
        self.failUnless("STRING token rejected by IntegerConstraint"
                        in f.value)
        self.failUnless("at <RootUnslicer>.<methodcall .disputed arg[a]>"
                        in f.value)

    def testFailWrongReturnRemote(self):
        rr, target = self.setupTarget(BrokenTarget())
        d = rr.callRemote(RIMyTarget["add"], 3, 4) # violates return constraint
        f = de(d, 2)
        self.failUnless(f.check(Violation))
        self.failUnless("in outbound method results" in f.value)

    def testFailWrongReturnLocal1(self):
        # the target method returns a value which violates our schema
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote(RIMyTarget3['disputed2'], a=1)
        # RIMyTarget3['disputed2'] expects a string. The target returns an
        # int. RIMyTarget (the real interface) returns an int, so they think
        # they're ok.
        self.failIf(target.calls)
        f = de(d, 2)
        self.failUnless(f.check(Violation))
        self.failUnless("INT token rejected by StringConstraint" in str(f))
        self.failUnless("in inbound method results" in str(f))
        self.failUnless("at <RootUnslicer>.Answer(req=1)" in str(f))

    def testFailWrongReturnLocal2(self):
        # the target returns a value which violates our _resultConstraint
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote(RIMyTarget['disputed'], a=1,
                          _resultConstraint=str)
        # The target returns an int, which matches the schema they're using,
        # so they think they're ok. We've overridden our expectations to
        # require a string.
        self.failIf(target.calls)
        f = de(d, 2)
        self.failUnless(f.check(Violation))
        self.failUnless("INT token rejected by StringConstraint" in str(f))
        self.failUnless("in inbound method results" in str(f))
        self.failUnless("at <RootUnslicer>.Answer(req=1)" in str(f))



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
pb.registerRemoteCopy(reflect.qual(MyCopyable1), MyRemoteCopy1)

class MyCopyable2(pb.Copyable):
    def getTypeToCopy(self):
        return "MyCopyable2name"
    def getStateToCopy(self):
        return {"a": 1, "b": self.b}
class MyRemoteCopy2(pb.RemoteCopy):
    copytype = "MyCopyable2name"
    def setCopyableState(self, state):
        self.c = 1
        self.d = state["b"]


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

class MyCopyable4(pb.Copyable):
    pass
class MyRemoteCopy4(pb.RemoteCopy):
    copytype = reflect.qual(MyCopyable4)
    stateSchema = schema.AttributeDictConstraint(('foo', int),
                                                 ('bar', str))
    pass


class RIHelper(pb.RemoteInterface):
    def set(obj=schema.Any()): return bool
    def set2(obj1=schema.Any(), obj2=schema.Any()): return bool
    def get(): return schema.Any()
    def echo(obj=schema.Any()): return schema.Any()
    def defer(obj=schema.Any()): return schema.Any()
    def hang(): return schema.Any()

class HelperTarget(pb.Referenceable):
    implements(RIHelper)
    def remote_set(self, obj):
        self.obj = obj
        return True
    def remote_set2(self, obj1, obj2):
        self.obj1 = obj1
        self.obj2 = obj2
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

    def failToSend(self, arg):
        rr, target = self.setupTarget(HelperTarget())
        d = rr.callRemote("set", obj=arg)
        why = de(d)
        return why

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

    def testCopy4(self):
        obj = MyCopyable4()
        obj.foo = 12
        obj.bar = "bar"
        res = self.send(obj)
        self.failUnless(isinstance(res, MyRemoteCopy4))
        self.failUnlessEqual(res.foo, 12)
        self.failUnlessEqual(res.bar, "bar")

        obj.bad = "unwanted attribute"
        why = self.failToSend(obj)
        self.failUnless(why.check(Violation))
        self.failUnless("unknown attribute 'bad'" in str(why))
        del obj.bad

        obj.foo = "not a number"
        why = self.failToSend(obj)
        self.failUnless(why.check(Violation))
        self.failUnless("STRING token rejected by IntegerConstraint" \
                        in str(why))

        obj.foo = 12
        obj.bar = "very long " * 1000
        why = self.failToSend(obj)
        self.failUnless(why.check(Violation))
        self.failUnless("token too large" in str(why))


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

    def send2(self, arg1, arg2):
        rr, target = self.setupTarget(HelperTarget())
        d = rr.callRemote("set2", obj1=arg1, obj2=arg2)
        self.failUnless(dr(d))
        return (target.obj1, target.obj2)

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
        # sending the same Referenceable in multiple arguments should result
        # in equivalent RRs
        r = Target()
        res1, res2 = self.send2(r, r)
        self.failUnless(res1 == res2)
        self.failUnless(res1 is res2)

    def testRef4(self):
        # sending the same Referenceable in multiple calls will result in
        # equivalent RRs
        r = Target()
        rr, target = self.setupTarget(HelperTarget())
        dr(rr.callRemote("set", obj=r))
        res1 = target.obj
        dr(rr.callRemote("set", obj=r))
        res2 = target.obj
        self.failUnless(res1 == res2)
        self.failUnless(res1 is res2)

    def testRef5(self):
        # however that is not true for non-Referenceable objects. The
        # serialization scope is bounded by each method call
        r = [1,2]
        rr, target = self.setupTarget(HelperTarget())
        dr(rr.callRemote("set", obj=r))
        res1 = target.obj
        dr(rr.callRemote("set", obj=r))
        res2 = target.obj
        self.failUnless(res1 == res2)
        self.failIf(res1 is res2)

    def testRef6(self):
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

    def testRef7(self):
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
        self.failUnlessEqual(f.type, 'tokens.Violation')
        self.failUnless("method 'missing' not defined" in f.value)

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
        d = self.remote1.callRemote("set", obj=self.remote1)
        d.addCallback(self.step4)
        return d

    def step4(self, res):
        assert self.target1.obj is self.target1
        # but sending one to someone else is not
        d = self.remote2.callRemote("set", obj=self.remote1)
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

# TODO:
#  when the Violation is remote, it is reported in a CopiedFailure, which
#  means f.type is a string. When it is local, it is reported in a Failure,
#  and f.type is the tokens.Violation class. I'm not sure how I feel about
#  these being different.
#
#  make sure an actual exception in the remote method call is handled
#  properly (not just a Violation)

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
