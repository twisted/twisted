#! /usr/bin/python

from twisted.trial import unittest
from twisted.python import reflect
from unbanana import Unbanana, Dummy, UnbananaFailure, RootUnslicer
from banana import Banana, RootSlicer

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

class UnbananaTestMixin:
    def setUp(self):
        self.unbanana = Unbanana()
    def tearDown(self):
        self.failUnless(len(self.unbanana.stack) == 1)
        self.failUnless(isinstance(self.unbanana.stack[0], RootUnslicer))
            
    def do(self, tokens):
        return self.unbanana.processTokens(tokens)

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
        self.unbanana.object = None # to stop the tearDown check
        
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
        self.banana = Banana()
    def do(self, obj):
        return self.banana.testSlice(obj)
    def tearDown(self):
        self.failUnless(len(self.banana.stack) == 1)
        self.failUnless(isinstance(self.banana.stack[0], RootSlicer))

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
        self.banana = Banana()
    def do(self, obj):
        return self.banana.testSlice(obj)
    def tearDown(self):
        self.failUnless(len(self.banana.stack) == 1)
        self.failUnless(isinstance(self.banana.stack[0], RootSlicer))
    
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

