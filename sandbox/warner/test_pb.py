#! /usr/bin/python

import gc

from twisted.python import components
from twisted.trial import unittest

import schema, pb
from tokens import BananaError, Violation, INT, STRING, OPEN
from slicer import UnbananaFailure

from twisted.python import log
import sys
#log.startLogging(sys.stderr)

class TestBroker(pb.Broker):
    def gotAnswer(self, req, results):
        self.answers.append((True, req, results))
    def gotError(self, req, f):
        self.answers.append((False, req, f))
    def abandonUnslicer(self, failure, leaf=None):
        pass
    def freeRemoteReference(self, refID):
        pass

class TestReferenceUnslicer(unittest.TestCase):
    # OPEN(reference), INT(refid), [STR(interfacename), INT(version)]... CLOSE
    def setUp(self):
        self.broker = TestBroker()

    def newUnslicer(self):
        unslicer = pb.ReferenceUnslicer()
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
        self.failUnless(u.wantInterfaceList)
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
        self.failUnless(u.wantInterfaceList)
        u.checkToken(OPEN, 9999)
        # pretend we did a u.doOpen("list") here
        interfaceNames = ["IFoo", "IBar"]
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
        req = pb.PendingRequest()
        self.broker.waitingForAnswers[12] = req
        u = self.newUnslicer()
        u.checkToken(INT, 0)
        u.receiveChild(12) # causes broker.getRequest
        u.checkToken(STRING, 8)
        u.receiveChild("results")
        self.failIf(self.broker.answers)
        u.receiveClose() # causes broker.gotAnswer
        self.failUnlessEqual(self.broker.answers, [(True, req, "results")])

    def testAccept2(self):
        req = pb.PendingRequest()
        req.setConstraint(schema.makeConstraint(str))
        self.broker.waitingForAnswers[12] = req
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
        req = pb.PendingRequest()
        self.broker.waitingForAnswers[12] = req
        u = self.newUnslicer()
        u.checkToken(INT, 0)
        self.failUnlessRaises(BananaError, u.receiveChild, 13)

    def testReject2(self):
        # answer a request with a result that violates the constraint
        req = pb.PendingRequest()
        req.setConstraint(schema.makeConstraint(int))
        self.broker.waitingForAnswers[12] = req
        u = self.newUnslicer()
        u.checkToken(INT, 0)
        u.receiveChild(12)
        self.failUnlessRaises(Violation, u.checkToken, STRING, 42)
        # this does not yet errback the request
        self.failIf(self.broker.answers)
        # it gets errbacked when banana reports the violation
        u.reportViolation(UnbananaFailure(Violation("icky"), "here"))
        self.failUnlessEqual(len(self.broker.answers), 1)
        err = self.broker.answers[0]
        self.failIf(err[0])
        self.failUnlessEqual(err[1], req)
        f = err[2]
        self.failUnless(f.check(Violation))

#from twisted.internet import interfaces
class Loopback:
#    __implements__ = interfaces.ITransport
    def write(self, data):
        self.peer.dataReceived(data)

class IMyTarget(pb.IRemoteInterface):
    # method constraints can be declared directly:
    add1 = schema.RemoteMethodSchema(_response=int, a=int, b=int)

    # or through their function definitions:
    def add(self, a=int, b=int): return int
    #add = schema.callable(add) # the metaclass makes this unnecessary
    # but it could be used for adding options or something
    def join(self, a=str, b=str, c=int): return str
    disputed = schema.RemoteMethodSchema(_response=int, a=int)

pb.registerRemoteInterface(IMyTarget)

class IMyTarget2(pb.IRemoteInterface):
    __remote_name__ = "IMyTargetInterface2"
    sub = schema.RemoteMethodSchema(_response=int, a=int, b=int)

pb.registerRemoteInterface(IMyTarget2)

# just like IMyTarget except for the return value of the disputed method
class IMyTarget3(IMyTarget):
    disputed = schema.RemoteMethodSchema(_response=str, a=int)
pb.registerRemoteInterface(IMyTarget3)

class Target(pb.Referenceable):
    __implements__ = (IMyTarget,)
    def __init__(self):
        self.calls = []
    def getMethodSchema(self, methodname):
        return None
    def remote_add(self, a, b):
        self.calls.append((a,b))
        return a+b
    def remote_disputed(self, a):
        return 24

class TargetWithoutInterfaces(Target):
    # twisted-1.3.0 has a bug which hits when __implements__ is empty. This
    # is a workaround.
    __implements__ = components.Interface,

class BrokenTarget(pb.Referenceable):
    __implements__ = (IMyTarget,)
    def remote_add(self, a, b):
        return "error"

class IFoo(components.Interface):
    pass

