#! /usr/bin/python

from twisted.trial import unittest
import schema, pb
from tokens import BananaError, Violation, INT, STRING, OPEN
from slicer import UnbananaFailure


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
        self.failUnlessRaises(BananaError, u.checkToken, STRING)
        u = self.newUnslicer()
        self.failUnlessRaises(BananaError, u.checkToken, OPEN)

    def testNoInterfaces(self):
        u = self.newUnslicer()
        u.checkToken(INT)
        u.receiveChild(12)
        self.failUnless(u.wantInterfaceList)
        rr1 = u.receiveClose()
        rr2 = self.broker.remoteReferences.get(12)
        self.failUnless(rr2)
        self.failUnless(isinstance(rr2, pb.RemoteReference))
        self.failUnlessEqual(rr2.broker, self.broker)
        self.failUnlessEqual(rr2.refID, 12)
        self.failUnlessEqual(rr2.interfaces, None)

    def testInterfaces(self):
        u = self.newUnslicer()
        u.checkToken(INT)
        u.receiveChild(12)
        self.failUnless(u.wantInterfaceList)
        u.checkToken(OPEN)
        # pretend we did a u.doOpen("list") here
        interfaces = [("IFoo", 1), ("IBar", 2)]
        u.receiveChild(interfaces)
        rr1 = u.receiveClose()
        rr2 = self.broker.remoteReferences.get(12)
        self.failUnless(rr2)
        self.failUnlessIdentical(rr1, rr2)
        self.failUnless(isinstance(rr2, pb.RemoteReference))
        self.failUnlessEqual(rr2.broker, self.broker)
        self.failUnlessEqual(rr2.refID, 12)
        self.failUnlessEqual(rr2.interfaces, interfaces)

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

    def testAccept1(self):
        req = pb.PendingRequest()
        self.broker.waitingForAnswers[12] = req
        u = self.newUnslicer()
        u.checkToken(INT)
        u.receiveChild(12) # causes broker.getRequest
        u.checkToken(STRING)
        u.receiveChild("results")
        self.failIf(self.broker.answers)
        u.receiveClose() # causes broker.gotAnswer
        self.failUnlessEqual(self.broker.answers, [(True, req, "results")])

    def testAccept2(self):
        req = pb.PendingRequest()
        req.setConstraint(schema.makeConstraint(str))
        self.broker.waitingForAnswers[12] = req
        u = self.newUnslicer()
        u.checkToken(INT)
        u.receiveChild(12) # causes broker.getRequest
        u.checkToken(STRING)
        u.receiveChild("results")
        self.failIf(self.broker.answers)
        u.receiveClose() # causes broker.gotAnswer
        self.failUnlessEqual(self.broker.answers, [(True, req, "results")])


    def testReject1(self):
        # answer a non-existent request
        req = pb.PendingRequest()
        self.broker.waitingForAnswers[12] = req
        u = self.newUnslicer()
        u.checkToken(INT)
        self.failUnlessRaises(BananaError, u.receiveChild, 13)

    def testReject2(self):
        # answer a request with a result that violates the constraint
        req = pb.PendingRequest()
        req.setConstraint(schema.makeConstraint(int))
        self.broker.waitingForAnswers[12] = req
        u = self.newUnslicer()
        u.checkToken(INT)
        u.receiveChild(12)
        self.failUnlessRaises(Violation, u.checkToken, STRING)
        # this will also errback the request
        self.failUnlessEqual(len(self.broker.answers), 1)
        err = self.broker.answers[0]
        self.failIf(err[0])
        self.failUnlessEqual(err[1], req)
        f = err[2]
        self.failUnless(f.check(Violation))

    def testReject3(self):
        # answer a request but explode before the CLOSE token is received
        req = pb.PendingRequest()
        self.broker.waitingForAnswers[12] = req
        u = self.newUnslicer()
        u.checkToken(INT)
        u.receiveChild(12)
        u.checkToken(STRING)
        u.receiveChild("results")
        self.failIf(self.broker.answers)
        u.receiveChild(UnbananaFailure()) # abandons unslicer, does errback

        self.failUnlessEqual(len(self.broker.answers), 1)
        err = self.broker.answers[0]
        self.failIf(err[0])
        self.failUnlessEqual(err[1], req)
        f = err[2]
        self.failUnless(isinstance(f,UnbananaFailure))
        # close would be ignored, but we had to bypass abandonUnslicer, so
        # that code path won't work
        #u.receiveClose() # should be ignored
        #self.failUnlessEqual(len(self.broker.answers), 1)

#from twisted.internet import interfaces
class Loopback:
#    __implements__ = interfaces.ITransport
    def write(self, data):
        self.peer.dataReceived(data)

class Target:
    def __init__(self):
        self.calls = []
    def getMethodSchema(self, methodname):
        return None
    def remote_add(self, a, b):
        self.calls.append((a,b))
        return a+b

class TestCall(unittest.TestCase):
    def setUp(self):
        self.targetBroker = pb.Broker()
        self.callingBroker = pb.Broker()
        self.targetTransport = Loopback()
        self.targetTransport.peer = self.callingBroker
        self.targetBroker.transport = self.targetTransport
        self.callingTransport = Loopback()
        self.callingTransport.peer = self.targetBroker
        self.callingBroker.transport = self.callingTransport

    def setupTarget(self):
        target = Target()
        objID = self.targetBroker.putObj(target)
        rr = self.callingBroker.registerRemoteReference(objID, None)
        return rr, target

    def testCall1(self):
        rr, target = self.setupTarget()
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
        import gc; gc.collect() # make sure

        self.failIf(self.callingBroker.remoteReferences.has_key(1))
        self.failIf(self.targetBroker.localObjects.has_key(1))
        
    def testFail1(self):
        rr, target = self.setupTarget()
        d = rr.callRemote("add", a=1, b=2, c=3)
        self.failIf(target.calls)
        f = unittest.deferredError(d)
        self.failUnless(str(f).find("remote_add() got an unexpected keyword argument 'c'") != -1)
        
