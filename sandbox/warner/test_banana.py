#! /usr/bin/python

from twisted.trial import unittest
dr = unittest.deferredResult
de = unittest.deferredError
from twisted.python import reflect, log, failure
from twisted.python.components import registerAdapter
from twisted.internet import reactor, defer

from banana import BananaError
from tokens import ISlicer, Violation
import slicer, schema, tokens, debug
from slicer import UnbananaFailure

import StringIO, types, sys

#log.startLogging(sys.stderr)

# some utility functions to manually assemble bytestreams

def tOPEN(count):
    return ("OPEN", count)
def tCLOSE(count):
    return ("CLOSE", count)
tABORT = ("ABORT",)

def bOPEN(opentype, count):
    assert count < 128
    return chr(count) + "\x88" + chr(len(opentype)) + "\x82" + opentype
def bCLOSE(count):
    assert count < 128
    return chr(count) + "\x89"
def bINT(num):
    if num >=0:
        assert num < 128
        return chr(num) + "\x81"
    num = -num
    assert num < 128
    return chr(num) + "\x83"
def bSTR(str):
    assert len(str) < 128
    return chr(len(str)) + "\x82" + str
def bERROR(str):
    assert len(str) < 128
    return chr(len(str)) + "\x8d" + str
    
# DecodeTest (24): turns tokens into objects, tests objects and UFs
# EncodeTest (13): turns objects/instance into tokens, tests tokens
# FailedInstanceTests (2): 1:turn instances into tokens and fail, 2:reverse

# ByteStream (3): turn object into bytestream, test bytestream
# InboundByteStream (14): turn bytestream into object, check object
#                         with or without constraints
# ThereAndBackAgain (20): encode then decode object, check object

# VocabTest1 (2): test setOutgoingVocabulary and an inbound Vocab sequence
# VocabTest2 (1): send object, test bytestream w/vocab-encoding
# Sliceable (2): turn instance into tokens (with ISliceable, test tokens

class TokenBanana(debug.TokenStorageBanana):
    """this Banana formats tokens as strings, numbers, and ('OPEN',) tuples
    instead of bytes. Used for testing purposes."""
    logReceiveErrors = False

    def testSlice(self, obj):
        assert len(self.slicerStack) == 1
        assert isinstance(self.slicerStack[0][0], slicer.RootSlicer)
        self.tokens = []
        dr(self.send(obj))
        assert len(self.slicerStack) == 1
        assert not self.rootSlicer.sendQueue
        assert isinstance(self.slicerStack[0][0], slicer.RootSlicer)
        return self.tokens

    def testFailure(self, obj):
        assert len(self.slicerStack) == 1
        assert isinstance(self.slicerStack[0][0], slicer.RootSlicer)
        self.tokens = []
        f = de(self.send(obj))
        assert len(self.slicerStack) == 1
        assert not self.rootSlicer.sendQueue
        assert isinstance(self.slicerStack[0][0], slicer.RootSlicer)
        return f, self.tokens

    def __del__(self):
        assert not self.rootSlicer.sendQueue

class UnbananaTestMixin:
    def setUp(self):
        self.hangup = False
        self.banana = TokenBanana()
    def tearDown(self):
        if not self.hangup:
            self.failUnless(len(self.banana.receiveStack) == 1)
            self.failUnless(isinstance(self.banana.receiveStack[0],
                                       slicer.StorageRootUnslicer))
            
    def do(self, tokens):
        self.failUnless(len(self.banana.receiveStack) == 1)
        self.failUnless(isinstance(self.banana.receiveStack[0],
                                   slicer.StorageRootUnslicer))
        obj = self.banana.processTokens(tokens)
        return obj

    def failIfUnbananaFailure(self, res):
        if isinstance(res, UnbananaFailure):
            # something went wrong
            print "There was a failure while Unbananaing '%s':" % res.where
            print res.getTraceback()
            self.fail("UnbananaFailure")

    def shouldDropConnection(self, tokens):
        ret = self.do(tokens)
        f = self.banana.transport.disconnectReason
        if not f:
            self.fail("didn't fail, ret=%s" % ret)
        if not isinstance(f, failure.Failure):
            self.fail("disconnectReason wasn't a Failure:", f)
        if not f.check(BananaError):
            self.fail("wrong exception type: %s" % f)
        self.hangup = True # to stop the tearDown check
        return f

    def checkUnbananaFailure(self, res, where, failtype=None):
        self.failUnless(isinstance(res, UnbananaFailure))
        if failtype:
            self.failUnless(res.failure,
                            "No Failure object in UnbananaFailure")
            if not res.check(failtype):
                print "Wrong exception (wanted '%s'):" % failtype
                print res.getTraceback()
                self.fail("Wrong exception (wanted '%s'):" % failtype)
        self.failUnlessEqual(res.where, where)
        self.banana.object = None # to stop the tearDown check TODO ??

class TestBanana(debug.LoggingStorageBanana):
    logReceiveErrors = False
    #doLog = "rx"
    pass

class TestTransport(StringIO.StringIO):
    disconnectReason = None
    def loseConnection(self, why="unknown"):
        self.disconnectReason = why

class TestBananaMixin:
    def setUp(self):
        self.makeBanana()

    def makeBanana(self):
        self.banana = TestBanana()
        self.banana.transport = TestTransport()
        self.banana.connectionMade()

    def encode(self, obj):
        dr(self.banana.send(obj))
        return self.banana.transport.getvalue()

    def clearOutput(self):
        self.banana.transport = TestTransport()

    def decode(self, str):
        self.banana.object = None
        self.banana.dataReceived(str)
        obj = self.banana.object
        self.banana.object = None
        return obj

    def shouldFail(self, stream):
        self.makeBanana()
        obj = self.decode(stream)
        f = self.banana.transport.disconnectReason
        if not f:
            self.fail("didn't fail, ret=%s" % ret)
        if not isinstance(f, failure.Failure):
            self.fail("disconnectReason wasn't a Failure:", f)
        if not f.check(BananaError):
            self.fail("wrong exception type: %s" % f)
        return f

    def wantEqual(self, got, wanted):
        if got != wanted:
            print
            print "wanted: '%s'" % wanted, repr(wanted)
            print "got   : '%s'" % got, repr(got)
            self.fail("did not get expected string")

    def loop(self, obj):
        return self.decode(self.encode(obj))
    def looptest(self, obj):
        obj2 = self.loop(obj)
        if isinstance(obj2, UnbananaFailure):
            print obj2.getTraceback()
            self.fail("UnbananaFailure at %s" % obj2.where)
        self.failUnlessEqual(obj2, obj)
        self.failUnlessEqual(type(obj2), type(obj))

