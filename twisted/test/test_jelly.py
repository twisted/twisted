
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
from pyunit import unittest
from twisted.spread import jelly
#from twisted import sexpy

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


class SimpleJellyTest:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        
    def isTheSameAs(self, other):
        return self.__dict__ == other.__dict__


class JellyTestCase(unittest.TestCase):
    """
    testcases for `jelly' module serialization.
    """
    def testSimple(self):
        """
        simplest test case
        """
        assert SimpleJellyTest('a', 'b').isTheSameAs(SimpleJellyTest('a', 'b'))
        a = SimpleJellyTest(1, 2)
        cereal = jelly.jelly(a)
        b = jelly.unjelly(cereal)
        assert a.isTheSameAs(b)

    def testIdentity(self):
        """
        test to make sure that objects retain identity properly
        """
        x = []
        y = (x)
        x.append(y)
        x.append(y)
        assert x[0] is x[1]
        assert x[0][0] is x
        s = jelly.jelly(x)
        z = jelly.unjelly(s)
        assert z[0] is z[1]
        assert z[0][0] is z

    def testUnicode(self):
        if hasattr(types, 'UnicodeType'):
            x = 'blah'
            assert jelly.unjelly(jelly.jelly(unicode(x))) == x

    def testStressReferences(self):
        reref = []
        toplevelTuple = ({'list': reref}, reref)
        reref.append(toplevelTuple)
        s = jelly.jelly(toplevelTuple)
        z = jelly.unjelly(s)
        assert z[0]['list'] is z[1]
        assert z[0]['list'][0] is z


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

        assert x.b is x.c.b, "Identity failure."
        # assert len(perst) == 3, "persistentStore should only be called 3 times."
        assert perst[0], "persistentStore was not called."
        assert x.b is a.b, "Persistent storage identity failure."

    def testTypeSecurity(self):
        """
        test for type-level security of serialization
        """
        taster = jelly.SecurityOptions()
        dct = jelly.jelly({})
        try:
            jelly.unjelly(dct, taster)
            assert 0, "Insecure Jelly unjellied successfully."
        except jelly.InsecureJelly:
            # OK, works
            pass

    def testLotsaTypes(self):
        """
        test for all types currently supported in jelly
        """
        a = A()
        jelly.unjelly(jelly.jelly(a))
        jelly.unjelly(jelly.jelly(a.amethod))
        items = [afunc, [1, 2, 3], 'test', 20.3, (1,2,3), None, A, unittest, {'a':1}, A.amethod]
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
        assert t3prime.other[0].other is t3prime.other[1].other

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
        assert isinstance(x.c, jelly.Unpersistable), "C came back: %s" % x.c.__class__
        # now, a malicious one
        mean = jelly.jelly(a)
        try:
            x = jelly.unjelly(mean, taster)
            assert 0, "x came back: %s" % x
        except jelly.InsecureJelly:
            # OK
            pass
        assert x.x is x.b, "Identity mismatch"
        

testCases = [JellyTestCase]
        
        
