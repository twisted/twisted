
import gc
import sys, re

from twisted.python import log
#log.startLogging(sys.stderr)

from zope.interface import implements, implementsOnly, implementedBy
from twisted.python import components, failure, reflect
from twisted.internet import reactor, defer
from twisted.trial import unittest
from twisted.internet.main import CONNECTION_LOST

from twisted.application.internet import TCPServer
from twisted.pb import schema, pb, tokens, remoteinterface, referenceable
from twisted.pb.tokens import BananaError, Violation, INT, STRING, OPEN
from twisted.pb.slicer import BananaFailure
from twisted.pb import copyable, broker, call
from twisted.pb.remoteinterface import getRemoteInterface
from twisted.pb.remoteinterface import RemoteInterfaceRegistry

try:
    from twisted.pb import crypto
except ImportError:
    crypto = None
if crypto and not crypto.available:
    crypto = None

from twisted.pb.test.common import HelperTarget, RIHelper, TargetMixin
from twisted.pb.test.common import getRemoteInterfaceName
from twisted.pb.negotiate import eventually, flushEventualQueue


class TestRequest(call.PendingRequest):
    def __init__(self, reqID, rref=None):
        self.answers = []
        call.PendingRequest.__init__(self, reqID, rref)
    def complete(self, res):
        self.answers.append((True, res))
    def fail(self, why):
        self.answers.append((False, why))

class TestReferenceUnslicer(unittest.TestCase):
    # OPEN(reference), INT(refid), [STR(interfacename), INT(version)]... CLOSE
    def setUp(self):
        self.broker = broker.Broker()

    def newUnslicer(self):
        unslicer = referenceable.ReferenceUnslicer()
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
        rr1,rr1d = u.receiveClose()
        self.failUnless(rr1d is None)
        rr2 = self.broker.getTrackerForYourReference(12).getRef()
        self.failUnless(rr2)
        self.failUnless(isinstance(rr2, referenceable.RemoteReference))
        self.failUnlessEqual(rr2.tracker.broker, self.broker)
        self.failUnlessEqual(rr2.tracker.clid, 12)
        self.failUnlessEqual(rr2.tracker.interfaceName, None)

    def testInterfaces(self):
        u = self.newUnslicer()
        u.checkToken(INT, 0)
        u.receiveChild(12)
        u.receiveChild("IBar")
        rr1,rr1d = u.receiveClose()
        self.failUnless(rr1d is None)
        rr2 = self.broker.getTrackerForYourReference(12).getRef()
        self.failUnless(rr2)
        self.failUnlessIdentical(rr1, rr2)
        self.failUnless(isinstance(rr2, referenceable.RemoteReference))
        self.failUnlessEqual(rr2.tracker.broker, self.broker)
        self.failUnlessEqual(rr2.tracker.clid, 12)
        self.failUnlessEqual(rr2.tracker.interfaceName, "IBar")

class TestAnswer(unittest.TestCase):
    # OPEN(answer), INT(reqID), [answer], CLOSE
    def setUp(self):
        self.broker = broker.Broker()

    def newUnslicer(self):
        unslicer = call.AnswerUnslicer()
        unslicer.broker = self.broker
        unslicer.opener = self.broker.rootUnslicer
        unslicer.protocol = self.broker
        return unslicer

    def makeRequest(self):
        req = call.PendingRequest(defer.Deferred())

    def testAccept1(self):
        req = TestRequest(12)
        self.broker.addRequest(req)
        u = self.newUnslicer()
        u.checkToken(INT, 0)
        u.receiveChild(12) # causes broker.getRequest
        u.checkToken(STRING, 8)
        u.receiveChild("results")
        self.failIf(req.answers)
        u.receiveClose() # causes broker.gotAnswer
        self.failUnlessEqual(req.answers, [(True, "results")])

    def testAccept2(self):
        req = TestRequest(12)
        req.setConstraint(schema.makeConstraint(str))
        self.broker.addRequest(req)
        u = self.newUnslicer()
        u.checkToken(INT, 0)
        u.receiveChild(12) # causes broker.getRequest
        u.checkToken(STRING, 15)
        u.receiveChild("results")
        self.failIf(req.answers)
        u.receiveClose() # causes broker.gotAnswer
        self.failUnlessEqual(req.answers, [(True, "results")])


    def testReject1(self):
        # answer a non-existent request
        req = TestRequest(12)
        self.broker.addRequest(req)
        u = self.newUnslicer()
        u.checkToken(INT, 0)
        self.failUnlessRaises(Violation, u.receiveChild, 13)

    def testReject2(self):
        # answer a request with a result that violates the constraint
        req = TestRequest(12)
        req.setConstraint(schema.makeConstraint(int))
        self.broker.addRequest(req)
        u = self.newUnslicer()
        u.checkToken(INT, 0)
        u.receiveChild(12)
        self.failUnlessRaises(Violation, u.checkToken, STRING, 42)
        # this does not yet errback the request
        self.failIf(req.answers)
        # it gets errbacked when banana reports the violation
        v = Violation("icky")
        v.setLocation("here")
        u.reportViolation(BananaFailure(v))
        self.failUnlessEqual(len(req.answers), 1)
        err = req.answers[0]
        self.failIf(err[0])
        f = err[1]
        self.failUnless(f.check(Violation))


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
    implementsOnly(implementedBy(pb.Referenceable))

