# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for twisted.reflect module.
"""

import weakref, os
try:
    from ihooks import ModuleImporter
except ImportError:
    ModuleImporter = None

try:
    from collections import deque
except ImportError:
    deque = None

from twisted.trial import unittest
from twisted.python import reflect, util
from twisted.python.versions import Version
from twisted.python.test.test_reflectpy3 import LookupsTestCase


class SettableTest(unittest.TestCase):
    def setUp(self):
        self.setter = reflect.Settable()

    def tearDown(self):
        del self.setter

    def testSet(self):
        self.setter(a=1, b=2)
        self.assertEqual(self.setter.a, 1)
        self.assertEqual(self.setter.b, 2)



class AccessorTester(reflect.Accessor):

    def set_x(self, x):
        self.y = x
        self.reallySet('x', x)


    def get_z(self):
        self.q = 1
        return 1


    def del_z(self):
        self.reallyDel("q")



class PropertyAccessorTester(reflect.PropertyAccessor):
    """
    Test class to check L{reflect.PropertyAccessor} functionalities.
    """
    r = 0

    def set_r(self, r):
        self.s = r


    def set_x(self, x):
        self.y = x
        self.reallySet('x', x)


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
        self.assertEqual(self.tester.x, 1)
        self.assertEqual(self.tester.y, 1)

    def testGet(self):
        self.assertEqual(self.tester.z, 1)
        self.assertEqual(self.tester.q, 1)

    def testDel(self):
        self.tester.z
        self.assertEqual(self.tester.q, 1)
        del self.tester.z
        self.assertEqual(hasattr(self.tester, "q"), 0)
        self.tester.x = 1
        del self.tester.x
        self.assertEqual(hasattr(self.tester, "x"), 0)



class PropertyAccessorTest(AccessorTest):
    """
    Tests for L{reflect.PropertyAccessor}, using L{PropertyAccessorTester}.
    """

    def setUp(self):
        self.tester = PropertyAccessorTester()


    def test_setWithDefaultValue(self):
        """
        If an attribute is present in the class, it can be retrieved by
        default.
        """
        self.assertEqual(self.tester.r, 0)
        self.tester.r = 1
        self.assertEqual(self.tester.r, 0)
        self.assertEqual(self.tester.s, 1)


    def test_getValueInDict(self):
        """
        The attribute value can be overriden by directly modifying the value in
        C{__dict__}.
        """
        self.tester.__dict__["r"] = 10
        self.assertEqual(self.tester.r, 10)


    def test_notYetInDict(self):
        """
        If a getter is defined on an attribute but without any default value,
        it raises C{AttributeError} when trying to access it.
        """
        self.assertRaises(AttributeError, getattr, self.tester, "x")



class ImportHooksLookupTests(unittest.TestCase, LookupsTestCase):
    """
    Tests for lookup methods in the presence of L{ihooks}-style import hooks.
    Runs all of the tests from L{LookupsTestCase} after installing a custom
    import hook.
    """
    skip = ("ihooks support is broken, and has probably been broken since "
            "Python 2.6. On the other hand, no one should use ihooks.")


    def setUp(self):
        """
        Perturb the normal import behavior subtly by installing an import
        hook.  No custom behavior is provided, but this adds some extra
        frames to the call stack, which L{namedAny} must be able to account
        for.
        """
        self.importer = ModuleImporter()
        self.importer.install()


    def tearDown(self):
        """
        Uninstall the custom import hook.
        """
        self.importer.uninstall()

# Prevent trial from re-running these unnecessarily:
del LookupsTestCase



class ObjectGrep(unittest.TestCase):
    def test_dictionary(self):
        """
        Test references search through a dictionnary, as a key or as a value.
        """
        o = object()
        d1 = {None: o}
        d2 = {o: None}

        self.assertIn("[None]", reflect.objgrep(d1, o, reflect.isSame))
        self.assertIn("{None}", reflect.objgrep(d2, o, reflect.isSame))

    def test_list(self):
        """
        Test references search through a list.
        """
        o = object()
        L = [None, o]

        self.assertIn("[1]", reflect.objgrep(L, o, reflect.isSame))

    def test_tuple(self):
        """
        Test references search through a tuple.
        """
        o = object()
        T = (o, None)

        self.assertIn("[0]", reflect.objgrep(T, o, reflect.isSame))

    def test_instance(self):
        """
        Test references search through an object attribute.
        """
        class Dummy:
            pass
        o = object()
        d = Dummy()
        d.o = o

        self.assertIn(".o", reflect.objgrep(d, o, reflect.isSame))

    def test_weakref(self):
        """
        Test references search through a weakref object.
        """
        class Dummy:
            pass
        o = Dummy()
        w1 = weakref.ref(o)

        self.assertIn("()", reflect.objgrep(w1, o, reflect.isSame))

    def test_boundMethod(self):
        """
        Test references search through method special attributes.
        """
        class Dummy:
            def dummy(self):
                pass
        o = Dummy()
        m = o.dummy

        self.assertIn(".im_self", reflect.objgrep(m, m.im_self, reflect.isSame))
        self.assertIn(".im_class", reflect.objgrep(m, m.im_class, reflect.isSame))
        self.assertIn(".im_func", reflect.objgrep(m, m.im_func, reflect.isSame))

    def test_everything(self):
        """
        Test references search using complex set of objects.
        """
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

    def test_depthLimit(self):
        """
        Test the depth of references search.
        """
        a = []
        b = [a]
        c = [a, b]
        d = [a, c]

        self.assertEqual(['[0]'], reflect.objgrep(d, a, reflect.isSame, maxDepth=1))
        self.assertEqual(['[0]', '[1][0]'], reflect.objgrep(d, a, reflect.isSame, maxDepth=2))
        self.assertEqual(['[0]', '[1][0]', '[1][1][0]'], reflect.objgrep(d, a, reflect.isSame, maxDepth=3))

    def test_deque(self):
        """
        Test references search through a deque object. Only for Python > 2.3.
        """
        o = object()
        D = deque()
        D.append(None)
        D.append(o)

        self.assertIn("[1]", reflect.objgrep(D, o, reflect.isSame))

    if deque is None:
        test_deque.skip = "Deque not available"


class GetClass(unittest.TestCase):
    def testOld(self):
        class OldClass:
            pass
        old = OldClass()
        self.assertIn(reflect.getClass(OldClass).__name__, ('class', 'classobj'))
        self.assertEqual(reflect.getClass(old).__name__, 'OldClass')

    def testNew(self):
        class NewClass(object):
            pass
        new = NewClass()
        self.assertEqual(reflect.getClass(NewClass).__name__, 'type')
        self.assertEqual(reflect.getClass(new).__name__, 'NewClass')



class DeprecationTestCase(unittest.TestCase):
    """
    Test deprecations in twisted.python.reflect
    """

    def test_allYourBase(self):
        """
        Test deprecation of L{reflect.allYourBase}. See #5481 for removal.
        """
        self.callDeprecated(
            (Version("Twisted", 11, 0, 0), "inspect.getmro"),
            reflect.allYourBase, DeprecationTestCase)


    def test_accumulateBases(self):
        """
        Test deprecation of L{reflect.accumulateBases}. See #5481 for removal.
        """
        l = []
        self.callDeprecated(
            (Version("Twisted", 11, 0, 0), "inspect.getmro"),
            reflect.accumulateBases, DeprecationTestCase, l, None)


    def lookForDeprecationWarning(self, testMethod, attributeName, warningMsg):
        """
        Test deprecation of attribute 'reflect.attributeName' by calling
        'reflect.testMethod' and verifying the warning message
        'reflect.warningMsg'

        @param testMethod: Name of the offending function to be used with
            flushWarnings
        @type testmethod: C{str}

        @param attributeName: Name of attribute to be checked for deprecation
        @type attributeName: C{str}

        @param warningMsg: Deprecation warning message
        @type warningMsg: C{str}
        """
        warningsShown = self.flushWarnings([testMethod])
        self.assertEqual(len(warningsShown), 1)
        self.assertIdentical(warningsShown[0]['category'], DeprecationWarning)
        self.assertEqual(
            warningsShown[0]['message'],
            "twisted.python.reflect." + attributeName + " "
            "was deprecated in Twisted 12.1.0: " + warningMsg + ".")


    def test_settable(self):
        """
        Test deprecation of L{reflect.Settable}.
        """
        reflect.Settable()
        self.lookForDeprecationWarning(
            self.test_settable, "Settable",
            "Settable is old and untested. Please write your own version of this "
            "functionality if you need it")


    def test_accessorType(self):
        """
        Test deprecation of L{reflect.AccessorType}.
        """
        reflect.AccessorType(' ', ( ), { })
        self.lookForDeprecationWarning(
            self.test_accessorType, "AccessorType",
            "AccessorType is old and untested. Please write your own version of "
            "this functionality if you need it")


    def test_propertyAccessor(self):
        """
        Test deprecation of L{reflect.PropertyAccessor}.
        """
        reflect.PropertyAccessor()
        self.lookForDeprecationWarning(
            self.test_propertyAccessor, "PropertyAccessor",
            "PropertyAccessor is old and untested. Please write your own "
            "version of this functionality if you need it")


    def test_accessor(self):
        """
        Test deprecation of L{reflect.Accessor}.
        """
        reflect.Accessor()
        self.lookForDeprecationWarning(
            self.test_accessor, "Accessor",
            "Accessor is an implementation for Python 2.1 which is no longer "
            "supported by Twisted")


    def test_originalAccessor(self):
        """
        Test deprecation of L{reflect.OriginalAccessor}.
        """
        reflect.OriginalAccessor()
        self.lookForDeprecationWarning(
            self.test_originalAccessor, "OriginalAccessor",
            "OriginalAccessor is a reference to class "
            "twisted.python.reflect.Accessor which is deprecated")


    def test_summer(self):
        """
        Test deprecation of L{reflect.Summer}.
        """
        reflect.Summer()
        self.lookForDeprecationWarning(
            self.test_summer, "Summer",
            "Summer is a child class of twisted.python.reflect.Accessor which "
            "is deprecated")
