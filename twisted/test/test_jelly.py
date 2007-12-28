
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Test cases for 'jelly' object serialization.
"""

import datetime, types

from twisted.spread import jelly, pb

from twisted.trial import unittest

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


class NewStyle(object):
    pass


class JellyTestCase(unittest.TestCase):
    """
    testcases for `jelly' module serialization.
    """

    def testMethodSelfIdentity(self):
        a = A()
        b = B()
        a.bmethod = b.bmethod
        b.a = a
        im_ = jelly.unjelly(jelly.jelly(b)).a.bmethod
        self.assertEquals(im_.im_class, im_.im_self.__class__)


    def testNewStyle(self):
        n = NewStyle()
        n.x = 1
        n2 = NewStyle()
        n.n2 = n2
        n.n3 = n2
        c = jelly.jelly(n)
        m = jelly.unjelly(c)
        self.failUnless(isinstance(m, NewStyle))
        self.assertIdentical(m.n2, m.n3)


    def testDateTime(self):
        dtn = datetime.datetime.now()
        dtd = datetime.datetime.now() - dtn
        input = [dtn, dtd]
        c = jelly.jelly(input)
        output = jelly.unjelly(c)
        self.assertEquals(input, output)
        self.assertNotIdentical(input, output)


    def testSimple(self):
        """
        simplest test case
        """
        self.failUnless(SimpleJellyTest('a', 'b').isTheSameAs(SimpleJellyTest('a', 'b')))
        a = SimpleJellyTest(1, 2)
        cereal = jelly.jelly(a)
        b = jelly.unjelly(cereal)
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
        s = jelly.jelly(x)
        z = jelly.unjelly(s)
        self.assertIdentical(z[0], z[1])
        self.assertIdentical(z[0][0], z)


    def testUnicode(self):
        if hasattr(types, 'UnicodeType'):
            x = unicode('blah')
            y = jelly.unjelly(jelly.jelly(x))
            self.assertEquals(x, y)
            self.assertEquals(type(x), type(y))


    def testStressReferences(self):
        reref = []
        toplevelTuple = ({'list': reref}, reref)
        reref.append(toplevelTuple)
        s = jelly.jelly(toplevelTuple)
        z = jelly.unjelly(s)
        self.assertIdentical(z[0]['list'], z[1])
        self.assertIdentical(z[0]['list'][0], z)


    def testMoreReferences(self):
        a = []
        t = (a,)
        a.append((t,))
        s = jelly.jelly(t)
        z = jelly.unjelly(s)
        self.assertIdentical(z[0][0][0], z)


    def testTypeSecurity(self):
        """
        test for type-level security of serialization
        """
        taster = jelly.SecurityOptions()
        dct = jelly.jelly({})
        self.assertRaises(jelly.InsecureJelly, jelly.unjelly, dct, taster)


    def testNewStyleClasses(self):
        j = jelly.jelly(D)
        uj = jelly.unjelly(D)
        self.assertIdentical(D, uj)


    def testLotsaTypes(self):
        """
        test for all types currently supported in jelly
        """
        a = A()
        jelly.unjelly(jelly.jelly(a))
        jelly.unjelly(jelly.jelly(a.amethod))
        items = [afunc, [1, 2, 3], not bool(1), bool(1), 'test', 20.3, (1,2,3), None, A, unittest, {'a':1}, A.amethod]
        for i in items:
            self.assertEquals(i, jelly.unjelly(jelly.jelly(i)))
    

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
        t3prime = jelly.unjelly(jelly.jelly(d))["t3"]
        self.assertIdentical(t3prime.other[0].other, t3prime.other[1].other)


    def testClassSecurity(self):
        """
        test for class-level security of serialization
        """
        taster = jelly.SecurityOptions()
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
        friendly = jelly.jelly(a, taster)
        x = jelly.unjelly(friendly, taster)
        self.failUnless(isinstance(x.c, jelly.Unpersistable),
                        "C came back: %s" % x.c.__class__)
        # now, a malicious one
        mean = jelly.jelly(a)
        try:
            x = jelly.unjelly(mean, taster)
            self.fail("x came back: %s" % x)
        except jelly.InsecureJelly:
            # OK
            pass
        self.assertIdentical(x.x, x.b, "Identity mismatch")
        #test class serialization
        friendly = jelly.jelly(A, taster)
        x = jelly.unjelly(friendly, taster)
        self.assertIdentical(x, A, "A came back: %s" % x)


    def testUnjellyable(self):
        """
        Test that if Unjellyable is used to deserialize a jellied object,
        state comes out right.
        """
        class JellyableTestClass(jelly.Jellyable):
            pass
        jelly.setUnjellyableForClass(JellyableTestClass, jelly.Unjellyable)
        input = JellyableTestClass()
        input.attribute = 'value'
        output = jelly.unjelly(jelly.jelly(input))
        self.assertEquals(output.attribute, 'value')
        self.failUnless(
            isinstance(output, jelly.Unjellyable),
            "Got instance of %r, not Unjellyable" % (output.__class__,))


    def testPersistentStorage(self):
        perst = [{}, 1]
        def persistentStore(obj, jel, perst = perst):
            perst[1] = perst[1] + 1
            perst[0][perst[1]] = obj
            return str(perst[1])

        def persistentLoad(pidstr, unj, perst = perst):
            pid = int(pidstr)
            return perst[0][pid]

        a = SimpleJellyTest(1, 2)
        b = SimpleJellyTest(3, 4)
        c = SimpleJellyTest(5, 6)

        a.b = b
        a.c = c
        c.b = b

        jel = jelly.jelly(a, persistentStore = persistentStore)
        x = jelly.unjelly(jel, persistentLoad = persistentLoad)

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
        jel = jelly.jelly(n)
        m = jelly.unjelly(jel)
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



class ClassA(pb.Copyable, pb.RemoteCopy):
    def __init__(self):
        self.ref = ClassB(self)



class ClassB(pb.Copyable, pb.RemoteCopy):
    def __init__(self, ref):
        self.ref = ref



class CircularReferenceTestCase(unittest.TestCase):
    def testSimpleCircle(self):
        jelly.setUnjellyableForClass(ClassA, ClassA)
        jelly.setUnjellyableForClass(ClassB, ClassB)
        a = jelly.unjelly(jelly.jelly(ClassA()))
        self.failUnless(a.ref.ref is a, "Identity not preserved in circular reference")


    def testCircleWithInvoker(self):
        class dummyInvokerClass: pass
        dummyInvoker = dummyInvokerClass()
        dummyInvoker.serializingPerspective = None
        a0 = ClassA()
        jelly.setUnjellyableForClass(ClassA, ClassA)
        jelly.setUnjellyableForClass(ClassB, ClassB)
        j = jelly.jelly(a0, invoker=dummyInvoker)
        a1 = jelly.unjelly(j)
        self.failUnlessIdentical(a1.ref.ref, a1,
                                 "Identity not preserved in circular reference")
