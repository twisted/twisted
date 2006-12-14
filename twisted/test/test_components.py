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


    def test_getComponentDefaults(self):
        """
        Test that a default value specified to Componentized.getComponent if
        there is no component for the requested interface.
        """
        componentized = components.Componentized()
        default = object()
        self.assertIdentical(
            componentized.getComponent(ITest, default),
            default)
        self.assertIdentical(
            componentized.getComponent(ITest, default=default),
            default)
        self.assertIdentical(
            componentized.getComponent(ITest),
            None)



class AdapterTestCase(unittest.TestCase):
    """Test adapters."""

    def testAdapterGetComponent(self):
        o = object()
        a = Adept(o)
        self.assertRaises(components.CannotAdapt, ITest, a)
        self.assertEquals(ITest(a, None), None)



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


class RegistrationTestCase(unittest.TestCase):
    """
    Tests for adapter registration.
    """
    def _registerAdapterForClassOrInterface(self, original):
        adapter = lambda o: None
        class TheInterface(Interface):
            pass
        components.registerAdapter(adapter, original, TheInterface)
        self.assertIdentical(
            components.getAdapterFactory(original, TheInterface, None),
            adapter)


    def test_registerAdapterForClass(self):
        """
        Test that an adapter from a class can be registered and then looked
        up.
        """
        class TheOriginal(object):
            pass
        return self._registerAdapterForClassOrInterface(TheOriginal)


    def test_registerAdapterForInterface(self):
        """
        Test that an adapter from an interface can be registered and then
        looked up.
        """
        class TheOriginal(Interface):
            pass
        return self._registerAdapterForClassOrInterface(TheOriginal)


    def _duplicateAdapterForClassOrInterface(self, original):
        firstAdapter = lambda o: False
        secondAdapter = lambda o: True
        class TheInterface(Interface):
            pass
        components.registerAdapter(firstAdapter, original, TheInterface)
        self.assertRaises(
            ValueError,
            components.registerAdapter,
            secondAdapter, original, TheInterface)
        # Make sure that the original adapter is still around as well
        self.assertIdentical(
            components.getAdapterFactory(original, TheInterface, None),
            firstAdapter)


    def test_duplicateAdapterForClass(self):
        """
        Test that attempting to register a second adapter from a class
        raises the appropriate exception.
        """
        class TheOriginal(object):
            pass
        return self._duplicateAdapterForClassOrInterface(TheOriginal)


    def test_duplicateAdapterForInterface(self):
        """
        Test that attempting to register a second adapter from an interface
        raises the appropriate exception.
        """
        class TheOriginal(Interface):
            pass
        return self._duplicateAdapterForClassOrInterface(TheOriginal)


    def _duplicateAdapterForClassOrInterfaceAllowed(self, original):
        firstAdapter = lambda o: False
        secondAdapter = lambda o: True
        class TheInterface(Interface):
            pass
        components.registerAdapter(firstAdapter, original, TheInterface)
        components.ALLOW_DUPLICATES = True
        try:
            components.registerAdapter(secondAdapter, original, TheInterface)
            self.assertIdentical(
                components.getAdapterFactory(original, TheInterface, None),
                secondAdapter)
        finally:
            components.ALLOW_DUPLICATES = False

        # It should be rejected again at this point
        self.assertRaises(
            ValueError,
            components.registerAdapter,
            firstAdapter, original, TheInterface)

        self.assertIdentical(
            components.getAdapterFactory(original, TheInterface, None),
            secondAdapter)

    def test_duplicateAdapterForClassAllowed(self):
        """
        Test that when L{components.ALLOW_DUPLICATES} is set to a true
        value, duplicate registrations from classes are allowed to override
        the original registration.
        """
        class TheOriginal(object):
            pass
        return self._duplicateAdapterForClassOrInterfaceAllowed(TheOriginal)


    def test_duplicateAdapterForInterfaceAllowed(self):
        """
        Test that when L{components.ALLOW_DUPLICATES} is set to a true
        value, duplicate registrations from interfaces are allowed to
        override the original registration.
        """
        class TheOriginal(Interface):
            pass
        return self._duplicateAdapterForClassOrInterfaceAllowed(TheOriginal)


    def _multipleInterfacesForClassOrInterface(self, original):
        adapter = lambda o: None
        class FirstInterface(Interface):
            pass
        class SecondInterface(Interface):
            pass
        components.registerAdapter(adapter, original, FirstInterface, SecondInterface)
        self.assertIdentical(
            components.getAdapterFactory(original, FirstInterface, None),
            adapter)
        self.assertIdentical(
            components.getAdapterFactory(original, SecondInterface, None),
            adapter)


    def test_multipleInterfacesForClass(self):
        """
        Test the registration of an adapter from a class to several
        interfaces at once.
        """
        class TheOriginal(object):
            pass
        return self._multipleInterfacesForClassOrInterface(TheOriginal)


    def test_multipleInterfacesForInterface(self):
        """
        Test the registration of an adapter from an interface to several
        interfaces at once.
        """
        class TheOriginal(Interface):
            pass
        return self._multipleInterfacesForClassOrInterface(TheOriginal)


    def _subclassAdapterRegistrationForClassOrInterface(self, original):
        firstAdapter = lambda o: True
        secondAdapter = lambda o: False
        class TheSubclass(original):
            pass
        class TheInterface(Interface):
            pass
        components.registerAdapter(firstAdapter, original, TheInterface)
        components.registerAdapter(secondAdapter, TheSubclass, TheInterface)
        self.assertIdentical(
            components.getAdapterFactory(original, TheInterface, None),
            firstAdapter)
        self.assertIdentical(
            components.getAdapterFactory(TheSubclass, TheInterface, None),
            secondAdapter)


    def test_subclassAdapterRegistrationForClass(self):
        """
        Test that an adapter to a particular interface can be registered
        from both a class and its subclass.
        """
        class TheOriginal(object):
            pass
        return self._subclassAdapterRegistrationForClassOrInterface(TheOriginal)


    def test_subclassAdapterRegistrationForInterface(self):
        """
        Test that an adapter to a particular interface can be registered
        from both an interface and its subclass.
        """
        class TheOriginal(Interface):
            pass
        return self._subclassAdapterRegistrationForClassOrInterface(TheOriginal)