class BrokenTarget(pb.Referenceable):
    implements(RIMyTarget)

    def remote_add(self, a, b):
        return "error"

class IFoo(components.Interface):
    # non-remote Interface
    pass

class Target2(Target):
    implementsOnly(IFoo, RIMyTarget2)


class TestInterface(TargetMixin, unittest.TestCase):

    def testTypes(self):
        self.failUnless(isinstance(RIMyTarget,
                                   remoteinterface.RemoteInterfaceClass))
        self.failUnless(isinstance(RIMyTarget2,
                                   remoteinterface.RemoteInterfaceClass))

    def testRegister(self):
        reg = RemoteInterfaceRegistry
        self.failUnlessEqual(reg["RIMyTarget"], RIMyTarget)
        self.failUnlessEqual(reg["RIMyTargetInterface2"], RIMyTarget2)

    def testDuplicateRegistry(self):
        try:
            class RIMyTarget(pb.RemoteInterface):
                def foo(bar=int): return int
        except remoteinterface.DuplicateRemoteInterfaceError:
            pass
        else:
            self.fail("duplicate registration not caught")

    def testInterface1(self):
        # verify that we extract the right interfaces from a local object.
        # also check that the registry stuff works.
        self.setupBrokers()
        rr, target = self.setupTarget(Target())
        iface = getRemoteInterface(target)
        self.failUnlessEqual(iface, RIMyTarget)
        iname = getRemoteInterfaceName(target)
        self.failUnlessEqual(iname, "RIMyTarget")
        self.failUnlessIdentical(RemoteInterfaceRegistry["RIMyTarget"],
                                 RIMyTarget)
        
        rr, target = self.setupTarget(Target2())
        iname = getRemoteInterfaceName(target)
        self.failUnlessEqual(iname, "RIMyTargetInterface2")
        self.failUnlessIdentical(\
            RemoteInterfaceRegistry["RIMyTargetInterface2"], RIMyTarget2)


    def testInterface2(self):
        # verify that RemoteInterfaces have the right attributes
        t = Target()
        iface = getRemoteInterface(t)
        self.failUnlessEqual(iface, RIMyTarget)

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
        iface = getRemoteInterface(t)
        self.failIf(iface)

class Unsendable:
    pass