def join(*args):
    return "".join(args)



class DecodeTest(UnbananaTestMixin, unittest.TestCase):
        
    def test_simple_list(self):
        "simple list"
        res = self.do([tOPEN(0),'list',1,2,3,"a","b",tCLOSE(0)])
        self.failUnlessEqual(res, [1,2,3,'a','b'])

    def test_aborted_list(self):
        "aborted list"
        res = self.do([tOPEN(0),'list', 1, tABORT, tCLOSE(0)])
        self.checkUnbananaFailure(res, "root.[1]")

    def test_aborted_list2(self):
        "aborted list2"
        res = self.do([tOPEN(0),'list', 1, tABORT,
                       tOPEN(1),'list', 2, 3, tCLOSE(1),
                       tCLOSE(0)])
        self.checkUnbananaFailure(res, "root.[1]")

    def test_aborted_list3(self):
        "aborted list3"
        res = self.do([tOPEN(0),'list', 1, 
                        tOPEN(1),'list', 2, 3, 4,
                         tOPEN(2),'list', 5, 6, tABORT, tCLOSE(2),
                        tCLOSE(1),
                       tCLOSE(0)])
        self.checkUnbananaFailure(res, "root.[1].[3].[2]")

    def test_nested_list(self):
        "nested list"
        res = self.do([tOPEN(0),'list',1,2,tOPEN(1),'list',3,4,tCLOSE(1),tCLOSE(0)])
        self.failUnlessEqual(res, [1,2,[3,4]])

    def test_list_with_tuple(self):
        "list with tuple"
        res = self.do([tOPEN(0),'list',1,2,tOPEN(1),'tuple',3,4,tCLOSE(1),tCLOSE(0)])
        self.failUnlessEqual(res, [1,2,(3,4)])

    def test_dict(self):
        "dict"
        res = self.do([tOPEN(0),'dict',"a",1,"b",2,tCLOSE(0)])
        self.failUnlessEqual(res, {'a':1, 'b':2})
        
    def test_dict_with_duplicate_keys(self):
        "dict with duplicate keys"
        f = self.shouldDropConnection([tOPEN(0),'dict',"a",1,"a",2,tCLOSE(0)])
        self.failUnlessEqual(f.value.where, "root.{}")
        self.failUnlessEqual(f.value.args[0], "duplicate key 'a'")

    def test_dict_with_list(self):
        "dict with list"
        res = self.do([tOPEN(0),'dict',
                        "a",1,
                        "b", tOPEN(1),'list', 2, 3, tCLOSE(1),
                       tCLOSE(0)])
        self.failUnlessEqual(res, {'a':1, 'b':[2,3]})
        
    def test_dict_with_tuple_as_key(self):
        "dict with tuple as key"
        res = self.do([tOPEN(0),'dict',
                        tOPEN(1),'tuple', 1, 2, tCLOSE(1), "a",
                       tCLOSE(0)])
        self.failUnlessEqual(res, {(1,2):'a'})
        
    def test_dict_with_mutable_key(self):
        "dict with mutable key"
        f = self.shouldDropConnection([tOPEN(0),'dict',
                                        tOPEN(1),'list', 1, 2, tCLOSE(1), "a",
                                       tCLOSE(0)])
        self.failUnlessEqual(f.value.where, "root.{}")
        self.failUnlessEqual(f.value.args[0], "unhashable key '[1, 2]'")

    def test_instance(self):
        "instance"
        f1 = Foo(); f1.a = 1; f1.b = [2,3]
        f2 = Bar(); f2.d = 4; f1.c = f2
        res = self.do([tOPEN(0),'instance', "test_banana.Foo",
                        "a", 1,
                        "b", tOPEN(1),'list', 2, 3, tCLOSE(1),
                        "c", tOPEN(2),'instance', "test_banana.Bar",
                              "d", 4,
                             tCLOSE(2),
                       tCLOSE(0)])
        self.failUnlessEqual(res, f1)
        
    def test_instance_bad1(self):
        "subinstance with numeric classname"
        tokens = [tOPEN(0),'instance', "Foo",
                   "a", 1,
                   "b", tOPEN(1),'list', 2, 3, tCLOSE(1),
                   "c",
                   tOPEN(2),'instance', 37, "d", 4, tCLOSE(2),
                  tCLOSE(0)]
        f = self.shouldDropConnection(tokens)
        self.failUnlessEqual(f.value.where, "root.<Foo>.c.<??>")
        self.failUnlessEqual(f.value.args[0],
                             "InstanceUnslicer classname must be string")

    def test_instance_bad2(self):
        "subinstance with numeric attribute name"
        tokens = [tOPEN(0),'instance', "Foo",
                   "a", 1,
                   "b", tOPEN(1),'list', 2, 3, tCLOSE(1),
                   "c",
                   tOPEN(2),'instance',
                    "Bar", 37, 4,
                   tCLOSE(2),
                  tCLOSE(0)]
        f = self.shouldDropConnection(tokens)
        self.failUnlessEqual(f.value.where, "root.<Foo>.c.<Bar>.attrname??")
        self.failUnlessEqual(f.value.args[0],
                             "InstanceUnslicer keys must be STRINGs")

    def test_ref1(self):
        res = self.do([tOPEN(0),'list',
                        tOPEN(1),'list', 1, 2, tCLOSE(1),
                        tOPEN(2),'reference', 1, tCLOSE(2),
                       tCLOSE(0)])
        self.failIfUnbananaFailure(res)
        self.failUnlessEqual(res, [[1,2], [1,2]])
        self.failUnlessIdentical(res[0], res[1])

    def test_ref2(self):
        res = self.do([tOPEN(0),'list',
                       tOPEN(1),'list', 1, 2, tCLOSE(1),
                       tOPEN(2),'reference', 0, tCLOSE(2),
                       tCLOSE(0)])
        self.failIfUnbananaFailure(res)
        wanted = [[1,2]]
        wanted.append(wanted)
        self.failUnlessEqual(res, wanted)
        self.failUnlessIdentical(res, res[1])

    def test_ref3(self):
        res = self.do([tOPEN(0),'list',
                        tOPEN(1),'tuple', 1, 2, tCLOSE(1),
                        tOPEN(2),'reference', 1, tCLOSE(2),
                       tCLOSE(0)])
        self.failIfUnbananaFailure(res)
        wanted = [(1,2)]
        wanted.append(wanted[0])
        self.failUnlessEqual(res, wanted)
        self.failUnlessIdentical(res[0], res[1])

    def test_ref4(self):
        res = self.do([tOPEN(0),'list',
                        tOPEN(1),'dict', "a", 1, tCLOSE(1),
                        tOPEN(2),'reference', 1, tCLOSE(2),
                       tCLOSE(0)])
        self.failIfUnbananaFailure(res)
        wanted = [{"a":1}]
        wanted.append(wanted[0])
        self.failUnlessEqual(res, wanted)
        self.failUnlessIdentical(res[0], res[1])

    def test_ref5(self):
        # The Droste Effect: a list that contains itself
        res = self.do([tOPEN(0),'list',
                        5,
                        6,
                        tOPEN(1),'reference', 0, tCLOSE(1),
                        7,
                       tCLOSE(0)])
        self.failIfUnbananaFailure(res)
        wanted = [5,6]
        wanted.append(wanted)
        wanted.append(7)
        self.failUnlessEqual(res, wanted)
        self.failUnlessIdentical(res[2], res)

    def test_ref6(self):
        # everybody's favorite "([(ref0" test case. A tuple of a list of a
        # tuple of the original tuple. Such cycles must always have a
        # mutable container in them somewhere, or they couldn't be
        # constructed, but the resulting object involves a lot of deferred
        # results because the mutable list is the *only* object that can
        # be created without dependencies
        res = self.do([tOPEN(0),'tuple',
                        tOPEN(1),'list',
                         tOPEN(2),'tuple',
                          tOPEN(3),'reference', 0, tCLOSE(3),
                         tCLOSE(2),
                        tCLOSE(1),
                       tCLOSE(0)])
        self.failIfUnbananaFailure(res)
        wanted = ([],)
        wanted[0].append((wanted,))
        self.failUnlessEqual(res, wanted)
        self.failUnlessIdentical(res[0][0][0], res)

        # TODO: need a test where tuple[0] and [1] are deferred, but
        # tuple[0] becomes available before tuple[2] is inserted. Not sure
        # this is possible, but it would improve test coverage in
        # TupleUnslicer
        
    def test_failed_dict1(self):
        # dies during open because of bad opentype
        res = self.do([tOPEN(0),'list', 1,
                        tOPEN(1),"bad",
                         "a", 2,
                         "b", 3,
                        tCLOSE(1),
                       tCLOSE(0)])
        self.checkUnbananaFailure(res, "root.[1]")

    def test_failed_dict2(self):
        # dies during start
        res = self.do([tOPEN(0),'list', 1,
                       tOPEN(1),'dict2', "a", 2, "b", 3, tCLOSE(1),
                       tCLOSE(0)])
        self.checkUnbananaFailure(res, "root.[1].{}")
        #"dead in start"

    def test_failed_dict3(self):
        # dies during key
        res = self.do([tOPEN(0),'list', 1,
                       tOPEN(1),'dict1', "a", 2, "die", tCLOSE(1),
                       tCLOSE(0)])
        self.checkUnbananaFailure(res, "root.[1].{}")
        #"aaaaaaaaargh"
        res = self.do([tOPEN(2),'list', 3, 4, tCLOSE(2)])
        self.failUnlessEqual(res, [3,4])

    def test_failed_dict4(self):
        # dies during value
        res = self.do([tOPEN(0),'list', 1,
                        tOPEN(1),'dict1',
                         "a", 2,
                         "b", "die",
                        tCLOSE(1),
                       tCLOSE(0)])
        self.checkUnbananaFailure(res, "root.[1].{}[b]")
        # "aaaaaaaaargh"
        
    def test_failed_dict5(self):
        # dies during finish
        res = self.do([tOPEN(0),'list', 1,
                        tOPEN(1),'dict1',
                         "a", 2,
                         "please_die_in_finish", 3,
                        tCLOSE(1),
                       tCLOSE(0)])
        self.checkUnbananaFailure(res, "root.[1].{}")
        # "dead in receiveClose()"

