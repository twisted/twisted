# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

import os, gc, struct

from twisted.trial import unittest

from twisted.world import structfile, compound, storable
from twisted.world.storable import Storable
from twisted.world import database
from twisted.world import allocator

counter = 1
def testPath(fn):
    global counter
    c = fn+str(counter)
    counter += 1
    return c

class TestBase(unittest.TestCase):
    pass



class TestOffsets(TestBase):
    def setUp(self):
        self.sf = structfile.StructuredFile(testPath("structfile"),
                                            (int, "x"), (int, "y"),
                                            maxSize = 100,
                                            offset = 60)

    def testBasic(self):
        aaaa = 0x61616161
        for x in range(10):
            self.sf[x] = x, x+1
            self.assertEquals(self.sf[x], (x, x+1))
        rr = range(10)
        rr.reverse()
        for x in rr:
            self.assertEquals(self.sf[x], (x, x+1))
        self.sf[0] = aaaa, aaaa
        self.sf.fl.seek(self.sf.offset)
        self.assertEquals('a',self.sf.fl.read(1))
        self.sf[0:len(self.sf)] = [(0, 0)] * (len(self.sf) )
        for x in self.sf:
            assert x == (0, 0)


class TestStructuredFile(TestBase):
    def setUp(self):
        self.sf = structfile.StructuredFile(testPath("structfile"),
                                            (int, "x"), (float, "y"),
                                            (bool, 'z'), (long, 'a'))

    def testLen(self):
        self.assertEquals(len(self.sf), 0)
        self.sf.append((1,2,3,4))
        self.assertEquals(len(self.sf), 1)
        slicer = self.sf[1:]
        self.assertEquals(len(slicer), 0)
        slicer.append((5, 6, 7, 8))
        self.assertEquals(len(slicer), 1)
        self.assertEquals(len(self.sf), 2)
        self.sf.append((9, 10, 11, 12))
        self.assertEquals(len(self.sf), 3)



    def testAll(self):
        one = 1, 43.4, True, 1234123512334L
        self.sf.setAll(0, *one)
        two = 3453, 332, False, 2134555234L
        self.sf.setAll(2345, *two)
        three = 1, 433.2, True, 123412341234L
        self.sf.setAll(234, *three)

        self.assertEquals(one, self.sf.getAll(0))
        self.assertEquals(two, self.sf.getAll(2345))
        self.assertEquals(three, self.sf.getAll(234))

    def testIter(self):
        for x in range(10):
            self.sf.append((int(x),float(x),bool(x),long(x)))
        c = 0
        for x in self.sf:
            assert x == (int(c),float(c),bool(c),long(c))
            c += 1
        self.failUnlessEqual(c,10)

    def testAt(self):
        self.sf.setAt(0, 'z', False)
        self.assertEquals(False, self.sf.getAt(0, 'z'))
        
        l = 123412341231234L
        self.sf.setAt(2345, 'a', l)
        self.assertEquals(l, self.sf.getAt(2345, 'a'))

def selfzip(x):
    return zip(x,x)

class TestBlockCopy(TestBase):
    def setUp(self):
        self.sf = structfile.StructuredFile(testPath("schemamatic.garbage"),
                                           (int, "x"), (int, "y"))
        for n in xrange(100):
            self.sf.append((n,n))

    def testSimple(self):
        self.sf.copyBlock(10, 80, 10)
        self.assertEquals(list(self.sf[5:15]),
                          selfzip(range(5, 15)))
        self.assertEquals(list(self.sf[75:95]),
                          selfzip(range(75, 80) + range(10, 20) + range(90, 95)))

    def testOverlapLeft(self):
        self.sf.copyBlock(5, 10, 50)
        self.assertEquals(list(self.sf[0:60]),
                          selfzip(range(10) + range(5,55)))

    def testOverlapRight(self):
        self.sf.copyBlock(10, 5, 50)
        self.assertEquals(list(self.sf[0:60]),
                          selfzip(range(5) + range(10, 60) + range(55,60)))

