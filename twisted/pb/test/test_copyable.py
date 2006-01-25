
from twisted.trial import unittest
from twisted.python import reflect, components, failure
from twisted.pb.test.common import TargetMixin, HelperTarget

from twisted.pb import pb, copyable, tokens, schema
from twisted.pb.tokens import Violation

# MyCopyable1 is the basic pb.Copyable/pb.RemoteCopy pair. This one does not
# use auto-registration. (well, it does, but the pb.RemoteCopy's name is
# different, so the auto-registration is useless, so we explicitly register
# the correct name)

class MyCopyable1(pb.Copyable):
    # the getTypeToCopy name will be the fully-qualified class name, which
    # will depend upon how you first import this
    pass
class MyRemoteCopy1(pb.RemoteCopy):
    pass
pb.registerRemoteCopy(reflect.qual(MyCopyable1), MyRemoteCopy1)

# MyCopyable2 overrides the various pb.Copyable/pb.RemoteCopy methods. It
# also sets 'copytype' to auto-register with a matching name

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

# MyCopyable3 uses a custom Slicer and a custom Unslicer

class MyCopyable3(MyCopyable2):
    def getTypeToCopy(self):
        return "MyCopyable3name"
    def getAlternateCopyableState(self):
        return {"e": 2}

class MyCopyable3Slicer(copyable.CopyableSlicer):
    def slice(self, streamable, banana):
        yield 'copyable'
        yield self.obj.getTypeToCopy()
        state = self.obj.getAlternateCopyableState()
        for k,v in state.iteritems():
            yield k
            yield v

class MyRemoteCopy3(pb.RemoteCopy):
    pass
class MyRemoteCopy3Unslicer(copyable.RemoteCopyUnslicer):
    def __init__(self):
        self.schema = None
    def factory(self, state):
        obj = MyRemoteCopy3()
        obj.setCopyableState(state)
        return obj
    def receiveClose(self):
        obj,d = copyable.RemoteCopyUnslicer.receiveClose(self)
        obj.f = "yes"
        return obj, d

# register MyCopyable3Slicer as an ISlicer adapter for MyCopyable3, so we
# can verify that it overrides the inherited CopyableSlicer behavior. We
# also register an Unslicer to create the results.
components.registerAdapter(MyCopyable3Slicer, MyCopyable3, tokens.ISlicer)
copyable.registerRemoteCopyUnslicerFactory("MyCopyable3name",
                                           MyRemoteCopy3Unslicer)


# MyCopyable4 uses auto-registration, and adds a stateSchema

class MyCopyable4(pb.Copyable):
    pass
class MyRemoteCopy4(pb.RemoteCopy):
    copytype = reflect.qual(MyCopyable4)
    stateSchema = schema.AttributeDictConstraint(('foo', int),
                                                 ('bar', str))
    pass

# MyCopyable5 disables auto-registration

class MyRemoteCopy5(pb.RemoteCopy):
    copytype = None # disable auto-registration


