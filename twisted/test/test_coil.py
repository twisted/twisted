from pyunit import unittest

from twisted.manhole import coil

import types

# classes for testClassHierarchy
class A: pass
class B(A): pass
class C(B): pass
class D: pass
class E(C, D): pass
class F(A): pass

class MyConfig(coil.Configurable):
    configTypes = {
        "foo": types.IntType,
        "bar": types.StringType
        }

class CoilTest(unittest.TestCase):
    def testConfigurable(self):
        c = MyConfig()
        c.configure({'foo':1, 'bar':'hi'})
        self.failUnlessRaises(coil.InvalidConfiguration,
                              c.configure, {'foo':'hi'})
        self.failUnlessRaises(coil.InvalidConfiguration,
                              c.configure, {'bar':1})

    def testClassHierarchy(self):
        r = coil.ClassHierarchy()
        map(r.registerClass, (A, B, C, D, E, F))
        subs = list(r.getSubClasses(A, 1))
        subs.sort(lambda a, b: cmp(str(a), str(b)))
        self.failUnlessEqual(subs, [B, C, E, F])