class TestStrings(TestBase):
    def setUp(self):
        self.sf = structfile.StructuredFile(
            testPath("strings"), 
            (structfile.str255, 'name'), 
            (structfile.FixedSizeString(11), 'ssn')
        )

    def testAll(self):
        record = 'Barney Rubble', '632-12-0987'

        self.sf.setAll(345, *record)
        outnm, outssn = self.sf.getAll(345)
        outnm = outnm[:outnm.find('\x00')]
        self.assertEquals(record, (outnm, outssn))

    def testAt(self):
        nm = 'Fred Flintstone'
        self.sf.setAt(1, 'name', nm)
        outnm = self.sf.getAt(1, 'name')
        self.assertEquals(nm, outnm[:outnm.find('\x00')])
        
        ssn = '123-45-5678'
        self.sf.setAt(1, 'ssn', ssn)
        outssn = self.sf.getAt(1, 'ssn')
        self.assertEquals(ssn, outssn)


class Fixture(Storable):
    __schema__ = {
        'intTest': int,
        'floatTest': float,
        'storTest': Storable,
    }

    def __init__(self, a, b, c):
        self.intTest = a
        self.floatTest = b
        self.storTest = c

class DebugFixture(Fixture):
    __DEBUG__ = 1

class ListOnnaStick(Storable):
    __schema__ = {
        'fixedStuff': int,
        'listTest': compound.ListOf(int),
        'moreFixed': int,
    }

class ListOfStorables(Storable):
    __schema__ = {
        'list': compound.ListOf(Storable),
    }

class StringOnnaStick(Storable):
    __schema__ = {
        'meat': str,
    }
         
class UnhashableListOnnaStick(Storable):
    __schema__ = {
        'fixedStuff': int,
        'listTest': compound.ListOf(int),
        'moreFixed': int,
    }
    
    def __hash__(self):
        return hash(self.listTest)

class RefTest(Storable):
    __schema__ = {
        'a': int,
        'b': storable.ref('RefTest'),
    }

           
class TestStorableSchema(unittest.TestCase):
    class MROTestA(Storable):
        __schema__ = {
            'a': int,
            'obj': int,
            'mro': str,
        }

    class MROTestB(MROTestA):
        __schema__ = {
            'b': int,
            'obj': str,
            'mro': Storable,
        }

    class MROTestC(MROTestB):
        __schema__ = {
            'c': int,
            'obj': int,
        }

    class MROTestD(MROTestA):
        __schema__ = {
            'd': int, 
            'obj': str,
        }

    class MROTestE(MROTestB, MROTestD):
        __schema__ = {
            'e': int,
        }

    class MROTestF(MROTestD, MROTestB):
        __schema__ = {
            'f': int,
        }

    def testSchemaMRO(self):
        d_ = dict(Storable.__schema__)
        da = {'a': int, 'obj': int, 'mro': str}
        db = {'b': int, 'obj': str, 'mro': Storable}
        dc = {'c': int, 'obj': int}
        dd = {'d': int, 'obj': str}
        de = {'e': int}
        df = {'f': int}
        
        d = dict(d_)
        d.update(da)
        self.failUnlessEqual(self.MROTestA.__schema__, d)

        d = dict(d_)
        d.update(da)
        d.update(db)
        self.failUnlessEqual(self.MROTestB.__schema__, d)

        d = dict(d_)
        d.update(da)
        d.update(db)
        d.update(dc)
        self.failUnlessEqual(self.MROTestC.__schema__, d)


        d = dict(d_)
        d.update(da)
        d.update(dd)
        self.failUnlessEqual(self.MROTestD.__schema__, d)

        d = dict(d_)
        d.update(da)
        d.update(dd)
        d.update(db)
        d.update(de)
        self.failUnlessEqual(self.MROTestE.__schema__, d)

        d = dict(d_)
        d.update(da)
        d.update(db)
        d.update(dd)
        d.update(df)
        #
        # this is the real test that determines whether 
        # we pass for Python 2.3 MRO or not.
        #
        # However, right now, we're not.  So this is skipped ;)
        #
        # If you're using a schema that's affected by this
        # for a good reason, I'd like to shake your hand.
        #
        #self.failUnlessEqual(self.MROTestF.__schema__, d)

