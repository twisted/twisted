#! /usr/bin/python

from twisted.trial import unittest
from twisted.python import reflect
from banana import Banana, BananaError
import slicer, schema, tokens
from slicer import Dummy, UnbananaFailure
from slicer import RootSlicer, RootSlicer2
from slicer import RootUnslicer

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
        # insert artificial tokens into receiveData. Once upon a time this
        # worked by directly calling the commented-out functions, but schema
        # checking and abandonUnslicer made that unfeasible.

        #if self.debug:
        #    print "receiveToken(%s)" % (token,)

        if type(token) == type(()):
            if token[0] == "OPEN":
                count = token[2]
                opentype = token[1]
                assert count < 128
                assert len(opentype) < 128
                b = ( chr(count) + tokens.OPEN +
                      chr(len(opentype)) + tokens.STRING + opentype )
                self.dataReceived(b)
                #self.handleOpen(count, opentype)
            elif token[0] == "CLOSE":
                count = token[1]
                assert count < 128
                b = chr(count) + tokens.CLOSE
                self.dataReceived(b)
                #self.handleClose(count)
            elif token[0] == "ABORT":
                if len(token) == 2:
                    count = token[1]
                else:
                    count = 0
                assert count < 128
                b = chr(count) + tokens.ABORT
                self.dataReceived(b)
                #self.handleAbort(count)
        elif type(token) == int:
            assert 0 <= token < 128
            b = chr(token) + tokens.INT
            self.dataReceived(b)
        elif type(token) == str:
            assert len(token) < 128
            b = chr(len(token)) + tokens.STRING + token
            self.dataReceived(b)
        else:
            raise NotImplementedError, "hey, this is just a quick hack"

    def receivedObject(self, obj):
        self.object = obj

    def processTokens(self, tokens):
        self.object = None
        for t in tokens:
            self.receiveToken(t)
        return self.object

class UnbananaTestMixin:
    def setUp(self):
        self.hangup = False
        self.banana = TokenBanana()
    def tearDown(self):
        if not self.hangup:
            self.failUnless(len(self.banana.receiveStack) == 1)
            self.failUnless(isinstance(self.banana.receiveStack[0],
                                       RootUnslicer))
            
    def do(self, tokens):
        return self.banana.processTokens(tokens)

    def failIfUnbananaFailure(self, res):
        if isinstance(res, UnbananaFailure):
            # something went wrong
            print "There was a failure while Unbananaing '%s':" % res.where
            print res.failure.getTraceback()
            self.fail("UnbananaFailure")

    def assertRaisesBananaError(self, where, f, *args):
        try:
            f(*args)
        except Exception, e:
            if not isinstance(e, BananaError):
                print "wrong exception type: %s" % e
                raise
            if where != None:
                if e.where != where:
                    print "e.where", e.where
                    print "where", where
                    self.fail("BananaError '%s' didn't occur at '%s'" % \
                              (e, where))
        self.hangup = True # to stop the tearDown check

    def checkUnbananaFailure(self, res, where, failtype=None):
        self.failUnless(isinstance(res, UnbananaFailure))
        if failtype:
            self.failUnless(res.failure,
                            "No Failure object in UnbananaFailure")
            if not res.failure.check(failtype):
                print "Wrong exception (wanted '%s'):" % failtype
                print res.failure.getTraceback()
                self.fail("Wrong exception (wanted '%s'):" % failtype)
        self.failUnlessEqual(res.where, where)
        self.banana.object = None # to stop the tearDown check TODO ??
        