class Target2(Target):
    __implements__ = (IMyTarget, IFoo, IMyTarget2)

class TargetMixin:

    def setupBrokers(self):
        self.targetBroker = pb.Broker()
        self.callingBroker = pb.Broker()
        self.targetTransport = Loopback()
        self.targetTransport.peer = self.callingBroker
        self.targetBroker.transport = self.targetTransport
        self.callingTransport = Loopback()
        self.callingTransport.peer = self.targetBroker
        self.callingBroker.transport = self.callingTransport

    def setupTarget(self, target):
        objID = self.targetBroker.putObj(target)
        rr = self.callingBroker.registerRemoteReference(objID)
        return rr, target

    def setupTarget2(self, target):
        # with interfaces
        objID = self.targetBroker.putObj(target)
        ilist = pb.getRemoteInterfaceNames(target)
        rr = self.callingBroker.registerRemoteReference(objID, ilist)
        return rr, target

    def setupTarget3(self, target, senderInterfaceNames):
        # with mismatched interfaces
        objID = self.targetBroker.putObj(target)
        f = self.callingBroker.registerRemoteReference
        rr = f(objID, senderInterfaceNames)
        return rr, target


class TestInterface(unittest.TestCase, TargetMixin):

    def testInterface1(self):
        # verify that we extract the right interfaces from a local object.
        # also check that the registry stuff works.
        self.setupBrokers()
        rr, target = self.setupTarget(Target())
        ilist = pb.getRemoteInterfaces(target)
        self.failUnlessEqual(ilist, [IMyTarget, pb.IRemoteInterface])
        inames = pb.getRemoteInterfaceNames(target)
        self.failUnlessEqual(inames, ["IMyTarget", "IRemoteInterface"])
        self.failUnlessIdentical(pb.remoteInterfaceRegistry["IMyTarget"],
                                 IMyTarget)
        
        rr, target = self.setupTarget(Target2())
        ilist = pb.getRemoteInterfaceNames(target)
        self.failUnlessEqual(ilist, ["IMyTarget",
                                     "IMyTargetInterface2",
                                     "IRemoteInterface"])
        self.failUnlessIdentical(\
            pb.remoteInterfaceRegistry["IMyTargetInterface2"], IMyTarget2)


    def testInterface2(self):
        # verify that a RemoteReferenceSchema created with a given set of
        # Interfaces behaves correctly
        t = Target()
        ilist = pb.getRemoteInterfaces(t)
        inames = pb.getRemoteInterfaceNames(t)
        s = t.getSchema()
        methods = s.getMethods()
        methods.sort()
        self.failUnlessEqual(methods, ["add", "add1", "disputed", "join"])

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
        d = rr.callRemote("add", a=1, b=2, c=3)
        # add() does not take a 'c' argument, so we get a TypeError here
        self.failIf(target.calls)
        f = unittest.deferredError(d, 2)
        # TODO: once CopyableFailure is done, this comparison should be
        # less stringish
        self.failUnless(str(f).find("remote_add() got an unexpected keyword argument 'c'") != -1)

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
        self.failUnless(str(f).find("Violation, unknown argument 'c'") != -1)

    def testFailRemoteArgConstraint(self):
        # the brokers disagree about the Interfaces, so the sender thinks
        # they're ok but the recipient catches the violation
        rr, target = self.setupTarget3(Target(), ["IMyTarget2"])
        d = rr.callRemote("sub", a=1, b=2)
        # IMyTarget2 has a 'sub' method. But IMyTarget (the real interface)
        # does not.
        self.failIf(target.calls)
        f = unittest.deferredError(d, 2)
        self.failUnless(str(f).find("Violation, method 'sub' not defined in any RemoteInterface") != -1)

    def testFailRemoteReturnConstraint(self):
        rr, target = self.setupTarget2(BrokenTarget())
        d = rr.callRemote("add", 3, 4) # violates return constraint
        f = unittest.deferredError(d, 2)
        self.failUnless(str(f).find("Violation, in outbound method results") != -1)

    def testFailLocalReturnConstraint(self):
        rr, target = self.setupTarget3(Target(), ["IMyTarget3"])
        d = rr.callRemote("disputed", a=1)
        # IMyTarget.disputed returns an int, but the local side believes it
        # uses IMyTarget3 which returns a string. This should be rejected by
        # the local side when the response comes back
        self.failIf(target.calls)
        f = unittest.deferredError(d, 2)
        self.failUnless(str(f).find("Violation, INT token rejected by StringConstraint in inbound method results") != -1)


# test how a Referenceable gets transformed into a RemoteReference as it
# crosses the wire, then verify that it gets transformed back into the
# original Referenceable when it comes back

