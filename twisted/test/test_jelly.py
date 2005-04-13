
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Test cases for 'jelly' object serialization.
"""

from twisted.spread import jelly

from twisted.test import test_newjelly

class TestNode(object, jelly.Jellyable):
    """An object to test jellyfying of new style class isntances.
    """
    classAttr = 4
    def __init__(self, parent=None):
        if parent:
            self.id = parent.id + 1
            parent.children.append(self)
        else:
            self.id = 1
        self.parent = parent
        self.children = []


class JellyTestCase(test_newjelly.JellyTestCase):
    jc = jelly
    if test_newjelly.haveDatetime:
        def testDateTime(self):
            test_newjelly.JellyTestCase.testDateTime(self)

    def testPersistentStorage(self):
        perst = [{}, 1]
        def persistentStore(obj, jel, perst = perst):
            perst[1] = perst[1] + 1
            perst[0][perst[1]] = obj
            return str(perst[1])

        def persistentLoad(pidstr, unj, perst = perst):
            pid = int(pidstr)
            return perst[0][pid]

        SimpleJellyTest = test_newjelly.SimpleJellyTest
        a = SimpleJellyTest(1, 2)
        b = SimpleJellyTest(3, 4)
        c = SimpleJellyTest(5, 6)

        a.b = b
        a.c = c
        c.b = b

        jel = self.jc.jelly(a, persistentStore = persistentStore)
        x = self.jc.unjelly(jel, persistentLoad = persistentLoad)

        self.assertIdentical(x.b, x.c.b)
        # assert len(perst) == 3, "persistentStore should only be called 3 times."
        self.failUnless(perst[0], "persistentStore was not called.")
        self.assertIdentical(x.b, a.b, "Persistent storage identity failure.")

    def testNewStyleClasses(self):
        n = TestNode()
        n1 = TestNode(n)
        n11 = TestNode(n1)
        n2 = TestNode(n)
        # Jelly it
        jel = self.jc.jelly(n)
        m = self.jc.unjelly(jel)
        # Check that it has been restored ok
        TestNode.classAttr == 5 # Shouldn't override jellied values
        self._check_newstyle(n,m)

    def _check_newstyle(self, a, b):
        self.assertEqual(a.id, b.id)
        self.assertEqual(a.classAttr, 4)
        self.assertEqual(b.classAttr, 4)
        self.assertEqual(len(a.children), len(b.children))
        for x,y in zip(a.children, b.children):
            self._check_newstyle(x,y)

class CircularReferenceTestCase(test_newjelly.CircularReferenceTestCase):
    jc = jelly


testCases = [JellyTestCase, CircularReferenceTestCase]