class Bar:
    def __cmp__(self, them):
        if not type(them) == type(self):
            return -1
        return cmp((self.__class__, self.__dict__),
                   (them.__class__, them.__dict__))
class Foo(Bar):
    pass
        
class EncodeTest(unittest.TestCase):
    def setUp(self):
        self.banana = TokenBanana()
    def do(self, obj):
        return self.banana.testSlice(obj)
    def tearDown(self):
        self.failUnless(len(self.banana.slicerStack) == 1)
        self.failUnless(isinstance(self.banana.slicerStack[0][0],
                                   slicer.RootSlicer))

    def testList(self):
        res = self.do([1,2])
        self.failUnlessEqual(res, [tOPEN(0),'list', 1, 2, tCLOSE(0)])
    def testTuple(self):
        res = self.do((1,2))
        self.failUnlessEqual(res, [tOPEN(0),'tuple', 1, 2, tCLOSE(0)])
    def testNestedList(self):
        res = self.do([1,2,[3,4]])
        self.failUnlessEqual(res, [tOPEN(0),'list', 1, 2,
                                    tOPEN(1),'list', 3, 4, tCLOSE(1),
                                   tCLOSE(0)])
    def testNestedList2(self):
        res = self.do([1,2,(3,4,[5, "hi"])])
        self.failUnlessEqual(res, [tOPEN(0),'list', 1, 2,
                                    tOPEN(1),'tuple', 3, 4,
                                     tOPEN(2),'list', 5, "hi", tCLOSE(2),
                                    tCLOSE(1),
                                   tCLOSE(0)])

    def testDict(self):
        res = self.do({'a': 1, 'b': 2})
        self.failUnless(
            res == [tOPEN(0),'dict', 'a', 1, 'b', 2, tCLOSE(0)] or
            res == [tOPEN(0),'dict', 'b', 2, 'a', 1, tCLOSE(0)])
    def test_ref1(self):
        l = [1,2]
        obj = [l,l]
        res = self.do(obj)
        self.failUnlessEqual(res, [tOPEN(0),'list',
                                    tOPEN(1),'list', 1, 2, tCLOSE(1),
                                    tOPEN(2),'reference', 1, tCLOSE(2),
                                   tCLOSE(0)])

    def test_ref2(self):
        obj = [[1,2]]
        obj.append(obj)
        res = self.do(obj)
        self.failUnlessEqual(res, [tOPEN(0),'list',
                                    tOPEN(1),'list', 1, 2, tCLOSE(1),
                                    tOPEN(2),'reference', 0, tCLOSE(2),
                                   tCLOSE(0)])

    def test_ref3(self):
        obj = [(1,2)]
        obj.append(obj[0])
        res = self.do(obj)
        self.failUnlessEqual(res, [tOPEN(0),'list',
                                    tOPEN(1),'tuple', 1, 2, tCLOSE(1),
                                    tOPEN(2),'reference', 1, tCLOSE(2),
                                   tCLOSE(0)])

    def test_ref4(self):
        obj = [{"a":1}]
        obj.append(obj[0])
        res = self.do(obj)
        self.failUnlessEqual(res, [tOPEN(0),'list',
                                    tOPEN(1),'dict', "a", 1, tCLOSE(1),
                                    tOPEN(2),'reference', 1, tCLOSE(2),
                                   tCLOSE(0)])

    def test_ref6(self):
        # everybody's favorite "([(ref0" test case.
        obj = ([],)
        obj[0].append((obj,))
        res = self.do(obj)
        self.failUnlessEqual(res,
                             [tOPEN(0),'tuple',
                               tOPEN(1),'list',
                                tOPEN(2),'tuple',
                                 tOPEN(3),'reference', 0, tCLOSE(3),
                                tCLOSE(2),
                               tCLOSE(1),
                              tCLOSE(0)])

    def test_refdict1(self):
        # a dictionary with a value that isn't available right away
        d = {1: "a"}
        t = (d,)
        d[2] = t
        res = self.do(d)
        self.failUnlessEqual(res,
                             [tOPEN(0),'dict',
                               1, "a",
                               2, tOPEN(1),'tuple',
                                   tOPEN(2),'reference', 0, tCLOSE(2),
                                  tCLOSE(1),
                              tCLOSE(0)])
    
    def test_instance_one(self):
        obj = Bar()
        obj.a = 1
        classname = reflect.qual(Bar)
        res = self.do(obj)
        self.failUnlessEqual(res,
                             [tOPEN(0),'instance', classname, "a", 1, tCLOSE(0)])
    def test_instance_two(self):
        f1 = Foo(); f1.a = 1; f1.b = [2,3]
        f2 = Bar(); f2.d = 4; f1.c = f2
        fooname = reflect.qual(Foo)
        barname = reflect.qual(Bar)
        # needs OrderedDictSlicer for the test to work
        res = self.do(f1)
        self.failUnlessEqual(res,
                             [tOPEN(0),'instance', fooname,
                               "a", 1,
                               "b", tOPEN(1),'list', 2, 3, tCLOSE(1),
                               "c",
                                 tOPEN(2),'instance', barname,
                                  "d", 4,
                                 tCLOSE(2),
                              tCLOSE(0)])



