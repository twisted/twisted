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

"""Test cases for 'jelly' object serialization.
"""

import types
from twisted.trial import unittest
from twisted.spread import newjelly, pb

class A:
    """
    dummy class
    """
    def amethod(self):
        pass

def afunc(self):
    pass

class B:
    """
    dummy class
    """
    def bmethod(self):
        pass


class C:
    """
    dummy class
    """
    def cmethod(self):
        pass


class D(object):
    """
    newstyle class
    """


class SimpleJellyTest:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        
    def isTheSameAs(self, other):
        return self.__dict__ == other.__dict__

try:
    object
    haveObject = 0 # 1 # more work to be done before this really works
except:
    haveObject = 0
else:
    class NewStyle(object):
        pass


class JellyTestCase(unittest.TestCase):
    """
    testcases for `jelly' module serialization.
    """
    jc = newjelly

    def testMethodSelfIdentity(self):
        a = A()
        b = B()
        a.bmethod = b.bmethod
        b.a = a
        im_ = self.jc.unjelly(self.jc.jelly(b)).a.bmethod
        self.assertEquals(im_.im_class, im_.im_self.__class__)

    if haveObject:
        def testNewStyle(self):
            n = NewStyle()
            n.x = 1
            n2 = NewStyle()
            n.n2 = n2
            n.n3 = n2
            c = self.jc.jelly(n)
            m = self.jc.unjelly(c)
            self.failUnless(isinstance(m, NewStyle))
            self.assertIdentical(m.n2, m.n3)

    def testSimple(self):
        """
        simplest test case
        """
        self.failUnless(SimpleJellyTest('a', 'b').isTheSameAs(SimpleJellyTest('a', 'b')))
        a = SimpleJellyTest(1, 2)
        cereal = self.jc.jelly(a)
        b = self.jc.unjelly(cereal)
        self.failUnless(a.isTheSameAs(b))

    def testIdentity(self):
        """
        test to make sure that objects retain identity properly
        """
        x = []
        y = (x)
        x.append(y)
        x.append(y)
        self.assertIdentical(x[0], x[1])
        self.assertIdentical(x[0][0], x)
        s = self.jc.jelly(x)
        z = self.jc.unjelly(s)
        self.assertIdentical(z[0], z[1])
        self.assertIdentical(z[0][0], z)

    def testUnicode(self):
        if hasattr(types, 'UnicodeType'):
            x = unicode('blah')
            y = self.jc.unjelly(self.jc.jelly(x))
            self.assertEquals(x, y)
            self.assertEquals(type(x), type(y))

    def testStressReferences(self):
        reref = []
        toplevelTuple = ({'list': reref}, reref)
        reref.append(toplevelTuple)
        s = self.jc.jelly(toplevelTuple)
        z = self.jc.unjelly(s)
        self.assertIdentical(z[0]['list'], z[1])
        self.assertIdentical(z[0]['list'][0], z)

    def testMoreReferences(self):
        a = []
        t = (a,)
        a.append((t,))
        s = self.jc.jelly(t)
        z = self.jc.unjelly(s)
        self.assertIdentical(z[0][0][0], z)

    def testTypeSecurity(self):
        """
        test for type-level security of serialization
        """
        taster = self.jc.SecurityOptions()
        dct = self.jc.jelly({})
        try:
            self.jc.unjelly(dct, taster)
            self.fail("Insecure Jelly unjellied successfully.")
        except self.jc.InsecureJelly:
            # OK, works
            pass

    def testNewStyleClasses(self):
        j = self.jc.jelly(D)
        uj = self.jc.unjelly(D)
        self.assertIdentical(D, uj)

    def testLotsaTypes(self):
        """
        test for all types currently supported in jelly
        """
        a = A()
        self.jc.unjelly(self.jc.jelly(a))
        self.jc.unjelly(self.jc.jelly(a.amethod))
        items = [afunc, [1, 2, 3], not bool(1), bool(1), 'test', 20.3, (1,2,3), None, A, unittest, {'a':1}, A.amethod]
        for i in items:
            self.assertEquals(i, self.jc.unjelly(self.jc.jelly(i)))
    
    def testSetState(self):
        global TupleState
        class TupleState:
            def __init__(self, other):
                self.other = other
            def __getstate__(self):
                return (self.other,)
            def __setstate__(self, state):
                self.other = state[0]
            def __hash__(self):
                return hash(self.other)
        a = A()
        t1 = TupleState(a)
        t2 = TupleState(a)
        t3 = TupleState((t1, t2))
        d = {t1: t1, t2: t2, t3: t3, "t3": t3}
        t3prime = self.jc.unjelly(self.jc.jelly(d))["t3"]
        self.assertIdentical(t3prime.other[0].other, t3prime.other[1].other)

    def testClassSecurity(self):
        """
        test for class-level security of serialization
        """
        taster = self.jc.SecurityOptions()
        taster.allowInstancesOf(A, B)
        a = A()
        b = B()
        c = C()
        # add a little complexity to the data
        a.b = b
        a.c = c
        # and a backreference
        a.x = b
        b.c = c
        # first, a friendly insecure serialization
        friendly = self.jc.jelly(a, taster)
        x = self.jc.unjelly(friendly, taster)
        self.failUnless(isinstance(x.c, self.jc.Unpersistable),
                        "C came back: %s" % x.c.__class__)
        # now, a malicious one
        mean = self.jc.jelly(a)
        try:
            x = self.jc.unjelly(mean, taster)
            self.fail("x came back: %s" % x)
        except self.jc.InsecureJelly:
            # OK
            pass
        self.assertIdentical(x.x, x.b, "Identity mismatch")
        #test class serialization
        friendly = self.jc.jelly(A, taster)
        x = self.jc.unjelly(friendly, taster)
        self.assertIdentical(x, A, "A came back: %s" % x)

class ClassA(pb.Copyable, pb.RemoteCopy):
    def __init__(self):
        self.ref = ClassB(self)

class ClassB(pb.Copyable, pb.RemoteCopy):
    def __init__(self, ref):
        self.ref = ref

class CircularReferenceTestCase(unittest.TestCase):
    jc = newjelly
    def testSimpleCircle(self):
        self.jc.setUnjellyableForClass(ClassA, ClassA)
        self.jc.setUnjellyableForClass(ClassB, ClassB)
        a = self.jc.unjelly(self.jc.jelly(ClassA()))
        self.failUnless(a.ref.ref is a, "Identity not preserved in circular reference")

    def testCircleWithInvoker(self):
        class dummyInvokerClass: pass
        dummyInvoker = dummyInvokerClass()
        dummyInvoker.serializingPerspective = None
        a0 = ClassA()
        self.jc.setUnjellyableForClass(ClassA, ClassA)
        self.jc.setUnjellyableForClass(ClassB, ClassB)
        j = self.jc.jelly(a0, invoker=dummyInvoker)
        a1 = self.jc.unjelly(j)
        self.failUnlessIdentical(a1.ref.ref, a1,
                                 "Identity not preserved in circular reference")
        
testCases = [JellyTestCase, CircularReferenceTestCase]
