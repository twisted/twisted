#! /usr/bin/python

from twisted.trial import unittest
from twisted.python import reflect
from banana import Banana
from slicer import Dummy, UnbananaFailure
from slicer import RootSlicer, RootSlicer2
from slicer import RootUnslicer, RootUnslicer2

import cStringIO, types

def OPEN(opentype, count):
    return ("OPEN", opentype, count)
def OPENlist(count):
    return ("OPEN", "list", count)
def OPENtuple(count):
    return ("OPEN", "tuple", count)
def OPENdict(count):
    return ("OPEN", "dict", count)
def OPENinstance(count):
    return ("OPEN", "instance", count)
def OPENref(count):
    return ("OPEN", "reference", count)
def CLOSE(count):
    return ("CLOSE", count)
ABORT = ("ABORT",)

def OPENdict1(count):
    return ("OPEN", "dict1", count)
def OPENdict2(count):
    return ("OPEN", "dict2", count)

class TokenBanana(Banana):
    """this Banana formats tokens as strings, numbers, and ('OPEN',) tuples
    instead of bytes. Used for testing purposes."""

    tokens = []

    def sendOpen(self, opentype):
        openID = self.openCount
        self.openCount += 1
        self.sendToken(("OPEN", opentype, openID))
        return openID

    def sendToken(self, token):
        self.tokens.append(token)

    def sendClose(self, openID):
        self.sendToken(("CLOSE", openID))

    def sendAbort(self, count=0):
        self.sendToken(("ABORT",))

    def testSlice(self, obj):
        assert(len(self.slicerStack) == 1)
        assert(isinstance(self.slicerStack[0],RootSlicer))
        self.tokens = []
        self.send(obj)
        assert(len(self.slicerStack) == 1)
        assert(isinstance(self.slicerStack[0],RootSlicer))
        return self.tokens

    def receiveToken(self, token):
        # future optimization note: most Unslicers on the stack will not
        # override .taste or .doOpen, so it would be faster to have the few
        # that *do* add themselves to a separate .openers and/or .tasters
        # stack. The issue is robustness: if the Unslicer is thrown out
        # because of an exception or an ABORT token (i.e. startDiscarding is
        # called), we must be sure to clean out their opener/taster too and
        # not leave it dangling. Having them implemented as methods inside
        # the Unslicer makes that easy, but means a full traversal of the
        # stack for each token even when nobody is doing any tasting.

#        for i in range(len(self.receiveStack)-1, -1, -1):
#            self.receiveStack[i].taste(token)

        if self.debug:
            print "receiveToken(%s)" % (token,)

        if type(token) == types.TupleType and token[0] == "OPEN":
            self.handleOpen(token[2], token[1])
            return

        if type(token) == types.TupleType and token[0] == "CLOSE":
            self.handleClose(token[1])
            return

        if type(token) == types.TupleType and token[0] == "ABORT":
            self.handleAbort()
            return

        self.handleToken(token)

    def receivedObject(self, obj):
        self.object = obj

    def processTokens(self, tokens):
        self.object = None
        for t in tokens:
            self.receiveToken(t)
        return self.object

class UnbananaTestMixin:
    def setUp(self):
        self.banana = TokenBanana()
    def tearDown(self):
        self.failUnless(len(self.banana.receiveStack) == 1)
        self.failUnless(isinstance(self.banana.receiveStack[0], RootUnslicer))
            
    def do(self, tokens):
        return self.banana.processTokens(tokens)

    def failIfUnbananaFailure(self, res):
        if isinstance(res, UnbananaFailure):
            # something went wrong
            print "There was a failure while Unbananaing '%s':" % res.where
            print res.failure.getTraceback()
            self.fail("UnbananaFailure")
        
    def assertUnbananaFailure(self, res, where, failtype=None):
        self.failUnless(isinstance(res, UnbananaFailure))
        if failtype:
            self.failUnless(res.failure,
                            "No Failure object in UnbananaFailure")
            if not res.failure.check(failtype):
                print "Wrong exception (wanted '%s'):" % failtype
                print res.failure.getTraceback()
                self.fail("Wrong exception (wanted '%s'):" % failtype)
        self.failUnlessEqual(res.where, where)
        self.banana.object = None # to stop the tearDown check
        