class ErrorfulSlicer(slicer.BaseSlicer):
    def __init__(self, mode, shouldSucceed, ignoreChildDeath=False):
        self.mode = mode
        self.items = [1]
        self.items.append(mode)
        self.items.append(3)
        #if mode not in ('success', 'deferred-good'):
        if not shouldSucceed:
            self.items.append("unreached")
        self.counter = -1
        self.childDied = False
        self.ignoreChildDeath = ignoreChildDeath

    def __iter__(self):
        return self
    def slice(self, streamable, banana):
        self.streamable = streamable
        if self.mode == "slice":
            raise Violation("slice failed")
        return self

    def next(self):
        self.counter += 1
        if not self.items:
            raise StopIteration
        obj = self.items.pop(0)
        if obj == "next":
            raise Violation("next failed")
        if obj == "deferred-good":
            d = defer.Deferred()
            reactor.callLater(1, d.callback, None)
            return d
        if obj == "deferred-bad":
            d = defer.Deferred()
            # the Banana should bail, so don't bother with the timer
            return d
        if obj == "newSlicerFor":
            unserializable = open("unserializable.txt", "w")
            # Hah! Serialize that!
            return unserializable
        if obj == "unreached":
            print "error: slicer.next called after it should have stopped"
        return obj

    def childAborted(self, v):
        self.childDied = True
        if not self.ignoreChildDeath:
            raise v

    def describe(self):
        return "ErrorfulSlicer[%d]" % self.counter

# Slicer creation (schema pre-validation?)
# .slice (called in pushSlicer) ?
# .slice.next raising Violation
# .slice.next returning Deferred when streaming isn't allowed
# .sendToken (non-primitive token, can't happen)
# .newSlicerFor (no ISlicer adapter)
# top.childAborted

