
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Test cases for twisted.reflect module.
"""

import weakref

# Twisted Imports
from twisted.trial import unittest
from twisted.python import reflect


class SettableTest(unittest.TestCase):
    def setUp(self):
        self.setter = reflect.Settable()

    def tearDown(self):
        del self.setter

    def testSet(self):
        self.setter(a=1, b=2)
        self.failUnlessEqual(self.setter.a, 1)
        self.failUnlessEqual(self.setter.b, 2)


class AccessorTester(reflect.Accessor):
    def set_x(self, x):
        self.y = x
        self.reallySet('x',x)

    def get_z(self):
        self.q = 1
        return 1

    def del_z(self):
        self.reallyDel("q")


class AccessorTest(unittest.TestCase):
    def setUp(self):
        self.tester = AccessorTester()

    def testSet(self):
        self.tester.x = 1
        self.failUnlessEqual(self.tester.x, 1)
        self.failUnlessEqual(self.tester.y, 1)

    def testGet(self):
        self.failUnlessEqual(self.tester.z, 1)
        self.failUnlessEqual(self.tester.q, 1)

    def testDel(self):
        self.tester.z
        self.failUnlessEqual(self.tester.q, 1)
        del self.tester.z
        self.failUnlessEqual(hasattr(self.tester, "q"), 0)
        self.tester.x = 1
        del self.tester.x
        self.failUnlessEqual(hasattr(self.tester, "x"), 0)


class LookupsTestCase(unittest.TestCase):
    """Test lookup methods."""

    def testClassLookup(self):
        self.assertEquals(reflect.namedClass("twisted.python.reflect.Summer"), reflect.Summer)

    def testModuleLookup(self):
        self.assertEquals(reflect.namedModule("twisted.python.reflect"), reflect)

class LookupsTestCaseII(unittest.TestCase):
    def testPackageLookup(self):
        import twisted.python
        self.failUnlessIdentical(reflect.namedAny("twisted.python"),
                                 twisted.python)

    def testModuleLookup(self):
        self.failUnlessIdentical(reflect.namedAny("twisted.python.reflect"),
                                 reflect)

    def testClassLookup(self):
        self.failUnlessIdentical(reflect.namedAny("twisted.python."
                                                  "reflect.Summer"),
                                 reflect.Summer)

    def testAttributeLookup(self):
        # Note - not failUnlessIdentical because unbound method lookup
        # creates a new object every time.  This is a foolishness of
        # Python's object implementation, not a bug in Twisted.
        self.failUnlessEqual(reflect.namedAny("twisted.python."
                                              "reflect.Summer.reallySet"),
                             reflect.Summer.reallySet)

    def testSecondAttributeLookup(self):
        self.failUnlessIdentical(reflect.namedAny("twisted.python."
                                                  "reflect.Summer."
                                                  "reallySet.__doc__"),
                                 reflect.Summer.reallySet.__doc__)

    def testExceptionHandling(self):
        # If the namedAny causes a module to be imported, errors in the
        # import should not be masked.
        self.assertRaises(
            ZeroDivisionError,
            reflect.namedAny, "twisted.test.reflect_helper_ZDE")
        self.assertRaises(
            ValueError,
            reflect.namedAny, "twisted.test.reflect_helper_VE")

        # And attributes that don't exist should raise an AttributeError
        self.assertRaises(
            AttributeError,
            reflect.namedAny, "twisted.nosuchmoduleintheworld")
        self.assertRaises(
            AttributeError,
            reflect.namedAny, "twisted.python.reflect.Summer.nosuchattributeintheworld")

        # Finally, invalid module names should raise a ValueError
        self.assertRaises(
            ValueError,
            reflect.namedAny, "")
        self.assertRaises(
            ValueError,
            reflect.namedAny, "12345")
        self.assertRaises(
            ValueError,
            reflect.namedAny, "@#$@(#.!@(#!@#")
        self.assertRaises(
            ValueError,
            reflect.namedAny, "tcelfer.nohtyp.detsiwt")

class ObjectGrep(unittest.TestCase):
    def testDictionary(self):
        o = object()
        d1 = {None: o}
        d2 = {o: None}

        self.assertIn("[None]", reflect.objgrep(d1, o, reflect.isSame))
        self.assertIn("{None}", reflect.objgrep(d2, o, reflect.isSame))

    def testList(self):
        o = object()
        L = [None, o]

        self.assertIn("[1]", reflect.objgrep(L, o, reflect.isSame))

    def testTuple(self):
        o = object()
        T = (o, None)

        self.assertIn("[0]", reflect.objgrep(T, o, reflect.isSame))

    def testInstance(self):
        class Dummy:
            pass
        o = object()
        d = Dummy()
        d.o = o

        self.assertIn(".o", reflect.objgrep(d, o, reflect.isSame))

    def testWeakref(self):
        class Dummy:
            pass
        o = Dummy()
        w1 = weakref.ref(o)

        self.assertIn("()", reflect.objgrep(w1, o, reflect.isSame))

    def testBoundMethod(self):
        class Dummy:
            def dummy(self):
                pass
        o = Dummy()
        m = o.dummy

        self.assertIn(".im_self", reflect.objgrep(m, m.im_self, reflect.isSame))
        self.assertIn(".im_class", reflect.objgrep(m, m.im_class, reflect.isSame))
        self.assertIn(".im_func", reflect.objgrep(m, m.im_func, reflect.isSame))

    def testEverything(self):
        class Dummy:
            def method(self):
                pass

        o = Dummy()
        D1 = {(): "baz", None: "Quux", o: "Foosh"}
        L = [None, (), D1, 3]
        T = (L, {}, Dummy())
        D2 = {0: "foo", 1: "bar", 2: T}
        i = Dummy()
        i.attr = D2
        m = i.method
        w = weakref.ref(m)

        self.assertIn("().im_self.attr[2][0][2]{'Foosh'}", reflect.objgrep(w, o, reflect.isSame))

    def testDepthLimit(self):
        a = []
        b = [a]
        c = [a, b]
        d = [a, c]

        self.assertEquals(['[0]'], reflect.objgrep(d, a, reflect.isSame, maxDepth=1))
        self.assertEquals(['[0]', '[1][0]'], reflect.objgrep(d, a, reflect.isSame, maxDepth=2))
        self.assertEquals(['[0]', '[1][0]', '[1][1][0]'], reflect.objgrep(d, a, reflect.isSame, maxDepth=3))


class GetClass(unittest.TestCase):
    def testOld(self):
        class OldClass:
            pass
        old = OldClass()
        self.assertIn(reflect.getClass(OldClass).__name__, ('class', 'classobj'))
        self.assertEquals(reflect.getClass(old).__name__, 'OldClass')

    def testNew(self):
        class NewClass(object):
            pass
        new = NewClass()
        self.assertEquals(reflect.getClass(NewClass).__name__, 'type')
        self.assertEquals(reflect.getClass(new).__name__, 'NewClass')

class Breakable(object):

    breakRepr = False
    breakStr = False

    def __str__(self):
        if self.breakStr:
            raise self
        else:
            return '<Breakable>'

    def __repr__(self):
        if self.breakRepr:
            raise self
        else:
            return 'Breakable()'

class BrokenType(Breakable, type):
    breakName = False
    def get___name__(self):
        if self.breakName:
            raise RuntimeError("no name")
        return 'BrokenType'
    __name__ = property(get___name__)

class BTBase(Breakable):
    __metaclass__ = BrokenType
    breakRepr = True
    breakStr = True


class NoClassAttr(object):
    __class__ = property(lambda x: x.not_class)

class SafeRepr(unittest.TestCase):

    def testWorkingRepr(self):
        x = [1,2,3]
        self.assertEquals(reflect.safe_repr(x), repr(x))

    def testBrokenRepr(self):
        b = Breakable()
        b.breakRepr = True
        reflect.safe_repr(b)

    def testBrokenStr(self):
        b = Breakable()
        b.breakStr = True
        reflect.safe_repr(b)

    def testBrokenClassRepr(self):
        class X(BTBase):
            breakRepr = True
        reflect.safe_repr(X)
        reflect.safe_repr(X())

    def testBrokenClassStr(self):
        class X(BTBase):
            breakStr = True
        reflect.safe_repr(X)
        reflect.safe_repr(X())

    def testBroken__Class__Attr(self):
        reflect.safe_repr(NoClassAttr())

    def testBroken__Class__Name__Attr(self):
        class X(BTBase):
            breakName = True
        reflect.safe_repr(X())


class SafeStr(unittest.TestCase):
    def testWorkingStr(self):
        x = [1,2,3]
        self.assertEquals(reflect.safe_str(x), str(x))

    def testBrokenStr(self):
        b = Breakable()
        b.breakStr = True
        reflect.safe_str(b)

    def testBrokenRepr(self):
        b = Breakable()
        b.breakRepr = True
        reflect.safe_str(b)

    def testBrokenClassStr(self):
        class X(BTBase):
            breakStr = True
        reflect.safe_str(X)
        reflect.safe_str(X())

    def testBrokenClassRepr(self):
        class X(BTBase):
            breakRepr = True
        reflect.safe_str(X)
        reflect.safe_str(X())

    def testBroken__Class__Attr(self):
        reflect.safe_str(NoClassAttr())

    def testBroken__Class__Name__Attr(self):
        class X(BTBase):
            breakName = True
        reflect.safe_str(X())