class UnbananaTestCase(UnbananaTestMixin, unittest.TestCase):
        
    def test_simple_list(self):
        "simple list"
        res = self.do([OPENlist(0),1,2,3,"a","b",CLOSE(0)])
        self.failUnlessEqual(res, [1,2,3,'a','b'])

    def test_aborted_list(self):
        "aborted list"
        res = self.do([OPENlist(0), 1, ABORT, CLOSE(0)])
        self.assertUnbananaFailure(res, "root.[1]")

    def test_aborted_list2(self):
        "aborted list2"
        res = self.do([OPENlist(0), 1, ABORT,
                       OPENlist(1), 2, 3, CLOSE(1),
                       CLOSE(0)])
        self.assertUnbananaFailure(res, "root.[1]")

    def test_aborted_list3(self):
        "aborted list3"
        res = self.do([OPENlist(0), 1, 
                        OPENlist(1), 2, 3, 4,
                         OPENlist(2), 5, 6, ABORT, CLOSE(2),
                        CLOSE(1),
                       CLOSE(0)])
        self.assertUnbananaFailure(res, "root.[1].[3].[2]")

    def test_nested_list(self):
        "nested list"
        res = self.do([OPENlist(0),1,2,OPENlist(1),3,4,CLOSE(1),CLOSE(0)])
        self.failUnlessEqual(res, [1,2,[3,4]])

    def test_list_with_tuple(self):
        "list with tuple"
        res = self.do([OPENlist(0),1,2,OPENtuple(1),3,4,CLOSE(1),CLOSE(0)])
        self.failUnlessEqual(res, [1,2,(3,4)])

    def test_dict(self):
        "dict"
        res = self.do([OPENdict(0),"a",1,"b",2,CLOSE(0)])
        self.failUnlessEqual(res, {'a':1, 'b':2})
        
    def test_dict_with_duplicate_keys(self):
        "dict with duplicate keys"
        res = self.do([OPENdict(0),"a",1,"a",2,CLOSE(0)])
        self.assertUnbananaFailure(res, "root.{}")
        
    def test_dict_with_list(self):
        "dict with list"
        res = self.do([OPENdict(0),
                        "a",1,
                        "b", OPENlist(1), 2, 3, CLOSE(1),
                       CLOSE(0)])
        self.failUnlessEqual(res, {'a':1, 'b':[2,3]})
        
    def test_dict_with_tuple_as_key(self):
        "dict with tuple as key"
        res = self.do([OPENdict(0),
                        OPENtuple(1), 1, 2, CLOSE(1), "a",
                       CLOSE(0)])
        self.failUnlessEqual(res, {(1,2):'a'})
        
    def test_dict_with_mutable_key(self):
        "dict with mutable key"
        res = self.do([OPENdict(0),
                        OPENlist(1), 1, 2, CLOSE(1), "a",
                       CLOSE(0)])
        self.assertUnbananaFailure(res, "root.{}")

    def test_instance(self):
        "instance"
        f1 = Dummy(); f1.a = 1; f1.b = [2,3]
        f2 = Dummy(); f2.d = 4; f1.c = f2
        res = self.do([OPENinstance(0), "Foo", "a", 1,
                       "b", OPENlist(1), 2, 3, CLOSE(1),
                       "c", OPENinstance(2), "Bar", "d", 4, CLOSE(2),
                       CLOSE(0)])
        self.failUnlessEqual(res, f1)
        
    def test_instance_bad1(self):
        "subinstance with numeric classname"
        res = self.do([OPENinstance(0), "Foo", "a", 1,
                       "b", OPENlist(1), 2, 3, CLOSE(1),
                       "c", OPENinstance(2), 31337, "d", 4, CLOSE(2),
                       CLOSE(0)])
        self.assertUnbananaFailure(res, "root.<Foo>.c.<??>")

    def test_ref1(self):
        res = self.do([OPENlist(0),
                        OPENlist(1), 1, 2, CLOSE(1),
                        OPENref(2), 1, CLOSE(2),
                       CLOSE(0)])
        self.failIfUnbananaFailure(res)
        self.failUnlessEqual(res, [[1,2], [1,2]])
        self.failUnlessIdentical(res[0], res[1])

    def test_ref2(self):
        res = self.do([OPENlist(0),
                       OPENlist(1), 1, 2, CLOSE(1),
                       OPENref(2), 0, CLOSE(2),
                       CLOSE(0)])
        self.failIfUnbananaFailure(res)
        wanted = [[1,2]]
        wanted.append(wanted)
        self.failUnlessEqual(res, wanted)
        self.failUnlessIdentical(res, res[1])

    def test_ref3(self):
        res = self.do([OPENlist(0),
                        OPENtuple(1), 1, 2, CLOSE(1),
                        OPENref(2), 1, CLOSE(2),
                       CLOSE(0)])
        self.failIfUnbananaFailure(res)
        wanted = [(1,2)]
        wanted.append(wanted[0])
        self.failUnlessEqual(res, wanted)
        self.failUnlessIdentical(res[0], res[1])

    def test_ref4(self):
        res = self.do([OPENlist(0),
                        OPENdict(1), "a", 1, CLOSE(1),
                        OPENref(2), 1, CLOSE(2),
                       CLOSE(0)])
        self.failIfUnbananaFailure(res)
        wanted = [{"a":1}]
        wanted.append(wanted[0])
        self.failUnlessEqual(res, wanted)
        self.failUnlessIdentical(res[0], res[1])

    def test_ref5(self):
        # The Droste Effect: a list that contains itself
        res = self.do([OPENlist(0),
                        5,
                        6,
                        OPENref(1), 0, CLOSE(1),
                        7,
                       CLOSE(0)])
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
        res = self.do([OPENtuple(0),
                        OPENlist(1),
                         OPENtuple(2),
                          OPENref(3), 0, CLOSE(3),
                         CLOSE(2),
                        CLOSE(1),
                       CLOSE(0)])
        self.failIfUnbananaFailure(res)
        wanted = ([],)
        wanted[0].append((wanted,))
        self.failUnlessEqual(res, wanted)
        self.failUnlessIdentical(res[0][0][0], res)

        # need a test where tuple[0] and [1] are deferred, but tuple[0]
        # becomes available before tuple[2] is inserted. Not sure this is
        # possible, but it would improve test coverage in TupleUnslicer
        