class EncodeFailureTest(unittest.TestCase):
    def setUp(self):
        self.banana = TokenBanana()

    def send(self, obj):
        return self.banana.send(obj)
    def failed(self, d):
        print "timeout"
        d.callback("timeout")
        
    def waitForSuccess(self, d):
        timeout = reactor.callLater(2, self.failed, d)
        e = dr(d)
        if e != "timeout":
            timeout.cancel()
        return self.banana.tokens
        
    def waitForError(self, d):
        timeout = reactor.callLater(2, self.failed, d)
        e = de(d)
        if e != "timeout":
            timeout.cancel()
        return e

    def testSuccess1(self):
        # make sure the test slicer works correctly
        s = ErrorfulSlicer("success", True)
        d = self.send(s)
        encoded = self.waitForSuccess(d)

    def testSuccessStreaming(self):
        # success
        s = ErrorfulSlicer("deferred-good", True)
        d = self.send(s)
        encoded = self.waitForSuccess(d)

    def test1(self):
        # failure during .slice (called from pushSlicer)
        s = ErrorfulSlicer("slice", False)
        d = self.send(s)
        e = self.waitForError(d)
        self.failUnless(e.check(Violation))
        self.failUnlessEqual(e.value.where, "<Root>")
        self.failUnlessEqual(e.value.args, ("slice failed",))

    def test2(self):
        # .slice.next raising Violation
        s = ErrorfulSlicer("next", False)
        d = self.send(s)
        e = self.waitForError(d)
        self.failUnless(e.check(Violation))
        self.failUnlessEqual(e.value.where, "<Root>.ErrorfulSlicer[1]")
        self.failUnlessEqual(e.value.args, ("next failed",))

    def test3(self):        
        # .slice.next returning Deferred when streaming isn't allowed
        self.banana.rootSlicer.allowStreaming(False)
        s = ErrorfulSlicer("deferred-bad", False)
        d = self.send(s)
        e = self.waitForError(d)
        self.failUnless(e.check(Violation))
        self.failUnlessEqual(e.value.where, "<Root>.ErrorfulSlicer[1]")
        self.failUnlessEqual(e.value.args, ("parent not streamable",))

    def test4(self):
        # .newSlicerFor (no ISlicer adapter), parent re-raises
        s = ErrorfulSlicer("newSlicerFor", False)
        d = self.send(s)
        e = self.waitForError(d)
        self.failUnless(e.check(Violation))
        self.failUnlessEqual(e.value.where, "<Root>.ErrorfulSlicer[1]")
        self.failUnless("cannot serialize <open file" in e.value.args[0])
        self.failUnless(s.childDied)

    def test5(self):
        # .newSlicerFor (no ISlicer adapter), parent ignores
        s = ErrorfulSlicer("newSlicerFor", True, True)
        d = self.send(s)
        e = self.waitForSuccess(d)
        self.failUnless(s.childDied) # noticed but ignored

# receiving side:
#  long header (>64 bytes)
#  checkToken (top.openerCheckToken)
#  checkToken (top.checkToken)
#  typebyte == LIST (oldbanana)
#  bad VOCAB key
#  too-long vocab key
#  bad FLOAT encoding
#  top.receiveClose
#  top.finish
#  top.reportViolation
#  oldtop.finish (in from handleViolation)
#  top.doOpen
#  top.start
# plus all of these when discardCount != 0

class DecodeFailureTest(TestBananaMixin, unittest.TestCase):

    def testSuccess1(self):
        s = join(bOPEN("list",0), bINT(1), bINT(2), bCLOSE(0))
        o = self.decode(s)
        self.failUnlessEqual(o, [1,2])

    def testLongHeader(self):
        raise unittest.SkipTest("not ready yet")
        # would be a string but the header is too long
        s = "\x01" * 66 + "\x82" + "stupidly long string"
        o = self.decode(s)

class FailedInstanceTests(unittest.TestCase):
    def setUp(self):
        self.banana = TokenBanana()
        # turn off the "unsafe" extensions
        self.banana.rootSlicer.slicerTable = {}
        self.banana.rootUnslicer.topRegistry = slicer.UnslicerRegistry
        self.banana.rootUnslicer.openRegistry = slicer.UnslicerRegistry

    def encode(self, obj):
        return self.banana.testFailure(obj)
    def decode(self, tokens):
        return self.banana.processTokens(tokens)

    def test_make_instance(self):
        f1 = Foo(); f1.a = 1; f1.b = [2,3]
        # this will fail
        f, encoded = self.encode(f1)
        self.failUnless(f.check(tokens.Violation))
        # it fails before any tokens have been emitted
        self.failUnlessEqual(encoded, [])
       
    def test_get_instance(self):
        tokens = [tOPEN(0),'instance', "test_banana.Foo", "a", 1,
                  "b", tOPEN(1),'list', 2, 3, tCLOSE(1),
                  "c", tOPEN(2),'instance', "Bar", "d", 4, tCLOSE(2),
                  tCLOSE(0)]
        # this will fail
        res = self.decode(tokens)
        self.failUnless(isinstance(res, UnbananaFailure))

class ByteStream(TestBananaMixin, unittest.TestCase):

    def test_list(self):
        obj = [1,2]
        expected = join(bOPEN("list", 0),
                         bINT(1), bINT(2),
                        bCLOSE(0),
                        )
        self.wantEqual(self.encode(obj), expected)

    def test_ref6(self):
        # everybody's favorite "([(ref0" test case.
        obj = ([],)
        obj[0].append((obj,))

        expected = join(bOPEN("tuple",0),
                         bOPEN("list",1),
                          bOPEN("tuple",2),
                           bOPEN("reference",3),
                            bINT(0),
                           bCLOSE(3),
                          bCLOSE(2),
                         bCLOSE(1),
                        bCLOSE(0))
        self.wantEqual(self.encode(obj), expected)

    def test_two(self):
        f1 = Foo(); f1.a = 1; f1.b = [2,3]
        f2 = Bar(); f2.d = 4; f1.c = f2
        fooname = reflect.qual(Foo)
        barname = reflect.qual(Bar)
        # needs OrderedDictSlicer for the test to work

        expected = join(bOPEN("instance",0), bSTR(fooname),
                         bSTR("a"), bINT(1),
                         bSTR("b"),
                          bOPEN("list",1),
                           bINT(2), bINT(3),
                          bCLOSE(1),
                         bSTR("c"),
                           bOPEN("instance",2), bSTR(barname),
                            bSTR("d"), bINT(4),
                           bCLOSE(2),
                        bCLOSE(0))
        self.wantEqual(self.encode(f1), expected)

