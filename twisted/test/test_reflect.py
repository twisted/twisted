
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

"""
Test cases for twisted.reflect module.
"""

# Twisted Imports
from pyunit import unittest
from twisted.python import reflect
from twisted.python import reference

class ResolverTest(unittest.TestCase):
    def testResolver(self):
        t=reference.Reference
        class A: pass
        a=A()
        a.m=t('x')
        a.n=t('y')
        a.o=t('z')

        x=[1,2,t('x')]
        y=[t('x'),t('y'),t('z')]
        z={'a':1,'b':2,'x':t('x'),'y':t('y')}
        look={'x':x,
              'y':y,
              'z':z}
        reference.Resolver(look).resolve([a,x,y,z])
        assert x[2]==x
        assert y==[x,y,z], y
        assert z['x']==x
        assert z['y']==y
        assert a.m==x
        assert a.n==y
        assert a.o==z



class SettableTest(unittest.TestCase):
    def setUp(self):
        self.setter = reflect.Settable()

    def tearDown(self):
        del self.setter

    def testSet(self):
        self.setter(a=1, b=2)
        self.failUnlessEqual(self.setter.a, 1)
        self.failUnlessEqual(self.setter.b, 2)


class AccessorTest(unittest.TestCase):
    def setUp(self):
        class Tester(reflect.Accessor):
            def set_x(self, x):
                self.y = x
                self.reallySet('x',x)

            def get_z(self):
                self.q = 1
                return 1

        self.tester = Tester()

    def testSet(self):
        self.tester.x = 1
        self.failUnlessEqual(self.tester.x, 1)
        self.failUnlessEqual(self.tester.y, 1)

    def testGet(self):
        self.failUnlessEqual(self.tester.z, 1)
        self.failUnlessEqual(self.tester.q, 1)

class PromiseTest(unittest.TestCase):
    def setUp(self):
        class SlowObject:
            def __init__(self):
                self.results = []
            def a(self, arg):
                self.results.append(("a", arg))
            def b(self, arg):
                self.results.append(("b", arg))
        self.slowObj = SlowObject()
        self.obj = reflect.Promise()

    def testSingle(self):
        """Promise: single"""
        self.obj.a(0)
        self.obj.__become__(self.slowObj)
        self.failUnlessEqual(self.obj.results, [("a", 0)])

    def testDouble(self):
        """Promise: double"""
        meth = self.obj.a
        meth("alpha")
        meth("beta")
        self.obj.__become__(self.slowObj)
        self.failUnlessEqual(self.obj.results,
                             [("a", "alpha"), ("a", "beta")])

    def testMixed(self):
        """Promise: mixed"""
        a = self.obj.a
        b = self.obj.b
        b(1)
        a(2)
        b(3)
        self.obj.a(4)
        self.obj.__become__(self.slowObj)
        self.failUnlessEqual(self.obj.results,
                             [("b", 1), ("a", 2), ("b", 3), ("a", 4)])

    def tearDown(self):
        del self.obj
        del self.slowObj


class LookupsTestCase(unittest.TestCase):
    """Test lookup methods."""
    
    def testClassLookup(self):
        self.assertEquals(reflect.namedClass("twisted.python.reflect.Summer"), reflect.Summer)
    
    def testModuleLookup(self):
        self.assertEquals(reflect.namedModule("twisted.python.reflect"), reflect)