class TestCall(TargetMixin, unittest.TestCase):
    def setUp(self):
        TargetMixin.setUp(self)
        self.setupBrokers()

    def testCall1(self):
        # this is done without interfaces
        rr, target = self.setupTarget(TargetWithoutInterfaces())
        d = rr.callRemote("add", a=1, b=2)
        d.addCallback(lambda res: self.failUnlessEqual(res, 3))
        d.addCallback(lambda res: self.failUnlessEqual(target.calls, [(1,2)]))
        d.addCallback(self._testCall1_1, rr)
        return d
    testCall1.timeout = 3
    def _testCall1_1(self, res, rr):
        # the caller still holds the RemoteReference
        self.failUnless(self.callingBroker.yourReferenceByCLID.has_key(1))

        # release the RemoteReference. This does two things: 1) the
        # callingBroker will forget about it. 2) they will send a decref to
        # the targetBroker so *they* can forget about it.
        del rr # this fires a DecRef
        gc.collect() # make sure
        # we need to give it a moment to deliver the DecRef message and act
        # on it
        d = defer.Deferred()
        reactor.callLater(0.1, d.callback, None)
        d.addCallback(self._testCall1_2)
        return d
    def _testCall1_2(self, res):
        self.failIf(self.callingBroker.yourReferenceByCLID.has_key(1))
        self.failIf(self.targetBroker.myReferenceByCLID.has_key(1))

    def testFail1(self):
        # this is done without interfaces
        rr, target = self.setupTarget(TargetWithoutInterfaces())
        d = rr.callRemote("fail")
        self.failIf(target.calls)
        d.addBoth(self._testFail1_1)
        return d
    testFail1.timeout = 2
    def _testFail1_1(self, f):
        # f should be a pb.CopiedFailure
        self.failUnless(isinstance(f, failure.Failure),
                        "Hey, we didn't fail: %s" % f)
        self.failUnless(f.check(ValueError),
                        "wrong exception type: %s" % f)
        self.failUnlessSubstring("you asked me to fail", f.value)

    def testFail2(self):
        # this is done without interfaces
        rr, target = self.setupTarget(TargetWithoutInterfaces())
        d = rr.callRemote("add", a=1, b=2, c=3)
        # add() does not take a 'c' argument, so we get a TypeError here
        self.failIf(target.calls)
        d.addBoth(self._testFail2_1)
        return d
    testFail2.timeout = 2
    def _testFail2_1(self, f):
        self.failUnless(isinstance(f, failure.Failure),
                        "Hey, we didn't fail: %s" % f)
        self.failUnless(f.check(TypeError),
                        "wrong exception type: %s" % f.type)
        self.failUnlessSubstring("remote_add() got an unexpected keyword "
                                 "argument 'c'", f.value)

    def testFail3(self):
        # this is done without interfaces
        rr, target = self.setupTarget(TargetWithoutInterfaces())
        d = rr.callRemote("bogus", a=1, b=2)
        # the target does not have .bogus method, so we get an AttributeError
        self.failIf(target.calls)
        d.addBoth(self._testFail3_1)
        return d
    testFail3.timeout = 2
    def _testFail3_1(self, f):
        self.failUnless(isinstance(f, failure.Failure),
                        "Hey, we didn't fail: %s" % f)
        self.failUnless(f.check(AttributeError),
                        "wrong exception type: %s" % f.type)
        self.failUnlessSubstring("TargetWithoutInterfaces", str(f))
        self.failUnlessSubstring(" has no attribute 'remote_bogus'", str(f))

    def testCall2(self):
        # server end uses an interface this time, but not the client end
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote("add", a=3, b=4, _useSchema=False)
        # the schema is enforced upon receipt
        d.addCallback(lambda res: self.failUnlessEqual(res, 7))
        return d
    testCall2.timeout = 2

    def testCall3(self):
        # use interface on both sides
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote('add', 3, 4) # enforces schemas
        d.addCallback(lambda res: self.failUnlessEqual(res, 7))
        return d
    testCall3.timeout = 2

    def testCall4(self):
        # call through a manually-defined RemoteMethodSchema
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote("add", 3, 4, _methodConstraint=RIMyTarget['add1'])
        d.addCallback(lambda res: self.failUnlessEqual(res, 7))
        return d
    testCall4.timeout = 2

    def testFailWrongMethodLocal(self):
        # the caller knows that this method does not really exist
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote("bogus") # RIMyTarget doesn't implement .bogus()
        d.addCallbacks(lambda res: self.fail("should have failed"),
                       self._testFailWrongMethodLocal_1)
        return d
    testFailWrongMethodLocal.timeout = 2
    def _testFailWrongMethodLocal_1(self, f):
        self.failUnless(f.check(Violation))
        self.failUnless(re.search(r'RIMyTarget\(.*\) does not offer bogus',
                                  str(f)))

    def testFailWrongMethodRemote(self):
        # if the target doesn't specify any remote interfaces, then the
        # calling side shouldn't try to do any checking. The problem is
        # caught on the target side.
        rr, target = self.setupTarget(Target(), False)
        d = rr.callRemote("bogus") # RIMyTarget doesn't implement .bogus()
        d.addCallbacks(lambda res: self.fail("should have failed"),
                       self._testFailWrongMethodRemote_1)
        return d
    testFailWrongMethodRemote.timeout = 2
    def _testFailWrongMethodRemote_1(self, f):
        self.failUnless(f.check(Violation))
        self.failUnlessSubstring("method 'bogus' not defined in RIMyTarget",
                                 str(f))

    def testFailWrongMethodRemote2(self):
        # call a method which doesn't actually exist. The sender thinks
        # they're ok but the recipient catches the violation
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote("bogus", _useSchema=False)
        # RIMyTarget2 has a 'sub' method, but RIMyTarget (the real interface)
        # does not
        d.addCallbacks(lambda res: self.fail("should have failed"),
                       self._testFailWrongMethodRemote2_1)
        d.addCallback(lambda res: self.failIf(target.calls))
        return d
    testFailWrongMethodRemote2.timeout = 2
    def _testFailWrongMethodRemote2_1(self, f):
        self.failUnless(f.check(Violation))
        self.failUnless(re.search(r'RIMyTarget\(.*\) does not offer bogus',
                                  str(f)))

    def testFailWrongArgsLocal1(self):
        # we violate the interface (extra arg), and the sender should catch it
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote("add", a=1, b=2, c=3)
        d.addCallbacks(lambda res: self.fail("should have failed"),
                       self._testFailWrongArgsLocal1_1)
        d.addCallback(lambda res: self.failIf(target.calls))
        return d
    testFailWrongArgsLocal1.timeout = 2
    def _testFailWrongArgsLocal1_1(self, f):
        self.failUnless(f.check(Violation))
        self.failUnlessSubstring("unknown argument 'c'", str(f.value))

    def testFailWrongArgsLocal2(self):
        # we violate the interface (bad arg), and the sender should catch it
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote("add", a=1, b="two")
        d.addCallbacks(lambda res: self.fail("should have failed"),
                       self._testFailWrongArgsLocal2_1)
        d.addCallback(lambda res: self.failIf(target.calls))
        return d
    testFailWrongArgsLocal2.timeout = 2
    def _testFailWrongArgsLocal2_1(self, f):
        self.failUnless(f.check(Violation))
        self.failUnlessSubstring("not a number", str(f.value))

    def testFailWrongArgsRemote1(self):
        # the sender thinks they're ok but the recipient catches the
        # violation
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote("add", a=1, b="foo", _useSchema=False)
        d.addCallbacks(lambda res: self.fail("should have failed"),
                       self._testFailWrongArgsRemote1_1)
        d.addCallbacks(lambda res: self.failIf(target.calls))
        return d
    testFailWrongArgsRemote1.timeout = 2
    def _testFailWrongArgsRemote1_1(self, f):
        self.failUnless(f.check(Violation))
        self.failUnlessSubstring("STRING token rejected by IntegerConstraint",
                                 f.value)
        self.failUnlessSubstring("at <RootUnslicer>.<methodcall .add arg[b]>",
                                 f.value)

    def testFailWrongReturnRemote(self):
        rr, target = self.setupTarget(BrokenTarget(), True)
        d = rr.callRemote("add", 3, 4) # violates return constraint
        d.addCallbacks(lambda res: self.fail("should have failed"),
                       self._testFailWrongReturnRemote_1)
        return d
    testFailWrongReturnRemote.timeout = 2
    def _testFailWrongReturnRemote_1(self, f):
        self.failUnless(f.check(Violation))
        self.failUnlessSubstring("in outbound method results", f.value)

    def testFailWrongReturnLocal(self):
        # the target returns a value which violates our _resultConstraint
        rr, target = self.setupTarget(Target(), True)
        d = rr.callRemote("add", a=1, b=2, _resultConstraint=str)
        # The target returns an int, which matches the schema they're using,
        # so they think they're ok. We've overridden our expectations to
        # require a string.
        d.addCallbacks(lambda res: self.fail("should have failed"),
                       self._testFailWrongReturnLocal_1)
        # the method should have been run
        d.addCallback(lambda res: self.failUnless(target.calls))
        return d
    testFailWrongReturnLocal.timeout = 2
    def _testFailWrongReturnLocal_1(self, f):
        self.failUnless(f.check(Violation))
        self.failUnlessSubstring("INT token rejected by StringConstraint",
                                 str(f))
        self.failUnlessSubstring("in inbound method results", str(f))
        self.failUnlessSubstring("at <RootUnslicer>.Answer(req=0)", str(f))



    def testDefer(self):
        rr, target = self.setupTarget(HelperTarget())
        d = rr.callRemote("defer", obj=12)
        d.addCallback(lambda res: self.failUnlessEqual(res, 12))
        return d
    testDefer.timeout = 2

    def testDisconnect1(self):
        rr, target = self.setupTarget(HelperTarget())
        d = rr.callRemote("hang")
        e = RuntimeError("lost connection")
        rr.tracker.broker.transport.loseConnection(e)
        d.addCallbacks(lambda res: self.fail("should have failed"),
                       lambda why: why.trap(RuntimeError) and None)
        return d
    testDisconnect1.timeout = 2

    def disconnected(self):
        self.lost = 1

    def testDisconnect2(self):
        rr, target = self.setupTarget(HelperTarget())
        self.lost = 0
        rr.notifyOnDisconnect(self.disconnected)
        rr.tracker.broker.transport.loseConnection(CONNECTION_LOST)
        d = eventually()
        d.addCallback(lambda res: self.failUnless(self.lost))
        return d

    def testDisconnect3(self):
        rr, target = self.setupTarget(HelperTarget())
        self.lost = 0
        rr.notifyOnDisconnect(self.disconnected)
        rr.dontNotifyOnDisconnect(self.disconnected)
        rr.tracker.broker.transport.loseConnection(CONNECTION_LOST)
        d = eventually()
        d.addCallback(lambda res: self.failIf(self.lost))
        return d

    def testUnsendable(self):
        rr, target = self.setupTarget(HelperTarget())
        d = rr.callRemote("set", obj=Unsendable())
        d.addCallbacks(lambda res: self.fail("should have failed"),
                       self._testUnsendable_1)
        return d
    testUnsendable.timeout = 2
    def _testUnsendable_1(self, why):
        self.failUnless(why.check(Violation))
        self.failUnlessSubstring("cannot serialize", why.value.args[0])


    