class UnbananaTestCase(UnbananaTestMixin, unittest.TestCase):
        
    def test_simple_list(self):
        "simple list"
        res = self.do([OPENlist(0),1,2,3,"a","b",CLOSE(0)])
        self.failUnlessEqual(res, [1,2,3,'a','b'])

    def test_aborted_list(self):
        "aborted list"
        res = self.do([OPENlist(0), 1, ABORT, CLOSE(0)])
        self.checkUnbananaFailure(res, "root.[1]")

    def test_aborted_list2(self):
        "aborted list2"
        res = self.do([OPENlist(0), 1, ABORT,
                       OPENlist(1), 2, 3, CLOSE(1),
                       CLOSE(0)])
        self.checkUnbananaFailure(res, "root.[1]")

    def test_aborted_list3(self):
        "aborted list3"
        res = self.do([OPENlist(0), 1, 
                        OPENlist(1), 2, 3, 4,
                         OPENlist(2), 5, 6, ABORT, CLOSE(2),
                        CLOSE(1),
                       CLOSE(0)])
        self.checkUnbananaFailure(res, "root.[1].[3].[2]")

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
        self.assertRaisesBananaError("root.{}",
                                     self.do,
                                     [OPENdict(0),"a",1,"a",2,CLOSE(0)])
        
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
        self.assertRaisesBananaError("root.{}",
                                     self.do,
                                     [OPENdict(0),
                                       OPENlist(1), 1, 2, CLOSE(1), "a",
                                      CLOSE(0)])

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
        self.assertRaisesBananaError("root.<Foo>.c.<??>",
                                     self.do,
                                     [OPENinstance(0), "Foo",
                                      "a", 1,
                                      "b", OPENlist(1), 2, 3, CLOSE(1),
                                      "c",
                                      OPENinstance(2), 37, "d", 4, CLOSE(2),
                                      CLOSE(0)])
    def test_instance_bad2(self):
        "subinstance with numeric attribute name"
        self.assertRaisesBananaError("root.<Foo>.c.<Bar>.attrname??",
                                     self.do,
                                     [OPENinstance(0), "Foo",
                                      "a", 1,
                                      "b", OPENlist(1), 2, 3, CLOSE(1),
                                      "c",
                                      OPENinstance(2), "Bar", 37, 4, CLOSE(2),
                                      CLOSE(0)])

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
        self.assertRaisesBananaError("root.[1].<OPEN(('bad',))>",
                                     self.do,
                                     [OPENlist(0), 1,
                                       ("OPEN", "bad", 1),
                                        "a", 2,
                                        "b", 3,
                                       CLOSE(1),
                                      CLOSE(0)])

    def test_dict2(self):
        # dies during start
        self.assertRaisesBananaError("root.[1].{}.<START>",
                                     self.do,
                                     [OPENlist(0), 1,
                                      OPENdict2(1), "a", 2, "b", 3, CLOSE(1),
                                      CLOSE(0)])
        #"dead in start"

    def test_dict3(self):
        # dies during key
        self.assertRaisesBananaError("root.[1].{}",
                                     self.do,
                                     [OPENlist(0), 1,
                                      OPENdict1(1), "a", 2, "die", CLOSE(1),
                                      CLOSE(0)])
        #"aaaaaaaaargh"

    def test_dict4(self):
        # dies during value
        self.assertRaisesBananaError("root.[1].{}[b].<receiveChild(die)>",
                                     self.do,
                                     [OPENlist(0), 1,
                                       OPENdict1(1),
                                        "a", 2,
                                        "b", "die",
                                       CLOSE(1),
                                      CLOSE(0)])
        # "aaaaaaaaargh"
        
    def test_dict5(self):
        # dies during finish
        self.assertRaisesBananaError("root.[1].{}.<CLOSE>",
                                     self.do,
                                     [OPENlist(0), 1,
                                       OPENdict1(1),
                                        "a", 2,
                                        "please_die_in_finish", 3,
                                       CLOSE(1),
                                      CLOSE(0)])
        # "dead in receiveClose()"
        
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

    def test_refdict1(self):
        # a dictionary with a value that isn't available right away
        d = {1: "a"}
        t = (d,)
        d[2] = t
        res = self.do(d)
        self.failUnlessEqual(res,
                             [OPENdict(0),
                               1, "a",
                               2, OPENtuple(1),
                                   OPENref(2), 0, CLOSE(2),
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
        self.failUnlessEqual(type(obj2), type(obj))

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

def join(*args):
    return "".join(args)

class ByteStream(TestBananaMixin, unittest.TestCase):

    def test_list(self):
        obj = [1,2]
        expected = join(self.OPEN("list", 0),
                         self.INT(1), self.INT(2),
                        self.CLOSE(0),
                        )
        self.wantEqual(self.encode(obj), expected)

    def test_ref6(self):
        # everybody's favorite "([(ref0" test case.
        obj = ([],)
        obj[0].append((obj,))
        OPEN = self.OPEN; CLOSE = self.CLOSE; INT = self.INT; STR = self.STR
        expected = join(OPEN("tuple",0),
                         OPEN("list",1),
                          OPEN("tuple",2),
                           OPEN("reference",3),
                            INT(0),
                           CLOSE(3),
                          CLOSE(2),
                         CLOSE(1),
                        CLOSE(0))
        self.wantEqual(self.encode(obj), expected)

    def test_two(self):
        f1 = Foo(); f1.a = 1; f1.b = [2,3]
        f2 = Bar(); f2.d = 4; f1.c = f2
        fooname = reflect.qual(Foo)
        barname = reflect.qual(Bar)
        # needs OrderedDictSlicer for the test to work
        OPEN = self.OPEN; CLOSE = self.CLOSE; INT = self.INT; STR = self.STR

        expected = join(OPEN("instance",0), STR(fooname),
                         STR("a"), INT(1),
                         STR("b"),
                          OPEN("list",1),
                           INT(2), INT(3),
                          CLOSE(1),
                         STR("c"),
                           OPEN("instance",2), STR(barname),
                            STR("d"), INT(4),
                           CLOSE(2),
                        CLOSE(0))
        self.wantEqual(self.encode(f1), expected)

class InboundByteStream(unittest.TestCase):

    def OPEN(self, opentype, count):
        assert count < 128
        assert len(opentype) < 128
        return chr(count) + "\x88" + \
               chr(len(opentype)) + "\x82" + opentype
    def OPENlist(self, count):
        return self.OPEN("list", count)
    def OPENtuple(self, count):
        return self.OPEN("tuple", count)
    def OPENdict(self, count):
        return self.OPEN("dict", count)
    def OPENinstance(self, count):
        return self.OPEN("instance", count)
    def OPENref(self, count):
        return self.OPEN("reference", count)
    def CLOSE(self, count):
        assert count < 128
        return chr(count) + "\x89"
    def INT(self, num):
        if num >=0:
            assert num < 128
            return chr(num) + "\x81"
        num = -num
        assert num < 128
        return chr(num) + "\x83"
    def STRING(self, string):
        assert len(string) < 128
        return chr(len(string)) + "\x82" + string

    def decode(self, string):
        banana = TestBanana()
        banana.object = None
        banana.dataReceived(string)
        return banana.object
    def check(self, obj, stream):
        obj2 = self.decode(stream)
        self.failUnlessEqual(obj, obj2)

    def testInt(self):
        self.check(1, "\x01\x81")
        self.check(130, "\x02\x01\x81")
        self.check(-1, "\x01\x83")
        self.check(-130, "\x02\x01\x83")
        self.check(0, self.INT(0))
        self.check(1, self.INT(1))
        self.check(127, self.INT(127))
        self.check(-1, self.INT(-1))
        self.check(-127, self.INT(-127))

    def testLong(self):
        self.check(258L, "\x02\x85\x01\x02") # TODO: 0x85 for LONGINT??
        self.check(-258L, "\x02\x86\x01\x02") # TODO: 0x85 for LONGINT??

    def testString(self):
        self.check("", "\x82")
        self.check("", "\x00\x82")
        self.check("", "\x00\x00\x82")
        self.check("", "\x00" * 64 + "\x82")
        self.assertRaises(BananaError, self.decode, "\x00" * 65)
        #self.decode("\x00" * 65 + "\x82")
        self.assertRaises(BananaError, self.decode, "\x00" * 65 + "\x82")

        self.check("a", "\x01\x82a")
        self.check("b"*130, "\x02\x01\x82" + "b"*130 + "extra")
        self.check("c"*1025, "\x01\x08\x82" + "c" * 1025 + "extra")
        self.check("fluuber", self.STRING("fluuber"))

    def decode2(self, string, constraint, childConstraint=None):
        constraint = schema.makeConstraint(constraint)
        if childConstraint:
            childConstraint = schema.makeConstraint(childConstraint)
        banana = TestBanana()
        banana.receiveStack[-1].constraint = constraint
        banana.receiveStack[-1].childConstraint = childConstraint
        banana.object = None
        banana.dataReceived(string)
        return banana.object
    def conform2(self, stream, obj, constraint, childConstraint=None):
        obj2 = self.decode2(stream, constraint, childConstraint)
        if isinstance(obj2, UnbananaFailure):
            print "failure", obj2, obj2.failure
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

    def testList(self):
        self.check([1,2],
                   join(self.OPENlist(1), self.INT(1), self.INT(2),
                        self.CLOSE(1)))
        self.check([1,"b"],
                   join(self.OPENlist(1), self.INT(1),
                        "\x01\x82b",
                        self.CLOSE(1)))
        self.check([1,2,[3,4]],
                   join(self.OPENlist(1), self.INT(1), self.INT(2),
                         self.OPENlist(2), self.INT(3), self.INT(4),
                         self.CLOSE(2),
                        self.CLOSE(1)))

    def testConstrainedList(self):
        self.conform2(join(self.OPENlist(1), self.INT(1), self.INT(2),
                           self.CLOSE(1)),
                      [1,2],
                      schema.ListOf(int))
        self.violate2(join(self.OPENlist(1), self.INT(1), "\x01\x82b",
                           self.CLOSE(1)),
                      "root.[1]",
                      schema.ListOf(int))
        self.conform2(join(self.OPENlist(1),
                            self.INT(1), self.INT(2), self.INT(3),
                           self.CLOSE(1)),
                      [1,2,3],
                      schema.ListOf(int, maxLength=3))
        self.violate2(join(self.OPENlist(1),
                            self.INT(1), self.INT(2), self.INT(3), self.INT(4),
                           self.CLOSE(1)),
                      "root.[3]",
                      schema.ListOf(int, maxLength=3))
        a100 = chr(100) + "\x82" + "a"*100
        b100 = chr(100) + "\x82" + "b"*100
        self.conform2(join(self.OPENlist(1), a100, b100, self.CLOSE(1)),
                      ["a"*100, "b"*100],
                      schema.ListOf(schema.StringConstraint(100), 2))
        self.violate2(join(self.OPENlist(1), a100, b100, self.CLOSE(1)),
                      "root.[0]",
                      schema.ListOf(schema.StringConstraint(99), 2))
        self.violate2(join(self.OPENlist(1), a100, b100, a100, self.CLOSE(1)),
                      "root.[2]",
                      schema.ListOf(schema.StringConstraint(100), 2))

        self.conform2(join(self.OPENlist(1),
                            self.OPENlist(2),
                             self.INT(11), self.INT(12),
                            self.CLOSE(2),
                            self.OPENlist(3),
                             self.INT(21), self.INT(22), self.INT(23),
                            self.CLOSE(3),
                           self.CLOSE(1)),
                      [[11,12], [21, 22, 23]],
                      schema.ListOf(schema.ListOf(int, maxLength=3)))

        self.violate2(join(self.OPENlist(1),
                            self.OPENlist(2),
                             self.INT(11), self.INT(12),
                            self.CLOSE(2),
                            self.OPENlist(3),
                             self.INT(21), self.INT(22), self.INT(23),
                            self.CLOSE(3),
                           self.CLOSE(1)),
                      "root.[1].[2]",
                      schema.ListOf(schema.ListOf(int, maxLength=2)))

    def testTuple(self):
        self.check((1,2),
                   join(self.OPENtuple(1), self.INT(1), self.INT(2),
                        self.CLOSE(1)))

    def testConstrainedTuple(self):
        self.conform2(join(self.OPENtuple(1), self.INT(1), self.INT(2),
                           self.CLOSE(1)),
                      (1,2),
                      schema.TupleOf(int, int))
        self.violate2(join(self.OPENtuple(1),
                           self.INT(1), self.INT(2), self.INT(3),
                           self.CLOSE(1)),
                      "root.[2]",
                      schema.TupleOf(int, int))
        self.violate2(join(self.OPENtuple(1),
                           self.INT(1), self.STRING("not a number"),
                           self.CLOSE(1)),
                      "root.[1]",
                      schema.TupleOf(int, int))
        self.conform2(join(self.OPENtuple(1),
                           self.INT(1), self.STRING("twine"),
                           self.CLOSE(1)),
                      (1, "twine"),
                      schema.TupleOf(int, str))
        self.conform2(join(self.OPENtuple(1),
                           self.INT(1),
                            self.OPENlist(2),
                             self.INT(1), self.INT(2), self.INT(3),
                            self.CLOSE(2),
                           self.CLOSE(1)),
                      (1, [1,2,3]),
                      schema.TupleOf(int, schema.ListOf(int)))
        self.conform2(join(self.OPENtuple(1),
                           self.INT(1),
                            self.OPENlist(2),
                             self.OPENlist(3), self.INT(2), self.CLOSE(3),
                             self.OPENlist(4), self.INT(3), self.CLOSE(4),
                            self.CLOSE(2),
                           self.CLOSE(1)),
                      (1, [[2], [3]]),
                      schema.TupleOf(int, schema.ListOf(schema.ListOf(int))))
        self.violate2(join(self.OPENtuple(1),
                           self.INT(1),
                            self.OPENlist(2),
                             self.OPENlist(3),
                              self.STRING("nan"),
                             self.CLOSE(3),
                             self.OPENlist(4), self.INT(3), self.CLOSE(4),
                            self.CLOSE(2),
                           self.CLOSE(1)),
                      "root.[1].[0].[0]",
                      schema.TupleOf(int, schema.ListOf(schema.ListOf(int))))

    def testDict(self):
        self.check({1:"a", 2:["b","c"]},
                   join(self.OPENdict(1),
                        self.INT(1), self.STRING("a"),
                        self.INT(2), self.OPENlist(2),
                         self.STRING("b"), self.STRING("c"),
                        self.CLOSE(2),
                        self.CLOSE(1)))

    def testConstrainedDict(self):
        self.conform2(join(self.OPENdict(1),
                           self.INT(1), self.STRING("a"),
                           self.INT(2), self.STRING("b"),
                           self.INT(3), self.STRING("c"),
                           self.CLOSE(1)),
                      {1:"a", 2:"b", 3:"c"},
                      schema.DictOf(int, str))
        self.conform2(join(self.OPENdict(1),
                           self.INT(1), self.STRING("a"),
                           self.INT(2), self.STRING("b"),
                           self.INT(3), self.STRING("c"),
                           self.CLOSE(1)),
                      {1:"a", 2:"b", 3:"c"},
                      schema.DictOf(int, str, maxKeys=3))
        self.violate2(join(self.OPENdict(1),
                           self.INT(1), self.STRING("a"),
                           self.INT(2), self.INT(10),
                           self.INT(3), self.STRING("c"),
                           self.CLOSE(1)),
                      "root.{}[2]",
                      schema.DictOf(int, str))
        self.violate2(join(self.OPENdict(1),
                           self.INT(1), self.STRING("a"),
                           self.INT(2), self.STRING("b"),
                           self.INT(3), self.STRING("c"),
                           self.CLOSE(1)),
                      "root.{}",
                      schema.DictOf(int, str, maxKeys=2))

    def TRUE(self):
        return join(self.OPEN("boolean",2), self.INT(1), self.CLOSE(2))
    def FALSE(self):
        return join(self.OPEN("boolean",2), self.INT(0), self.CLOSE(2))

    def testBool(self):
        self.check(True, self.TRUE())
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
        self.assertRaises(BananaError, self.decode2,
                          join(self.OPEN("boolean",1), self.STRING("vrai"),
                               self.CLOSE(1)),
                          schema.BooleanConstraint())
        self.violate2(self.TRUE(),
                      "root.<bool>",
                      schema.BooleanConstraint(False))
        self.violate2(self.FALSE(),
                      "root.<bool>",
                      schema.BooleanConstraint(True))


class ConstrainedRootUnslicer(RootUnslicer):
    openRegistry = slicer.UnslicerRegistry2
    topRegistry = slicer.UnslicerRegistry2

class TestBanana(Banana):
    slicerClass = RootSlicer2
    unslicerClass = ConstrainedRootUnslicer
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

def encode2(obj):
    b = TestBanana()
    b.transport = cStringIO.StringIO()
    b.send(obj)
    return b.transport.getvalue()
def decode2(string):
    b = TestBanana()
    b.dataReceived(string)
    return b.object
