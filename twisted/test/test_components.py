# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Test cases for Twisted component architecture."""

from zope import interface as zinterface
from zope.interface import Interface, implements

from twisted.trial import unittest, util
from twisted.python import components
import warnings

class InterfacesTestCase(unittest.TestCase):
    """Test interfaces."""

class Compo(components.Componentized):
    num = 0
    def inc(self):
        self.num = self.num + 1
        return self.num

class IAdept(Interface):
    def adaptorFunc():
        raise NotImplementedError()

class IElapsed(Interface):
    def elapsedFunc():
        """
        1!
        """

class Adept(components.Adapter):
    implements(IAdept)
    def __init__(self, orig):
        self.original = orig
        self.num = 0
    def adaptorFunc(self):
        self.num = self.num + 1
        return self.num, self.original.inc()

class Elapsed(components.Adapter):
    implements(IElapsed)
    def elapsedFunc(self):
        return 1

components.registerAdapter(Adept, Compo, IAdept)
components.registerAdapter(Elapsed, Compo, IElapsed)

class AComp(components.Componentized):
    pass
class BComp(AComp):
    pass
class CComp(BComp):
    pass

class ITest(Interface):
    pass
class ITest2(Interface):
    pass
class ITest3(Interface):
    pass
class ITest4(Interface):
    pass
class Test(components.Adapter):
    implements(ITest, ITest3, ITest4)
    def __init__(self, orig):
        pass
class Test2:
    implements(ITest2)
    temporaryAdapter = 1
    def __init__(self, orig):
        pass

components.registerAdapter(Test, AComp, ITest)
components.registerAdapter(Test, AComp, ITest3)
components.registerAdapter(Test2, AComp, ITest2)




class ComponentizedTestCase(unittest.TestCase):
    """Simple test case for caching in Componentized.
    """
    def testComponentized(self):
        c = Compo()
        assert c.getComponent(IAdept).adaptorFunc() == (1, 1)
        assert c.getComponent(IAdept).adaptorFunc() == (2, 2)
        assert IElapsed(IAdept(c)).elapsedFunc() == 1

    def testInheritanceAdaptation(self):
        c = CComp()
        co1 = c.getComponent(ITest)
        co2 = c.getComponent(ITest)
        co3 = c.getComponent(ITest2)
        co4 = c.getComponent(ITest2)
        assert co1 is co2
        assert co3 is not co4
        c.removeComponent(co1)
        co5 = c.getComponent(ITest)
        co6 = c.getComponent(ITest)
        assert co5 is co6
        assert co1 is not co5

    def testMultiAdapter(self):
        c = CComp()
        co1 = c.getComponent(ITest)
        co2 = c.getComponent(ITest2)
        co3 = c.getComponent(ITest3)
        co4 = c.getComponent(ITest4)
        assert co4 == None
        assert co1 is co3

class AdapterTestCase(unittest.TestCase):
    """Test adapters."""

    def testGetAdapterClass(self):
        mklass = components.getAdapterFactory(AComp, ITest, None)
        self.assertEquals(mklass, Test)

    def testBadRegister(self):
        # should fail because we already registered an ITest adapter for AComp
        self.assertRaises(ValueError, components.registerAdapter, Test, AComp, ITest)
    
    def testAllowDuplicates(self):
        components.ALLOW_DUPLICATES = 1
        try: 
            components.registerAdapter(Test, AComp, ITest)
        except ValueError:
            self.fail("Should have allowed re-registration")
            
        # should fail because we already registered an ITest adapter
        # for AComp
        components.ALLOW_DUPLICATES = 0
        self.assertRaises(ValueError, components.registerAdapter,
                          Test, AComp, ITest)
    
    def testAdapterGetComponent(self):
        o = object()
        a = Adept(o)
        self.assertRaises(components.CannotAdapt, ITest, a)
        self.assertEquals(ITest(a, None), None)

    def testMultipleInterfaceRegistration(self):
        class IMIFoo(Interface):
            pass
        class IMIBar(Interface):
            pass
        class MIFooer(components.Adapter):
            implements(IMIFoo, IMIBar)
        class Blegh:
            pass
        components.registerAdapter(MIFooer, Blegh, IMIFoo, IMIBar)
        self.assert_(isinstance(IMIFoo(Blegh()), MIFooer))
        self.assert_(isinstance(IMIBar(Blegh()), MIFooer))

class IMeta(Interface):
    pass

class MetaAdder(components.Adapter):
    implements(IMeta)
    def add(self, num):
        return self.original.num + num

class BackwardsAdder(components.Adapter):
    implements(IMeta)
    def add(self, num):
        return self.original.num - num

class MetaNumber:
    def __init__(self, num):
        self.num = num

class FakeAdder:
    def add(self, num):
        return num + 5

class FakeNumber:
    num = 3

class ComponentNumber(components.Componentized):
    def __init__(self):
        self.num = 0
        components.Componentized.__init__(self)

class ComponentMeta(components.Adapter):
    implements(IMeta)
    def __init__(self, original):
        components.Adapter.__init__(self, original)
        self.num = self.original.num

class ComponentAdder(ComponentMeta):
    def add(self, num):
        self.num += num
        return self.num

class ComponentDoubler(ComponentMeta):
    def add(self, num):
        self.num += (num * 2)
        return self.original.num

components.registerAdapter(MetaAdder, MetaNumber, IMeta)
components.registerAdapter(ComponentAdder, ComponentNumber, IMeta)

class IAttrX(Interface):
    def x():
        pass

class IAttrXX(Interface):
    def xx():
        pass

class Xcellent:
    implements(IAttrX)
    def x(self):
        return 'x!'

class DoubleXAdapter:
    num = 42
    def __init__(self, original):
        self.original = original
    def xx(self):
        return (self.original.x(), self.original.x())
    def __cmp__(self, other):
        return cmp(self.num, other.num)

components.registerAdapter(DoubleXAdapter, IAttrX, IAttrXX)

class TestMetaInterface(unittest.TestCase):
    
    def testBasic(self):
        n = MetaNumber(1)
        self.assertEquals(IMeta(n).add(1), 2)

    def testComponentizedInteraction(self):
        c = ComponentNumber()
        IMeta(c).add(1)
        IMeta(c).add(1)
        self.assertEquals(IMeta(c).add(1), 3)

    def testAdapterWithCmp(self):
        # Make sure that a __cmp__ on an adapter doesn't break anything
        xx = IAttrXX(Xcellent())
        self.assertEqual(('x!', 'x!'), xx.xx())

