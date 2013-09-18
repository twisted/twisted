# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for the L{twisted.python.reflect} module.
"""

import weakref
from collections import deque

try:
    from ihooks import ModuleImporter
except ImportError:
    ModuleImporter = None

from twisted.trial import unittest
from twisted.python import reflect
from twisted.python.versions import Version
from twisted.python.test.test_reflectpy3 import LookupsTestCase


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
        Test references search through a deque object.
        """
        o = object()
        D = deque()
        D.append(None)
        D.append(o)

        self.assertIn("[1]", reflect.objgrep(D, o, reflect.isSame))


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