class TestReferenceable(TargetMixin, unittest.TestCase):
    # test how a Referenceable gets transformed into a RemoteReference as it
    # crosses the wire, then verify that it gets transformed back into the
    # original Referenceable when it comes back. Also test how shared
    # references to the same object are handled.

    def setUp(self):
        TargetMixin.setUp(self)
        self.setupBrokers()
        if 0:
            print
            self.callingBroker.doLog = "TX"
            self.targetBroker.doLog = " rx"

    def send(self, arg):
        rr, target = self.setupTarget(HelperTarget())
        d = rr.callRemote("set", obj=arg)
        d.addCallback(self.failUnless)
        d.addCallback(lambda res: target.obj)
        return d

    def send2(self, arg1, arg2):
        rr, target = self.setupTarget(HelperTarget())
        d = rr.callRemote("set2", obj1=arg1, obj2=arg2)
        d.addCallback(self.failUnless)
        d.addCallback(lambda res: (target.obj1, target.obj2))
        return d

    def echo(self, arg):
        rr, target = self.setupTarget(HelperTarget())
        d = rr.callRemote("echo", obj=arg)
        return d

    def testRef1(self):
        # Referenceables turn into RemoteReferences
        r = Target()
        d = self.send(r)
        d.addCallback(self._testRef1_1, r)
        return d
    def _testRef1_1(self, res, r):
        t = res.tracker
        self.failUnless(isinstance(res, referenceable.RemoteReference))
        self.failUnlessEqual(t.broker, self.targetBroker)
        self.failUnless(type(t.clid) is int)
        self.failUnless(self.callingBroker.getMyReferenceByCLID(t.clid) is r)
        self.failUnlessEqual(t.interfaceName, 'RIMyTarget')

    def testRef2(self):
        # sending a Referenceable over the wire multiple times should result
        # in equivalent RemoteReferences
        r = Target()
        d = self.send(r)
        d.addCallback(self._testRef2_1, r)
        return d
    def _testRef2_1(self, res1, r):
        d = self.send(r)
        d.addCallback(self._testRef2_2, res1)
        return d
    def _testRef2_2(self, res2, res1):
        self.failUnless(res1 == res2)
        self.failUnless(res1 is res2) # newpb does this, oldpb didn't

    def testRef3(self):
        # sending the same Referenceable in multiple arguments should result
        # in equivalent RRs
        r = Target()
        d = self.send2(r, r)
        d.addCallback(self._testRef3_1)
        return d
    def _testRef3_1(self, (res1, res2)):
        self.failUnless(res1 == res2)
        self.failUnless(res1 is res2)

    def testRef4(self):
        # sending the same Referenceable in multiple calls will result in
        # equivalent RRs
        r = Target()
        rr, target = self.setupTarget(HelperTarget())
        d = rr.callRemote("set", obj=r)
        d.addCallback(self._testRef4_1, rr, r, target)
        return d
    def _testRef4_1(self, res, rr, r, target):
        res1 = target.obj
        d = rr.callRemote("set", obj=r)
        d.addCallback(self._testRef4_2, target, res1)
        return d
    def _testRef4_2(self, res, target, res1):
        res2 = target.obj
        self.failUnless(res1 == res2)
        self.failUnless(res1 is res2)

    def testRef5(self):
        # those RemoteReferences can be used to invoke methods on the sender.
        # 'r' lives on side A. The anonymous target lives on side B. From
        # side A we invoke B.set(r), and we get the matching RemoteReference
        # 'rr' which lives on side B. Then we use 'rr' to invoke r.getName
        # from side A.
        r = Target()
        r.name = "ernie"
        d = self.send(r)
        d.addCallback(lambda rr: rr.callRemote("getName"))
        d.addCallback(self.failUnlessEqual, "ernie")
        return d

    def testRef6(self):
        # Referenceables survive round-trips
        r = Target()
        d = self.echo(r)
        d.addCallback(self.failUnlessIdentical, r)
        return d

    def NOTtestRemoteRef1(self):
        # known URLRemoteReferences turn into Referenceables
        root = Target()
        rr, target = self.setupTarget(HelperTarget())
        self.targetBroker.factory = pb.PBServerFactory(root)
        urlRRef = self.callingBroker.remoteReferenceForName("", [])
        # urlRRef points at root
        d = rr.callRemote("set", obj=urlRRef)
        self.failUnless(dr(d))

        self.failUnlessIdentical(target.obj, root)

    def NOTtestRemoteRef2(self):
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
        self.failUnlessEqual(type(f.value), str)
        self.failUnless(f.value.find("unknown clid 'bogus'") != -1)

    def testArgs1(self):
        # sending the same non-Referenceable object in multiple calls results
        # in distinct objects, because the serialization scope is bounded by
        # each method call
        r = [1,2]
        rr, target = self.setupTarget(HelperTarget())
        d = rr.callRemote("set", obj=r)
        d.addCallback(self._testArgs1_1, rr, r, target)
        # TODO: also make sure the original list goes out of scope once the
        # method call has finished, to guard against a leaky
        # reference-tracking implementation.
        return d
    def _testArgs1_1(self, res, rr, r, target):
        res1 = target.obj
        d = rr.callRemote("set", obj=r)
        d.addCallback(self._testArgs1_2, target, res1)
        return d
    def _testArgs1_2(self, res, target, res1):
        res2 = target.obj
        self.failUnless(res1 == res2)
        self.failIf(res1 is res2)

    def testArgs2(self):
        # but sending them as multiple arguments of the *same* method call
        # results in identical objects
        r = [1,2]
        rr, target = self.setupTarget(HelperTarget())
        d = rr.callRemote("set2", obj1=r, obj2=r)
        d.addCallback(self._testArgs2_1, rr, target)
        return d
    def _testArgs2_1(self, res, rr, target):
        self.failUnlessIdentical(target.obj1, target.obj2)

    def testAnswer1(self):
        # also, shared objects in a return value should be shared
        r = [1,2]
        rr, target = self.setupTarget(HelperTarget())
        target.obj = (r,r)
        d = rr.callRemote("get")
        d.addCallback(lambda res: self.failUnlessIdentical(res[0], res[1]))
        return d

    def testAnswer2(self):
        # but objects returned by separate method calls should be distinct
        rr, target = self.setupTarget(HelperTarget())
        r = [1,2]
        target.obj = r
        d = rr.callRemote("get")
        d.addCallback(self._testAnswer2_1, rr, target)
        return d
    def _testAnswer2_1(self, res1, rr, target):
        d = rr.callRemote("get")
        d.addCallback(self._testAnswer2_2, res1)
        return d
    def _testAnswer2_2(self, res2, res1):
        self.failUnless(res1 == res2)
        self.failIf(res1 is res2)