class Copyable(TargetMixin, unittest.TestCase):

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
        # some of these tests require that we return a Failure object, so we
        # have to wrap this in a tuple to survive the Deferred.
        d.addCallback(lambda res: (target.obj,))
        return d

    def testCopy0(self):
        d = self.send(1)
        d.addCallback(self.failUnlessEqual, (1,))
        return d

    def testFailure1(self):
        self.callingBroker.unsafeTracebacks = True
        try:
            raise RuntimeError("message here")
        except:
            f0 = failure.Failure()
        d = self.send(f0)
        d.addCallback(self._testFailure1_1)
        return d
    def _testFailure1_1(self, (f,)):
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
        d = self.send(f0)
        d.addCallback(self._testFailure2_1)
        return d
    def _testFailure2_1(self, (f,)):
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
        d = self.send(obj)
        d.addCallback(self._testCopy1_1)
        return d
    def _testCopy1_1(self, (res,)):
        self.failUnless(isinstance(res, MyRemoteCopy1))
        self.failUnlessEqual(res.a, 12)
        self.failUnlessEqual(res.b, "foo")

    def testCopy2(self):
        obj = MyCopyable2() # has a custom getStateToCopy
        obj.a = 12 # ignored
        obj.b = "foo"
        d = self.send(obj)
        d.addCallback(self._testCopy2_1)
        return d
    def _testCopy2_1(self, (res,)):
        self.failUnless(isinstance(res, MyRemoteCopy2))
        self.failUnlessEqual(res.c, 1)
        self.failUnlessEqual(res.d, "foo")
        self.failIf(hasattr(res, "a"))

    def testCopy3(self):
        obj = MyCopyable3() # has a custom Slicer
        obj.a = 12 # ignored
        obj.b = "foo" # ignored
        d = self.send(obj)
        d.addCallback(self._testCopy3_1)
        return d
    def _testCopy3_1(self, (res,)):
        self.failUnless(isinstance(res, MyRemoteCopy3))
        self.failUnlessEqual(res.e, 2)
        self.failUnlessEqual(res.f, "yes")
        self.failIf(hasattr(res, "a"))

    def testCopy4(self):
        obj = MyCopyable4()
        obj.foo = 12
        obj.bar = "bar"
        d = self.send(obj)
        d.addCallback(self._testCopy4_1, obj)
        return d
    def _testCopy4_1(self, (res,), obj):
        self.failUnless(isinstance(res, MyRemoteCopy4))
        self.failUnlessEqual(res.foo, 12)
        self.failUnlessEqual(res.bar, "bar")

        obj.bad = "unwanted attribute"
        d = self.send(obj)
        d.addCallbacks(lambda res: self.fail("this was supposed to fail"),
                       self._testCopy4_2, errbackArgs=(obj,))
        return d
    def _testCopy4_2(self, why, obj):
        why.trap(Violation)
        self.failUnlessSubstring("unknown attribute 'bad'", str(why))
        del obj.bad

        obj.foo = "not a number"
        d = self.send(obj)
        d.addCallbacks(lambda res: self.fail("this was supposed to fail"),
                       self._testCopy4_3, errbackArgs=(obj,))
        return d
    def _testCopy4_3(self, why, obj):
        why.trap(Violation)
        self.failUnlessSubstring("STRING token rejected by IntegerConstraint",
                                 str(why))

        obj.foo = 12
        obj.bar = "very long " * 1000
        d = self.send(obj)
        d.addCallbacks(lambda res: self.fail("this was supposed to fail"),
                       self._testCopy4_4)
        return d
    def _testCopy4_4(self, why):
        why.trap(Violation)
        self.failUnlessSubstring("token too large", str(why))

class Registration(unittest.TestCase):
    def testRegistration(self):
        rc_classes = copyable.debug_RemoteCopyClasses
        copyable_classes = rc_classes.values()
        self.failUnless(MyRemoteCopy1 in copyable_classes)
        self.failUnless(MyRemoteCopy2 in copyable_classes)
        self.failUnlessIdentical(rc_classes["MyCopyable2name"],
                                 MyRemoteCopy2)
        self.failIf(MyRemoteCopy5 in copyable_classes)


##############
# verify that ICopyable adapters are actually usable


class TheThirdPartyClassThatIWantToCopy:
    def __init__(self, a, b):
        self.a = a
        self.b = b

def copy_ThirdPartyClass(orig):
    return "TheThirdPartyClassThatIWantToCopy_name", orig.__dict__
copyable.registerCopier(TheThirdPartyClassThatIWantToCopy,
                        copy_ThirdPartyClass)

def make_ThirdPartyClass(state):
    # unpack the state into constructor arguments
    a = state['a']; b = state['b']
    # now create the object with the constructor
    return TheThirdPartyClassThatIWantToCopy(a, b)
copyable.registerRemoteCopyFactory("TheThirdPartyClassThatIWantToCopy_name",
                                   make_ThirdPartyClass)

class Adaptation(TargetMixin, unittest.TestCase):
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
        # some of these tests require that we return a Failure object, so we
        # have to wrap this in a tuple to survive the Deferred.
        d.addCallback(lambda res: (target.obj,))
        return d

    def testAdaptation(self):
        obj = TheThirdPartyClassThatIWantToCopy(45, 91)
        d = self.send(obj)
        d.addCallback(self._testAdaptation_1)
        return d
    def _testAdaptation_1(self, (res,)):
        self.failUnless(isinstance(res, TheThirdPartyClassThatIWantToCopy))
        self.failUnlessEqual(res.a, 45)
        self.failUnlessEqual(res.b, 91)

