from pyunit import unittest
from twisted.python import roots
import types

class RootsTest(unittest.TestCase):
    def testCollection(self):
        collection = roots.Collection()
        collection.putEntity("x", 'test')
        self.failUnlessEqual(collection.getStaticEntity("x"),
                             'test')
        collection.delEntity("x")
        self.failUnlessEqual(collection.getStaticEntity('x'),
                             None)


    def testConstrained(self):
        class const(roots.Constrained):
            def nameConstraint(self, name):
                return (name == 'x')
        c = const()
        self.failUnlessEqual(c.putEntity('x', 'test'), None)
        self.failUnlessRaises(roots.ConstraintViolation,
                              c.putEntity, 'y', 'test')


    def testHomogenous(self):
        h = roots.Homogenous(types.IntType)
        h.putEntity('a', 1)
        self.failUnlessEqual(h.getStaticEntity('a'),1 )
        self.failUnlessRaises(roots.ConstraintViolation,
                              h.putEntity, 'x', 'y')

    def testAttributes(self):
        a = roots.Attributes(
            myString = types.StringType,
            myInt = types.IntType,
            )
        # positive path
        a.putEntity('myString', 'hello')
        a.putEntity('myInt', 100)
        self.failUnlessEqual(a.getStaticEntity('myString'), 'hello')
        self.failUnlessEqual(a.getStaticEntity('myInt'), 100)
        # negative path
        self.failUnlessRaises(roots.ConstraintViolation,
                              a.putEntity, "illegal name", "illegal value")
        self.failUnlessRaises(roots.ConstraintViolation,
                              a.putEntity, "myString", 100)
        self.failUnlessRaises(roots.ConstraintViolation,
                              a.putEntity, "myInt", 'hello')