class TestFactory(unittest.TestCase):
    def setUp(self):
        self.client = None
        self.server = None

    def gotReference(self, ref):
        self.client = ref

    def tearDown(self):
        if self.client:
            self.client.broker.transport.loseConnection()
        if self.server:
            return self.server.stopListening()

class TestCallable(unittest.TestCase):
    def setUp(self):
        self.services = [pb.PBService(), pb.PBService()]
        self.tubA, self.tubB = self.services
        for s in self.services:
            s.startService()
            l = s.listenOn("tcp:0:interface=127.0.0.1")
            s.setLocation("localhost:%d" % l.getPortnum())

    def tearDown(self):
        return defer.DeferredList([s.stopService() for s in self.services])

    def testBoundMethod(self):
        target = Target()
        meth_url = self.tubB.registerReference(target.remote_add)
        d = self.tubA.getReference(meth_url)
        d.addCallback(self._testBoundMethod_1)
        return d
    testBoundMethod.timeout = 5
    def _testBoundMethod_1(self, ref):
        self.failUnless(isinstance(ref, referenceable.RemoteMethodReference))
        #self.failUnlessEqual(ref.getSchemaName(),
        #                     RIMyTarget.__remote_name__ + "/remote_add")
        d = ref.callRemote(a=1, b=2)
        d.addCallback(lambda res: self.failUnlessEqual(res, 3))
        return d

    def testFunction(self):
        l = []
        # we need a keyword arg here
        def append(what):
            l.append(what)
        func_url = self.tubB.registerReference(append)
        d = self.tubA.getReference(func_url)
        d.addCallback(self._testFunction_1, l)
        return d
    testFunction.timeout = 5
    def _testFunction_1(self, ref, l):
        self.failUnless(isinstance(ref, referenceable.RemoteMethodReference))
        d = ref.callRemote(what=12)
        d.addCallback(lambda res: self.failUnlessEqual(l, [12]))
        return d