class InboundByteStream(TestBananaMixin, unittest.TestCase):

    def check(self, obj, stream):
        # use a new Banana for each check
        self.makeBanana()
        obj2 = self.decode(stream)
        self.failUnlessEqual(obj, obj2)

    def testInt(self):
        self.check(1, "\x01\x81")
        self.check(130, "\x02\x01\x81")
        self.check(-1, "\x01\x83")
        self.check(-130, "\x02\x01\x83")
        self.check(0, bINT(0))
        self.check(1, bINT(1))
        self.check(127, bINT(127))
        self.check(-1, bINT(-1))
        self.check(-127, bINT(-127))

    def testLong(self):
        self.check(258L, "\x02\x85\x01\x02") # TODO: 0x85 for LONGINT??
        self.check(-258L, "\x02\x86\x01\x02") # TODO: 0x85 for LONGINT??

    def testString(self):
        self.check("", "\x82")
        self.check("", "\x00\x82")
        self.check("", "\x00\x00\x82")
        self.check("", "\x00" * 64 + "\x82")

        f = self.shouldFail("\x00" * 65)
        self.failUnlessEqual(f.value.where, "root")
        self.failUnlessEqual(f.value.args[0],
                             "token prefix is limited to 64 bytes")
        f = self.shouldFail("\x00" * 65 + "\x82")
        self.failUnlessEqual(f.value.where, "root")
        self.failUnlessEqual(f.value.args[0],
                             "token prefix is limited to 64 bytes")

        self.check("a", "\x01\x82a")
        self.check("b"*130, "\x02\x01\x82" + "b"*130 + "extra")
        self.check("c"*1025, "\x01\x08\x82" + "c" * 1025 + "extra")
        self.check("fluuber", bSTR("fluuber"))


    def testList(self):
        self.check([1,2],
                   join(bOPEN('list',1),
                        bINT(1), bINT(2),
                        bCLOSE(1)))
        self.check([1,"b"],
                   join(bOPEN('list',1), bINT(1),
                        "\x01\x82b",
                        bCLOSE(1)))
        self.check([1,2,[3,4]],
                   join(bOPEN('list',1), bINT(1), bINT(2),
                         bOPEN('list',2), bINT(3), bINT(4),
                         bCLOSE(2),
                        bCLOSE(1)))

    def testTuple(self):
        self.check((1,2),
                   join(bOPEN('tuple',1), bINT(1), bINT(2),
                        bCLOSE(1)))

    def testDict(self):
        self.check({1:"a", 2:["b","c"]},
                   join(bOPEN('dict',1),
                        bINT(1), bSTR("a"),
                        bINT(2), bOPEN('list',2),
                         bSTR("b"), bSTR("c"),
                        bCLOSE(2),
                        bCLOSE(1)))

    def TRUE(self):
        return join(bOPEN("boolean",2), bINT(1), bCLOSE(2))
    def FALSE(self):
        return join(bOPEN("boolean",2), bINT(0), bCLOSE(2))

    def testBool(self):
        self.check(True, self.TRUE())

