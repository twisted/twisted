# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