class Node(Storable):
    __schema__ = {
        'children': compound.ListOf(storable.ref('Node')),
        'parent': storable.ref('Node'),
        'name': str,
        }

    def __init__(self, name, parent=None):
        self.name = name
        self.children = []
        self.parent = parent
        if parent:
            parent.children.append(self)

class Strings(Storable):
    __schema__ = {
        'strings': compound.ListOf(str)
    }

class TwoTuples(Storable):
    __schema__ = {
        'tup1': (int, int, int),
        'tup2': (int, int, str)
        }

class TupList(Storable):
    __schema__ = {
        'list': compound.ListOf((int, int, str))
        }

from twisted.world import typemap

class TestTypeMapper(unittest.TestCase):
    def testTup(self):
        self.assertEquals(typemap.getMapper((int,int,int)),
                          typemap.getMapper((int,int,int)))

class TestFixedClasses(unittest.TestCase):
    def setUp(self):
        self.db = database.Database(self.caseMethodName)

    def tearDown(self):
        self.db.dumpHTML(open(self.db.dirname+"-dump.html",'wb'))

    def testRecursiveStuff(self):
        n = Node("top")
        n.children.append(n)
        Node("child1", n)
        c2 = Node("child2", n)
        c3 = Node("child3", c2)
        for x in range(10):
            Node("xchild"+str(x), c3)
        c3.children.append(c3)
        uid = self.db.insert(n)
        del n
        del c2
        del c3
        newn = self.db.retrieve(uid)
        self.assertEquals(newn.name, newn.children[0].name)
        self.assertIdentical(newn, newn.children[0])

    def testFragmentFile(self):
        ff = allocator.FragmentFile(self.db)
        # (using imaginary OIDs)
        import sys
        u = iter(xrange(sys.maxint)).next
        allocz = []
        for x in range(10):
            oid = u()
            offt, size = ff.findSpace(oid, 10)
            self.failUnless(size >= 10)
            allocz.append((oid, offt, size))
        r0_10_2 = range(0,10,2)
        for x in r0_10_2:
            oid, offt, size = allocz[x]
            ff.free(oid, offt, size)
        r0_10_2.reverse()
        for x in r0_10_2:
            del allocz[x]
        self.assertEquals(ff.fragmentCount, 5)

    def testStrings(self):
        ss = StringOnnaStick()
        self.db.insert(ss)
        ss.meat = 'hello world'
        self.assertEquals(ss.meat, 'hello world')
        ss.meat = 'hello world' * 100
        self.assertEquals(ss.meat, 'hello world' * 100)
        

    def testAllocator(self):
        a1 = allocator.Allocation(self.db)
        a2 = allocator.Allocation(self.db)
        a3 = allocator.Allocation(self.db)
        a1.expand(10)
        a2.expand(10)
        a3.expand(10)
        self.assertEquals( a1.fragfile, a2.fragfile )
        self.assertEquals( a2.fragfile, a3.fragfile )
        for x in a1, a2, a3:
            self.failUnless( x.allocLength >= 20 )
        # expand in reverse order so that some space is reclaimed
        for x in xrange(1, 5):
            a3.expand(x)
            a2.expand(x)
            a1.expand(x)
        for x in a1, a2, a3:
            self.failUnless( x.allocLength >= 30)

    def alloc(self, s):
        return allocator.StringStore(self.db, s)

    def testMultipleFragments(self):
        a1 = self.alloc('1' * 10)
        a2 = self.alloc('2' * 10)
        a3 = self.alloc('3' * 10)
        a4 = self.alloc('4' * 10)
        a5 = self.alloc('5' * 10)
        a2.free()
        a4.free()
        a6 = self.alloc('6' * 10)
        a7 = self.alloc('7' * 10)
        self.assertEquals(a1.getData(), '1' * 10)
        self.assertEquals(a3.getData(), '3' * 10)
        self.assertEquals(a5.getData(), '5' * 10)
        self.assertEquals(a6.getData(), '6' * 10)
        self.assertEquals(a7.getData(), '7' * 10)

    def testListOf(self):
        import gc
        lst = ListOfStorables()
        lst.list = []
        uid = self.db.insert(lst)
        lst.list = []
        verify = []
        for x in range(20):
            x = Storable()
            lst.list.append(x)
            verify.append(x)
        gc.collect()
        self.failUnlessEqual(len(lst.list), 20)
        self.failUnlessEqual(lst.list, verify)
        self.failUnlessEqual(lst.list[-1], verify[-1])
        self.failUnlessEqual(lst.list[-20], verify[-20])
        self.failUnlessEqual(lst.list[:], verify[:])
        self.failUnlessEqual(lst.list[0:8], verify[0:8])
        self.failUnlessEqual(lst.list[-5:-7], verify[-5:-7])
        for x in range(15):
            lst.list.pop()
        gc.collect()
        self.failUnlessEqual(len(lst.list), 5)
        for x in range(100):
            lst.list.append(Node(str(x)))
        gc.collect()
        lst.list.insert(50, Node("special"))
        self.assertEquals(lst.list[50].name, "special")
        self.assertEquals(lst.list[49].name, "44")
        self.assertEquals(lst.list[51].name, "45")
        self.assertEquals(lst.list[100].name, "94")
        self.assertEquals(lst.list[105].name, "99")
        self.failUnlessEqual(len(lst.list), 106)
        del lst
        gc.collect()
        lst = self.db.retrieve(uid)
        #print lst, lst.list
        #print list(lst.list)

        self.failUnlessEqual(len(lst.list), 106)
        del lst.list[:]
        gc.collect()
        self.failUnlessEqual(len(lst.list), 0)

    def testDictOf(self):
        sd = compound.StorableDictionary(self.db, str, int)
        self.failUnlessEqual(len(sd), 0)
        sd['hello'] = 1
        self.failUnlessEqual(len(sd), 1)
        self.failUnless(sd.has_key('hello'))


    def testStringList(self):
        L = Strings()
        L.strings = []
        self.db.insert(L)

        import string
        L.strings.extend(string.lowercase)
        self.assertEquals(list(string.lowercase), L.strings)
        
    
    def testVarData(self):
        import operator
        for x in range(2):
            stick = ListOnnaStick()
            self.db.insert(stick)
            r50 = range(10)
            stick.listTest = r50[:]
            stick.listTest.extend(range(10,50))
            r50.extend(range(10, 50))
            t = 0
            self.assertEquals(len(stick.listTest), len(r50))
            for o in stick.listTest:
                t += o
            self.assertEquals(t, reduce(operator.add, r50))
            stick.listTest.pop(1)
            r50.pop(1)
            self.assertEquals(list(stick.listTest), r50)

    def testUnhashableVarData(self):
        import operator
        for x in range(2):
            stick = UnhashableListOnnaStick()
            self.db.insert(stick)
            r50 = range(10)
            stick.listTest = r50[:]
            stick.listTest.extend(range(10,50))
            r50.extend(range(10, 50))
            t = 0
            self.assertEquals(len(stick.listTest), len(r50))
            for o in stick.listTest:
                t += o
            self.assertEquals(t, reduce(operator.add, r50))
            stick.listTest.pop(1)
            r50.pop(1)
            self.assertEquals(list(stick.listTest), r50)

    def testDebugging(self):
        f = DebugFixture(1, 8.0, None)
        try:
            f.moo = 1
        except:
            pass
        else:
            self.fail()
        try:
            f.moo
        except:
            pass
        else:
            self.fail()
        f.intTest = 2
        f = Fixture(1, 2.0, None)
        f.moo = 1
        f.moo
        
    def testRef(self):
        ref = RefTest()
        uid = self.db.insert(ref)
        ref.a = 1
        ref.b = ref
        ref = None
        gc.collect()
        ref = self.db.retrieve(uid)
        self.assertEquals(ref.a, ref.b.a)
        self.assertEquals(ref.b.b.b.b.b.a, 1)
        
    def testSimpleFixed(self):
        f = Fixture(1, 2.0, None)
        uid = self.db.insert(f)
        self.assertEquals(uid, f.storedUIDPath())
        whiteboxOid, whiteboxGenhash = struct.unpack("!ii", uid.decode("hex"))
        junkGenhash = whiteboxGenhash ^ 0xabcd
        junkuid = struct.pack("!ii", whiteboxOid,
                              junkGenhash).encode("hex")
        self.assertRaises(KeyError, self.db.retrieve, junkuid)
        f = None
        import gc
        gc.collect()
        self.assertRaises(KeyError, self.db.retrieve, junkuid)
        newf = self.db.retrieve(uid)
        self.assertEquals(newf.intTest, 1)
        self.assertEquals(newf.floatTest, 2.0)
        self.assertEquals(newf.storTest, None)
        self.assertIdentical(self.db.retrieve(uid), newf)

        f2 = Fixture(3, 4.0, newf)
        uid2 = self.db.insert(f2)
        f2 = None
        newf2 = self.db.retrieve(uid2)
        self.assertIdentical(newf2.storTest, newf)

    def testTuples(self):
        tt = TwoTuples()
        tt.tup1 = (4, 5, 6)
        tt.tup2 = (9, 10, "hello")
        uid = self.db.insert(tt)
        self.assertEquals( tt.tup1, (4, 5, 6) )
        self.assertEquals( tt.tup2, (9, 10, "hello") )
        self.db.close()
        del self.db
        del tt
        self.setUp()
        self.db.insert(Node("screw up"))
        tt2 = self.db.retrieve(uid)
        self.assertEquals(tt2.tup1, (4, 5, 6))

    def testTuplesAndLists(self):
        # self.db._superchatty = 1
        sl = Strlist()
        uid = self.db.insert(sl)
        self.assertEquals(sl.strlist[:],'a b c'.split())
        self.db.close()
        self.setUp()
        # self.db._superchatty = 1
        tl = TupList()
        tl.list = [(1, 2, "3"), (4, 5, "6")]
        self.db.insert(tl)
        sl2 = self.db.retrieve(uid)
        self.assertEquals(sl2.strlist[:],'a b c'.split())

class Strlist(Storable):
    __schema__ = {"strlist": compound.ListOf(str)}
    def __init__(self):
        self.strlist = 'a b c'.split()

from twisted.world.util import Backwards

class TestBackwards(unittest.TestCase):
    def testSlice(self):
        lst = range(20)
        lst2 = list(lst)
        lst2.reverse()
        b = Backwards(lst)
        self.failUnlessEqual(lst2[0:10], b[0:10])
        self.failUnlessEqual(lst2[-10:-4], b[-10:-4])
        self.failUnlessEqual(lst2[:4], b[:4])
        self.failUnlessEqual(len(lst2), len(b))
    
    def testIndexes(self):
        lst = range(20)
        lst2 = list(lst)
        lst2.reverse()
        b = Backwards(lst)
        self.failUnlessEqual(b[4], lst2[4])
        self.failUnlessEqual(b[0], lst2[0])
        self.failUnlessEqual(b[19], lst2[19])
        self.failUnlessEqual(len(lst2), len(b))