class InboundByteStream2(TestBananaMixin, unittest.TestCase):

    def decode2(self, string, constraint=None, childConstraint=None):
        if constraint:
            constraint = schema.makeConstraint(constraint)
        if childConstraint:
            childConstraint = schema.makeConstraint(childConstraint)
        banana = TestBanana()
        banana.receiveStack[-1].constraint = constraint
        banana.receiveStack[-1].childConstraint = childConstraint
        banana.object = None
        banana.dataReceived(string)
        self.failUnlessEqual(len(banana.receiveStack), 1)
        return banana.object
    def conform2(self, stream, obj, constraint, childConstraint=None):
        obj2 = self.decode2(stream, constraint, childConstraint)
        if isinstance(obj2, UnbananaFailure):
            print "failure", obj2
        self.failUnlessEqual(obj, obj2)
    def violate2(self, stream, where, constraint, childConstraint=None):
        obj2 = self.decode2(stream, constraint, childConstraint)
        self.failUnless(isinstance(obj2, slicer.UnbananaFailure),
                        "unslicer failed to fail")
        self.failUnlessEqual(obj2.where, where)

    def testConstrainedInt(self):
        pass # TODO: after implementing new LONGINT token

    def testConstrainedString(self):
        self.conform2("\x82", "",
                    schema.StringConstraint(10))
        self.conform2("\x0a\x82" + "a"*10 + "extra", "a"*10,
                    schema.StringConstraint(10))
        self.violate2("\x0b\x82" + "a"*11 + "extra",
                      "root",
                      schema.StringConstraint(10))

    def NOTtestFoo(self):
        if 0:
            a100 = chr(100) + "\x82" + "a"*100
            b100 = chr(100) + "\x82" + "b"*100
            self.violate2(join(bOPEN('list',1),
                               bOPEN('list',2), a100, b100, bCLOSE(2),
                               bCLOSE(1)),
                          "root.[0].[0]",
                          schema.ListOf(
                schema.ListOf(schema.StringConstraint(99), 2), 2))

        def OPENweird(count, weird):
            return chr(count) + "\x88" + weird
        
        self.violate2(join(bOPEN('list',1),
                           bOPEN('list',2),
                           OPENweird(3, bINT(64)),
                           bINT(1), bINT(2), bCLOSE(3),
                           bCLOSE(2),
                           bCLOSE(1)),
                      "root.[0].[0]", None)



    def testConstrainedList(self):
        self.conform2(join(bOPEN('list',1), bINT(1), bINT(2),
                           bCLOSE(1)),
                      [1,2],
                      schema.ListOf(int))
        self.violate2(join(bOPEN('list',1), bINT(1), "\x01\x82b",
                           bCLOSE(1)),
                      "root.[1]",
                      schema.ListOf(int))
        self.conform2(join(bOPEN('list',1),
                            bINT(1), bINT(2), bINT(3),
                           bCLOSE(1)),
                      [1,2,3],
                      schema.ListOf(int, maxLength=3))
        self.violate2(join(bOPEN('list',1),
                            bINT(1), bINT(2), bINT(3), bINT(4),
                           bCLOSE(1)),
                      "root.[3]",
                      schema.ListOf(int, maxLength=3))
        a100 = chr(100) + "\x82" + "a"*100
        b100 = chr(100) + "\x82" + "b"*100
        self.conform2(join(bOPEN('list',1), a100, b100, bCLOSE(1)),
                      ["a"*100, "b"*100],
                      schema.ListOf(schema.StringConstraint(100), 2))
        self.violate2(join(bOPEN('list',1), a100, b100, bCLOSE(1)),
                      "root.[0]",
                      schema.ListOf(schema.StringConstraint(99), 2))
        self.violate2(join(bOPEN('list',1), a100, b100, a100, bCLOSE(1)),
                      "root.[2]",
                      schema.ListOf(schema.StringConstraint(100), 2))

        self.conform2(join(bOPEN('list',1),
                            bOPEN('list',2),
                             bINT(11), bINT(12),
                            bCLOSE(2),
                            bOPEN('list',3),
                             bINT(21), bINT(22), bINT(23),
                            bCLOSE(3),
                           bCLOSE(1)),
                      [[11,12], [21, 22, 23]],
                      schema.ListOf(schema.ListOf(int, maxLength=3)))

        self.violate2(join(bOPEN('list',1),
                            bOPEN('list',2),
                             bINT(11), bINT(12),
                            bCLOSE(2),
                            bOPEN('list',3),
                             bINT(21), bINT(22), bINT(23),
                            bCLOSE(3),
                           bCLOSE(1)),
                      "root.[1].[2]",
                      schema.ListOf(schema.ListOf(int, maxLength=2)))

    def testConstrainedTuple(self):
        self.conform2(join(bOPEN('tuple',1), bINT(1), bINT(2),
                           bCLOSE(1)),
                      (1,2),
                      schema.TupleOf(int, int))
        self.violate2(join(bOPEN('tuple',1),
                           bINT(1), bINT(2), bINT(3),
                           bCLOSE(1)),
                      "root.[2]",
                      schema.TupleOf(int, int))
        self.violate2(join(bOPEN('tuple',1),
                           bINT(1), bSTR("not a number"),
                           bCLOSE(1)),
                      "root.[1]",
                      schema.TupleOf(int, int))
        self.conform2(join(bOPEN('tuple',1),
                           bINT(1), bSTR("twine"),
                           bCLOSE(1)),
                      (1, "twine"),
                      schema.TupleOf(int, str))
        self.conform2(join(bOPEN('tuple',1),
                           bINT(1),
                            bOPEN('list',2),
                             bINT(1), bINT(2), bINT(3),
                            bCLOSE(2),
                           bCLOSE(1)),
                      (1, [1,2,3]),
                      schema.TupleOf(int, schema.ListOf(int)))
        self.conform2(join(bOPEN('tuple',1),
                           bINT(1),
                            bOPEN('list',2),
                             bOPEN('list',3), bINT(2), bCLOSE(3),
                             bOPEN('list',4), bINT(3), bCLOSE(4),
                            bCLOSE(2),
                           bCLOSE(1)),
                      (1, [[2], [3]]),
                      schema.TupleOf(int, schema.ListOf(schema.ListOf(int))))
        self.violate2(join(bOPEN('tuple',1),
                           bINT(1),
                            bOPEN('list',2),
                             bOPEN('list',3),
                              bSTR("nan"),
                             bCLOSE(3),
                             bOPEN('list',4), bINT(3), bCLOSE(4),
                            bCLOSE(2),
                           bCLOSE(1)),
                      "root.[1].[0].[0]",
                      schema.TupleOf(int, schema.ListOf(schema.ListOf(int))))

    def testConstrainedDict(self):
        self.conform2(join(bOPEN('dict',1),
                           bINT(1), bSTR("a"),
                           bINT(2), bSTR("b"),
                           bINT(3), bSTR("c"),
                           bCLOSE(1)),
                      {1:"a", 2:"b", 3:"c"},
                      schema.DictOf(int, str))
        self.conform2(join(bOPEN('dict',1),
                           bINT(1), bSTR("a"),
                           bINT(2), bSTR("b"),
                           bINT(3), bSTR("c"),
                           bCLOSE(1)),
                      {1:"a", 2:"b", 3:"c"},
                      schema.DictOf(int, str, maxKeys=3))
        self.violate2(join(bOPEN('dict',1),
                           bINT(1), bSTR("a"),
                           bINT(2), bINT(10),
                           bINT(3), bSTR("c"),
                           bCLOSE(1)),
                      "root.{}[2]",
                      schema.DictOf(int, str))
        self.violate2(join(bOPEN('dict',1),
                           bINT(1), bSTR("a"),
                           bINT(2), bSTR("b"),
                           bINT(3), bSTR("c"),
                           bCLOSE(1)),
                      "root.{}",
                      schema.DictOf(int, str, maxKeys=2))

    def TRUE(self):
        return join(bOPEN("boolean",2), bINT(1), bCLOSE(2))
    def FALSE(self):
        return join(bOPEN("boolean",2), bINT(0), bCLOSE(2))

    def testConstrainedBool(self):
        self.conform2(self.TRUE(),
                      True,
                      bool)
        self.conform2(self.TRUE(),
                      True,
                      schema.BooleanConstraint())
        self.conform2(self.FALSE(),
                      False,
                      schema.BooleanConstraint())

        # booleans have ints, not strings. To do otherwise is a protocol
        # error, not a schema Violation. 
        f = self.shouldFail(join(bOPEN("boolean",1), bSTR("vrai"), bCLOSE(1)))
        self.failUnlessEqual(f.value.args[0],
                             "BooleanUnslicer only accepts an INT token")

        self.violate2(self.TRUE(),
                      "root.<bool>",
                      schema.BooleanConstraint(False))
        self.violate2(self.FALSE(),
                      "root.<bool>",
                      schema.BooleanConstraint(True))


class A:
    """
    dummy class
    """
    def amethod(self):
        pass
    def __cmp__(self, other):
        if not type(other) == type(self):
            return -1
        return cmp(self.__dict__, other.__dict__)

def afunc(self):
    pass

