"""Test cases for 'jelly' object serialization.
"""

from pyunit import unittest
from twisted.spread import jelly
#from twisted import sexpy

class A:
    """
    dummy class
    """


class B:
    """
    dummy class
    """


class C:
    """
    dummy class
    """


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
        
        
