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

class CustomConfig(coil.Configurable):

    configTypes = {
        "foo": types.StringType,
    }
    
    def configInit(self, container, name):
        self.name = name
    
    def config_foo(self, foo):
        self.foo = foo


class CoilTest(unittest.TestCase):
    
    def testConfigurable(self):
        c = MyConfig()
        c.configure({'foo':1, 'bar':'hi'})
        self.assertEquals(c.configuration['foo'], 1)
        self.assertEquals(c.configuration['bar'], 'hi')
        self.failUnlessRaises(coil.InvalidConfiguration,
                              c.configure, {'foo':'hi'})
        self.failUnlessRaises(coil.InvalidConfiguration,
                              c.configure, {'bar':1})

    def testCustomConfigurable(self):
        c = coil.createConfigurable(CustomConfig, None, "testName")
        self.assertEquals(c.name, "testName")
        c.configure({'foo' : 'test'})
        self.assertEquals(c.foo, 'test')
    
    def testClassHierarchy(self):
        r = coil.ClassHierarchy()
        map(r.registerClass, (A, B, C, D, E, F))
        subs = list(r.getSubClasses(A, 1))
        subs.sort(lambda a, b: cmp(str(a), str(b)))
        self.failUnlessEqual(subs, [B, C, E, F])