class FailureTests(UnbananaTestMixin, unittest.TestCase):
    def setUp(self):
        UnbananaTestMixin.setUp(self)
        
    def test_dict1(self):
        # dies during open because of bad opentype
        res = self.do([OPENlist(0), 1,
                       ("OPEN", "die", 1), "a", 2, "b", 3, CLOSE(1),
                       CLOSE(0)])
        self.assertUnbananaFailure(res, "root.[1].<OPENdie>", KeyError)
    def test_dict2(self):
        # dies during start
        res = self.do([OPENlist(0), 1,
                       OPENdict2(1), "a", 2, "b", 3, CLOSE(1),
                       CLOSE(0)])
        self.assertUnbananaFailure(res, "root.[1].{}.<START>",
                                   "dead in start")
    def test_dict3(self):
        # dies during key
        res = self.do([OPENlist(0), 1,
                       OPENdict1(1), "a", 2, "die", CLOSE(1),
                       CLOSE(0)])
        self.assertUnbananaFailure(res, "root.[1].{}", "aaaaaaaaargh")
    def test_dict4(self):
        # dies during value
        res = self.do([OPENlist(0), 1,
                       OPENdict1(1), "a", 2, "b", "die", CLOSE(1),
                       CLOSE(0)])
        self.assertUnbananaFailure(res, "root.[1].{}[b]", "aaaaaaaaargh")
    def test_dict5(self):
        # dies during receiveChild
        res = self.do([OPENlist(0), 1,
                        OPENdict1(1),
                         "please_die_in_receiveChild", 2,
                         "a", OPENlist(2), 3, 4, CLOSE(2),
                        CLOSE(1),
                       CLOSE(0)])
        self.assertUnbananaFailure(res, "root.[1].{}[a]",
                                   "dead in receiveChild")
        
    def test_dict6(self):
        # dies during finish
        res = self.do([OPENlist(0), 1,
                        OPENdict1(1),
                         "a", 2,
                         "please_die_in_finish", 3,
                        CLOSE(1),
                       CLOSE(0)])
        self.assertUnbananaFailure(res, "root.[1].{}.<CLOSE>",
                                   "dead in receiveClose()")
        
