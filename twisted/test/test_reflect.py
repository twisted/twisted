# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for the L{twisted.python.reflect} module.
"""

from __future__ import division, absolute_import

import weakref
from collections import deque

from twisted.python.compat import _PY3
from twisted.trial import unittest
from twisted.python import reflect
from twisted.python.versions import Version



class ObjectGrep(unittest.TestCase):
    if _PY3:
        # This is to be removed when fixing #6986
        skip = "twisted.python.reflect.objgrep hasn't been ported to Python 3"


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

        self.assertIn(".__self__",
                      reflect.objgrep(m, m.__self__, reflect.isSame))
        self.assertIn(".__self__.__class__",
                      reflect.objgrep(m, m.__self__.__class__, reflect.isSame))
        self.assertIn(".__func__",
                      reflect.objgrep(m, m.__func__, reflect.isSame))

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

        self.assertIn("().__self__.attr[2][0][2]{'Foosh'}",
                      reflect.objgrep(w, o, reflect.isSame))

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
    if _PY3:
        oldClassNames = ['type']
    else:
        oldClassNames = ['class', 'classobj']

    def testOld(self):
        class OldClass:
            pass
        old = OldClass()
        self.assertIn(reflect.getClass(OldClass).__name__, self.oldClassNames)
        self.assertEqual(reflect.getClass(old).__name__, 'OldClass')

    def testNew(self):
        class NewClass(object):
            pass
        new = NewClass()
        self.assertEqual(reflect.getClass(NewClass).__name__, 'type')
        self.assertEqual(reflect.getClass(new).__name__, 'NewClass')


if not _PY3:
    # The functions tested below are deprecated but still used by external
    # projects like Nevow 0.10. They are not going to be ported to Python 3
    # (hence the condition above) and will be removed as soon as no project used
    # by Twisted will depend on these functions. Also, have a look at the
    # comments related to those functions in twisted.python.reflect.
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