class ThereAndBackAgain(TestBananaMixin, unittest.TestCase):

    def test_int(self):
        self.looptest(42)
        self.looptest(-47)
    def test_bigint(self):
        # some of these are small enough to fit in an INT
        self.looptest(int(2**31-1))
        self.looptest(long(2**31+0))
        self.looptest(long(2**31+1))
        self.looptest(long(-2**31-1))
        self.looptest(long(-2**31+0))
        self.looptest(int(-2**31+1))
        self.looptest(long(2**100))
        self.looptest(long(-2**100))
        self.looptest(long(2**1000))
        self.looptest(long(-2**1000))
    def test_string(self):
        self.looptest("biggles")
    def test_unicode(self):
        self.looptest(u"biggles\u1234")
    def test_list(self):
        self.looptest([1,2])
    def test_tuple(self):
        self.looptest((1,2))
    def test_bool(self):
        self.looptest(True)
        self.looptest(False)
    def test_float(self):
        self.looptest(20.3)
    def test_none(self):
        n2 = self.loop(None)
        self.failUnless(n2 is None)
    def test_dict(self):
        self.looptest({'a':1})

    def test_func(self):
        self.looptest(afunc)
    def test_module(self):
        self.looptest(unittest)
    def test_instance(self):
        a = A()
        self.looptest(a)
    def test_module(self):
        self.looptest(A)
    def test_boundMethod(self):
        a = A()
        m1 = a.amethod
        m2 = self.loop(m1)

        self.failUnlessEqual(m1.im_class, m2.im_class)
        self.failUnlessEqual(m1.im_self, m2.im_self)
        self.failUnlessEqual(m1.im_func, m2.im_func)

    def test_classMethod(self):
        self.looptest(A.amethod)

    # some stuff from test_newjelly
    def testIdentity(self):
        # test to make sure that objects retain identity properly
        x = []
        y = (x)
        x.append(y)
        x.append(y)
        self.assertIdentical(x[0], x[1])
        self.assertIdentical(x[0][0], x)
        s = self.encode(x)
        z = self.decode(s)
        self.assertIdentical(z[0], z[1])
        self.assertIdentical(z[0][0], z)

    def testUnicode(self):
        if hasattr(types, 'UnicodeType'):
            x = [unicode('blah')]
            y = self.decode(self.encode(x))
            self.assertEquals(x, y)
            self.assertEquals(type(x[0]), type(y[0]))

    def testStressReferences(self):
        reref = []
        toplevelTuple = ({'list': reref}, reref)
        reref.append(toplevelTuple)
        s = self.encode(toplevelTuple)
        z = self.decode(s)
        self.assertIdentical(z[0]['list'], z[1])
        self.assertIdentical(z[0]['list'][0], z)

    def testMoreReferences(self):
        a = []
        t = (a,)
        t2 = (t,)
        a.append(t2)
        s = self.encode(t)
        z = self.decode(s)
        self.assertIdentical(z[0][0][0], z)


        
class VocabTest1(unittest.TestCase):
    def test_incoming1(self):
        b = TokenBanana()
        vdict = {1: 'list', 2: 'tuple', 3: 'dict'}
        keys = vdict.keys()
        keys.sort()
        setVdict = [tOPEN(0),'vocab']
        for k in keys:
            setVdict.append(k)
            setVdict.append(vdict[k])
        setVdict.append(tCLOSE(0))
        b.processTokens(setVdict)
        # banana should now know this vocabulary
        self.failUnlessEqual(b.incomingVocabulary, vdict)

    def test_outgoing(self):
        b = TokenBanana()
        vdict = {1: 'list', 2: 'tuple', 3: 'dict'}
        keys = vdict.keys()
        keys.sort()
        setVdict = [tOPEN(0),'vocab']
        for k in keys:
            setVdict.append(k)
            setVdict.append(vdict[k])
        setVdict.append(tCLOSE(0))
        b.setOutgoingVocabulary(vdict)
        vocabTokens = b.getTokens()
        self.failUnlessEqual(vocabTokens, setVdict)
        # banana should now know this vocabulary

class VocabTest2(TestBananaMixin, unittest.TestCase):
    def vbOPEN(self, count, opentype):
        num = self.invdict[opentype]
        return chr(count) + "\x88" + chr(num) + "\x87"
    
    def test_loop(self):
        vdict = {1: 'list', 2: 'tuple', 3: 'dict'}
        self.invdict = dict(zip(vdict.values(), vdict.keys()))

        self.banana.setOutgoingVocabulary(vdict)
        self.failUnlessEqual(self.banana.outgoingVocabulary, self.invdict)
        self.decode(self.banana.transport.getvalue())
        self.failUnlessEqual(self.banana.incomingVocabulary, vdict)
        self.clearOutput()
        s = self.encode([({'a':1},)])

        vbOPEN = self.vbOPEN
        expected = "".join([vbOPEN(1,"list"),
                             vbOPEN(2,"tuple"),
                              vbOPEN(3,"dict"),
                               bSTR('a'), bINT(1),
                              bCLOSE(3),
                             bCLOSE(2),
                            bCLOSE(1)])
        self.wantEqual(s, expected)


class SliceableByItself(slicer.BaseSlicer):
    def __init__(self, value):
        self.value = value
    def slice(self, streamable, banana):
        self.streamable = streamable
        # this is our "instance state"
        yield {"value": self.value}

class CouldBeSliceable:
    def __init__(self, value):
        self.value = value

class _AndICanHelp(slicer.BaseSlicer):
    def slice(self, streamable, banana):
        self.streamable = streamable
        yield {"value": self.obj.value}
registerAdapter(_AndICanHelp, CouldBeSliceable, ISlicer)

class Sliceable(unittest.TestCase):
    def setUp(self):
        self.banana = TokenBanana()
    def do(self, obj):
        return self.banana.testSlice(obj)
    def tearDown(self):
        self.failUnless(len(self.banana.slicerStack) == 1)
        self.failUnless(isinstance(self.banana.slicerStack[0][0],
                                   slicer.RootSlicer))

    def testDirect(self):
        # the object is its own Slicer
        i = SliceableByItself(42)
        res = self.do(i)
        self.failUnlessEqual(res, [tOPEN(0),
                                   tOPEN(1), "dict", "value", 42, tCLOSE(1),
                                   tCLOSE(0)])

    def testAdapter(self):
        # the adapter is the Slicer
        i = CouldBeSliceable(43)
        res = self.do(i)
        self.failUnlessEqual(res, [tOPEN(0),
                                   tOPEN(1), "dict", "value", 43, tCLOSE(1),
                                   tCLOSE(0)])