class BananaTests(unittest.TestCase):
    def setUp(self):
        self.banana = TokenBanana()
    def do(self, obj):
        return self.banana.testSlice(obj)
    def tearDown(self):
        self.failUnless(len(self.banana.slicerStack) == 1)
        self.failUnless(isinstance(self.banana.slicerStack[0], RootSlicer))

    def testList(self):
        res = self.do([1,2])
        self.failUnlessEqual(res, [OPENlist(0), 1, 2, CLOSE(0)])
    def testTuple(self):
        res = self.do((1,2))
        self.failUnlessEqual(res, [OPENtuple(0), 1, 2, CLOSE(0)])
    def testNestedList(self):
        res = self.do([1,2,[3,4]])
        self.failUnlessEqual(res, [OPENlist(0), 1, 2,
                                    OPENlist(1), 3, 4, CLOSE(1),
                                   CLOSE(0)])
    def testNestedList2(self):
        res = self.do([1,2,(3,4,[5, "hi"])])
        self.failUnlessEqual(res, [OPENlist(0), 1, 2,
                                    OPENtuple(1), 3, 4,
                                     OPENlist(2), 5, "hi", CLOSE(2),
                                    CLOSE(1),
                                   CLOSE(0)])

    def testDict(self):
        res = self.do({'a': 1, 'b': 2})
        self.failUnless(
            res == [OPENdict(0), 'a', 1, 'b', 2, CLOSE(0)] or
            res == [OPENdict(0), 'b', 2, 'a', 1, CLOSE(0)])
    def test_ref1(self):
        l = [1,2]
        obj = [l,l]
        res = self.do(obj)
        self.failUnlessEqual(res, [OPENlist(0),
                                    OPENlist(1), 1, 2, CLOSE(1),
                                    OPENref(2), 1, CLOSE(2),
                                   CLOSE(0)])

    def test_ref2(self):
        obj = [[1,2]]
        obj.append(obj)
        res = self.do(obj)
        self.failUnlessEqual(res, [OPENlist(0),
                                    OPENlist(1), 1, 2, CLOSE(1),
                                    OPENref(2), 0, CLOSE(2),
                                   CLOSE(0)])

    def test_ref3(self):
        obj = [(1,2)]
        obj.append(obj[0])
        res = self.do(obj)
        self.failUnlessEqual(res, [OPENlist(0),
                                    OPENtuple(1), 1, 2, CLOSE(1),
                                    OPENref(2), 1, CLOSE(2),
                                   CLOSE(0)])

    def test_ref4(self):
        obj = [{"a":1}]
        obj.append(obj[0])
        res = self.do(obj)
        self.failUnlessEqual(res, [OPENlist(0),
                                    OPENdict(1), "a", 1, CLOSE(1),
                                    OPENref(2), 1, CLOSE(2),
                                   CLOSE(0)])

    def test_ref6(self):
        # everybody's favorite "([(ref0" test case.
        obj = ([],)
        obj[0].append((obj,))
        res = self.do(obj)
        self.failUnlessEqual(res,
                             [OPENtuple(0),
                               OPENlist(1),
                                OPENtuple(2),
                                 OPENref(3), 0, CLOSE(3),
                                CLOSE(2),
                               CLOSE(1),
                              CLOSE(0)])

class Bar:
    def __cmp__(self, other):
        if not type(other) == type(self):
            return -1
        return cmp(self.__dict__, other.__dict__)