class TestService(unittest.TestCase):
    def setUp(self):
        self.services = [pb.PBService()]
        self.services[0].startService()

    def tearDown(self):
        return defer.DeferredList([s.stopService() for s in self.services])

    def testRegister(self):
        s = self.services[0]
        l = s.listenOn("tcp:0:interface=127.0.0.1")
        s.setLocation("localhost:%d" % l.getPortnum())
        t1 = Target()
        public_url = s.registerReference(t1, "target")
        if crypto:
            self.failUnless(public_url.startswith("pb://"))
            self.failUnless(public_url.endswith("@localhost:%d/target"
                                                % l.getPortnum()))
        else:
            self.failUnlessEqual(public_url,
                                 "pbu://localhost:%d/target"
                                 % l.getPortnum())
        self.failUnlessEqual(s.registerReference(t1, "target"), public_url)
        self.failUnlessIdentical(s.getReferenceForURL(public_url), t1)
        t2 = Target()
        private_url = s.registerReference(t2)
        self.failUnlessEqual(s.registerReference(t2), private_url)
        self.failUnlessIdentical(s.getReferenceForURL(private_url), t2)

        s.unregisterURL(public_url)
        self.failUnlessRaises(KeyError, s.getReferenceForURL, public_url)

        s.unregisterReference(t2)
        self.failUnlessRaises(KeyError, s.getReferenceForURL, private_url)

        # TODO: check what happens when you register the same referenceable
        # under multiple URLs

    def getRef(self, target):
        self.services.append(pb.PBService())
        s1 = self.services[0]
        s2 = self.services[1]
        s2.startService()
        l = s1.listenOn("tcp:0:interface=127.0.0.1")
        s1.setLocation("localhost:%d" % l.getPortnum())
        public_url = s1.registerReference(target, "target")
        d = s2.getReference(public_url)
        return d

    def testConnect1(self):
        t1 = TargetWithoutInterfaces()
        d = self.getRef(t1)
        d.addCallback(lambda ref: ref.callRemote('add', a=2, b=3))
        d.addCallback(self._testConnect1, t1)
        return d
    testConnect1.timeout = 5
    def _testConnect1(self, res, t1):
        self.failUnlessEqual(t1.calls, [(2,3)])
        self.failUnlessEqual(res, 5)

    def testConnect2(self):
        t1 = Target()
        d = self.getRef(t1)
        d.addCallback(lambda ref: ref.callRemote('add', a=2, b=3))
        d.addCallback(self._testConnect2, t1)
        return d
    testConnect2.timeout = 5
    def _testConnect2(self, res, t1):
        self.failUnlessEqual(t1.calls, [(2,3)])
        self.failUnlessEqual(res, 5)


    def testConnect3(self):
        t1 = Target()
        d = self.getRef(t1)
        d.addCallback(lambda ref: ref.callRemote('add', a=2, b=3))
        d.addCallback(self._testConnect3, t1)
        return d
    testConnect3.timeout = 5
    def _testConnect3(self, res, t1):
        self.failUnlessEqual(t1.calls, [(2,3)])
        self.failUnlessEqual(res, 5)

    def testStatic(self):
        # make sure we can register static data too, at least hashable ones
        t1 = (1,2,3)
        d = self.getRef(t1)
        d.addCallback(lambda ref: self.failUnlessEqual(ref, (1,2,3)))
        return d
    testStatic.timeout = 2

    def testBadMethod(self):
        t1 = Target()
        d = self.getRef(t1)
        d.addCallback(lambda ref: ref.callRemote('missing', a=2, b=3))
        d.addCallbacks(self._testBadMethod_cb, self._testBadMethod_eb)
        return d
    testBadMethod.timeout = 5
    def _testBadMethod_cb(self, res):
        self.fail("method wasn't supposed to work")
    def _testBadMethod_eb(self, f):
        #self.failUnlessEqual(f.type, 'twisted.pb.tokens.Violation')
        self.failUnlessEqual(f.type, Violation)
        self.failUnless(re.search(r'RIMyTarget\(.*\) does not offer missing',
                                  str(f)))

    def testBadMethod2(self):
        t1 = TargetWithoutInterfaces()
        d = self.getRef(t1)
        d.addCallback(lambda ref: ref.callRemote('missing', a=2, b=3))
        d.addCallbacks(self._testBadMethod_cb, self._testBadMethod2_eb)
        return d
    testBadMethod2.timeout = 5
    def _testBadMethod2_eb(self, f):
        self.failUnlessEqual(f.type, 'exceptions.AttributeError')
        self.failUnlessSubstring("TargetWithoutInterfaces", f.value)
        self.failUnlessSubstring(" has no attribute 'remote_missing'", f.value)


