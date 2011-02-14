# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.trial import unittest
from twisted.python import roots
import types

class RootsTest(unittest.TestCase):

    def testExceptions(self):
        request = roots.Request()
        try:
            request.write("blah")
        except NotImplementedError:
            pass
        else:
            self.fail()
        try:
            request.finish()
        except NotImplementedError:
            pass
        else:
            self.fail()

    def testCollection(self):
        collection = roots.Collection()
        collection.putEntity("x", 'test')
        self.failUnlessEqual(collection.getStaticEntity("x"),
                             'test')
        collection.delEntity("x")
        self.failUnlessEqual(collection.getStaticEntity('x'),
                             None)
        try:
            collection.storeEntity("x", None)
        except NotImplementedError:
            pass
        else:
            self.fail()
        try:
            collection.removeEntity("x", None)
        except NotImplementedError:
            pass
        else:
            self.fail()

    def testConstrained(self):
        class const(roots.Constrained):
            def nameConstraint(self, name):
                return (name == 'x')
        c = const()
        self.failUnlessEqual(c.putEntity('x', 'test'), None)
        self.failUnlessRaises(roots.ConstraintViolation,
                              c.putEntity, 'y', 'test')


    def testHomogenous(self):
        h = roots.Homogenous()
        h.entityType = types.IntType
        h.putEntity('a', 1)
        self.failUnlessEqual(h.getStaticEntity('a'),1 )
        self.failUnlessRaises(roots.ConstraintViolation,
                              h.putEntity, 'x', 'y')