class Foo(Bar):
    pass

class BananaInstanceTests(unittest.TestCase):
    def setUp(self):
        self.banana = TokenBanana()
    def do(self, obj):
        return self.banana.testSlice(obj)
    def tearDown(self):
        self.failUnless(len(self.banana.slicerStack) == 1)
        self.failUnless(isinstance(self.banana.slicerStack[0], RootSlicer))
    
    def test_one(self):
        obj = Bar()
        obj.a = 1
        classname = reflect.qual(Bar)
        res = self.do(obj)
        self.failUnlessEqual(res,
                             [OPENinstance(0), classname, "a", 1, CLOSE(0)])
    def test_two(self):
        f1 = Foo(); f1.a = 1; f1.b = [2,3]
        f2 = Bar(); f2.d = 4; f1.c = f2
        fooname = reflect.qual(Foo)
        barname = reflect.qual(Bar)
        # needs OrderedDictSlicer for the test to work
        res = self.do(f1)
        self.failUnlessEqual(res,
                             [OPENinstance(0), fooname,
                               "a", 1,
                               "b", OPENlist(1), 2, 3, CLOSE(1),
                               "c",
                                 OPENinstance(2), barname,
                                  "d", 4,
                                 CLOSE(2),
                              CLOSE(0)])

class TestBananaMixin:
    def setUp(self):
        self.banana = TestBanana()
        self.banana.transport = cStringIO.StringIO()

    def encode(self, obj):
        self.banana.send(obj)
        return self.banana.transport.getvalue()

    def clearOutput(self):
        self.banana.transport = cStringIO.StringIO()

    def decode(self, str):
        self.banana.object = None
        self.banana.dataReceived(str)
        obj = self.banana.object
        self.banana.object = None
        return obj

    def wantEqual(self, got, wanted):
        if got != wanted:
            print
            print "wanted: '%s'" % wanted
            print "got   : '%s'" % got
            self.fail("did not get expected string")

    def loop(self, obj):
        return self.decode(self.encode(obj))
    def looptest(self, obj):
        obj2 = self.loop(obj)
        if isinstance(obj2, UnbananaFailure):
            print obj2.failure.getTraceback()
            self.fail("UnbananaFailure at %s" % obj2.where)
        self.failUnlessEqual(obj2, obj)

    def OPEN(self, opentype, count):
        assert count < 128
        return chr(count) + "\x88" + chr(len(opentype)) + "\x82" + opentype
    def CLOSE(self, count):
        assert count < 128
        return chr(count) + "\x89"
    def INT(self, num):
        assert num < 128
        return chr(num) + "\x81"
    def STR(self, str):
        assert len(str) < 128
        return chr(len(str)) + "\x82" + str

class ByteStream(TestBananaMixin, unittest.TestCase):

    def test_list(self):
        obj = [1,2]
        expected = "".join([self.OPEN("list", 0),
                            self.INT(1), self.INT(2),
                            self.CLOSE(0),
                            ])
        self.wantEqual(self.encode(obj), expected)

    def test_ref6(self):
        # everybody's favorite "([(ref0" test case.
        obj = ([],)
        obj[0].append((obj,))
        OPEN = self.OPEN; CLOSE = self.CLOSE; INT = self.INT; STR = self.STR
        expected = "".join([OPEN("tuple",0),
                             OPEN("list",1),
                              OPEN("tuple",2),
                               OPEN("reference",3),
                                INT(0),
                               CLOSE(3),
                              CLOSE(2),
                             CLOSE(1),
                            CLOSE(0)])
        self.wantEqual(self.encode(obj), expected)

    def test_two(self):
        f1 = Foo(); f1.a = 1; f1.b = [2,3]
        f2 = Bar(); f2.d = 4; f1.c = f2
        fooname = reflect.qual(Foo)
        barname = reflect.qual(Bar)
        # needs OrderedDictSlicer for the test to work
        OPEN = self.OPEN; CLOSE = self.CLOSE; INT = self.INT; STR = self.STR

        expected = "".join([OPEN("instance",0), STR(fooname),
                             STR("a"), INT(1),
                             STR("b"),
                              OPEN("list",1),
                               INT(2), INT(3),
                               CLOSE(1),
                             STR("c"),
                               OPEN("instance",2), STR(barname),
                                STR("d"), INT(4),
                               CLOSE(2),
                            CLOSE(0)])
        self.wantEqual(self.encode(f1), expected)