class ThreeWayHelper:
    passed = False

    def start(self):
        d = pb.getRemoteURL_TCP("localhost", self.portnum1, "", RIHelper)
        d.addCallback(self.step2)
        d.addErrback(self.err)
        return d

    def step2(self, remote1):
        # .remote1 is our RRef to server1's "t1" HelperTarget
        self.clients.append(remote1)
        self.remote1 = remote1
        d = pb.getRemoteURL_TCP("localhost", self.portnum2, "", RIHelper)
        d.addCallback(self.step3)
        return d

    def step3(self, remote2):
        # and .remote2 is our RRef to server2's "t2" helper target
        self.clients.append(remote2)
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
    # Here we test the three-party introduction process as depicted in the
    # classic Granovetter diagram. Alice has a reference to Bob and another
    # one to Carol. Alice wants to give her Carol-reference to Bob, by
    # including it as the argument to a method she invokes on her
    # Bob-reference.

    def setUp(self):
        self.services = [pb.PBService(), pb.PBService(), pb.PBService()]
        self.tubA, self.tubB, self.tubC = self.services
        for s in self.services:
            s.startService()
            l = s.listenOn("tcp:0:interface=127.0.0.1")
            s.setLocation("localhost:%d" % l.getPortnum())

    def tearDown(self):
        return defer.DeferredList([s.stopService() for s in self.services])

    def testGift(self):
        # we must start by giving Alice a reference to both Bob and Carol.

        self.bob = HelperTarget("bob")
        self.bob_url = self.tubB.registerReference(self.bob)
        self.carol = HelperTarget("carol")
        self.carol_url = self.tubC.registerReference(self.carol)

        # now, from Alice's point of view:
        d = self.tubA.getReference(self.bob_url)
        d.addCallback(self._aliceGotBob)
        return d
    testGift.timeout = 2

    def _aliceGotBob(self, abob):
        self.abob = abob # Alice's reference to Bob
        d = self.tubA.getReference(self.carol_url)
        d.addCallback(self._aliceGotCarol)
        return d

    def _aliceGotCarol(self, acarol):
        self.acarol = acarol # Alice's reference to Carol
        d2 = self.bob.waitfor()
        d = self.abob.callRemote("set", obj=self.acarol) # send the gift
        # TODO: at this point, 'del self.acarol' should not lose alice's
        # reference to carol, because it will still be in the gift table. The
        # trick is how to test that, we would need a way to stall the gift
        # delivery while we verify everything
        d.addCallback(lambda res: d2)
        d.addCallback(self._bobGotCarol)
        return d

    def _bobGotCarol(self, bcarol):
        # Bob has received the gift
        self.bcarol = bcarol
        #  alice's gift table should be empty
        brokerAB = self.abob.tracker.broker
        self.failIf(brokerAB.myGifts)
        self.failIf(brokerAB.myGiftsByGiftID)

        d2 = self.carol.waitfor()
        d = self.bcarol.callRemote("set", obj=12)
        d.addCallback(lambda res: d2)
        d.addCallback(self._carolCalled)
        return d

    def _carolCalled(self, res):
        self.failUnlessEqual(res, 12)


# TODO:
#  when the Violation is remote, it is reported in a CopiedFailure, which
#  means f.type is a string. When it is local, it is reported in a Failure,
#  and f.type is the tokens.Violation class. I'm not sure how I feel about
#  these being different.

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