class TestBanana(Banana):
    slicerClass = RootSlicer2
    unslicerClass = RootUnslicer2
    def receivedObject(self, obj):
        self.object = obj

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
    def test_string(self):
        self.looptest("biggles")
    def test_list(self):
        self.looptest([1,2])
    def test_tuple(self):
        self.looptest((1,2))

    # some stuff from test_newjelly
    def testIdentity(self):
        """
        test to make sure that objects retain identity properly
        """
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
        a.append((t,))
        s = self.encode(t)
        z = self.decode(s)
        self.assertIdentical(z[0][0][0], z)

    def testLotsaTypes(self):
        """
        test for all types currently supported in jelly
        """
        a = A()
        self.looptest(a)
        self.looptest(A)
        self.looptest(a.amethod)
        items = [afunc, [1, 2, 3], not bool(1), bool(1), 'test', 20.3, (1,2,3), None, A, unittest, {'a':1}, A.amethod]
        for i in items:
            self.looptest(i)
    #testLotsaTypes.skip = "not all types are implemented yet"

        
class VocabTest1(unittest.TestCase):
    def test_incoming1(self):
        b = TokenBanana()
        vdict = {1: 'list', 2: 'tuple', 3: 'dict'}
        keys = vdict.keys()
        keys.sort()
        setVdict = [OPEN('vocab', 0)]
        for k in keys:
            setVdict.append(k)
            setVdict.append(vdict[k])
        setVdict.append(CLOSE(0))
        b.processTokens(setVdict)
        # banana should now know this vocabulary
        self.failUnlessEqual(b.incomingVocabulary, vdict)

    def test_outgoing(self):
        b = TokenBanana()
        vdict = {1: 'list', 2: 'tuple', 3: 'dict'}
        keys = vdict.keys()
        keys.sort()
        setVdict = [OPEN('vocab', 0)]
        for k in keys:
            setVdict.append(k)
            setVdict.append(vdict[k])
        setVdict.append(CLOSE(0))
        b.tokens = []
        b.setOutgoingVocabulary(vdict)
        vocabTokens = b.tokens
        b.tokens = []
        self.failUnlessEqual(vocabTokens, setVdict)
        # banana should now know this vocabulary

class VocabTest2(TestBananaMixin, unittest.TestCase):
    def OPEN(self, opentype, count):
        num = self.invdict[opentype]
        return chr(count) + "\x88" + chr(num) + "\x87"
    def CLOSE(self, count):
        return chr(count) + "\x89"
    
    def test_loop(self):
        vdict = {1: 'list', 2: 'tuple', 3: 'dict'}
        self.invdict = dict(zip(vdict.values(), vdict.keys()))

        self.banana.setOutgoingVocabulary(vdict)
        self.failUnlessEqual(self.banana.outgoingVocabulary, self.invdict)
        self.decode(self.banana.transport.getvalue())
        self.failUnlessEqual(self.banana.incomingVocabulary, vdict)
        self.clearOutput()
        s = self.encode([({'a':1},)])

        OPEN = self.OPEN; CLOSE = self.CLOSE; INT = self.INT; STR = self.STR
        expected = "".join([OPEN("list", 0),
                             OPEN("tuple", 1),
                              OPEN("dict", 2),
                               STR('a'), INT(1),
                              CLOSE(2),
                             CLOSE(1),
                            CLOSE(0)])
        self.wantEqual(s, expected)
        
        
def encode(obj, debug=0):
    b = TokenBanana()
    b.debug = debug
    return b.testSlice(obj)
def decode(tokens, debug=0):
    b = TokenBanana()
    b.debug = debug
    obj = b.processTokens(tokens)
    return obj
