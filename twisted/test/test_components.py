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

"""Test cases for Twisted component architecture."""

from pyunit import unittest

from twisted.python import components


class IAdder(components.Interface):
    """A sample interface that adds stuff."""

    def add(self, a, b):
        """Returns the sub of a and b."""
        raise NotImplementedError

class ISub(IAdder):
    """Sub-interface."""

class IMultiply(components.Interface):
    """Interface that multiplies stuff."""

    def multiply(self, a, b):
        """Multiply two items."""
        raise NotImplementedError


class IntAdder:
    """Class that implements IAdder interface."""

    __implements__ = IAdder

    def add(self, a, b):
        return a + b

class Sub:
    """Class that implements ISub."""

    __implements__ = ISub

    def add(self, a, b):
        return 3


class IntMultiplyWithAdder:
    """Multiply, using Adder object."""

    __implements__ = IMultiply

    def __init__(self, adder):
        self.adder = adder

    def multiply(self, a, b):
        result = 0
        for i in range(a):
            result = self.adder.add(result, b)
        return result

components.registerAdapter(IntMultiplyWithAdder, IntAdder, IMultiply)

class MultiplyAndAdd:
    """Multiply and add."""

    __implements__ = (IAdder, IMultiply)

    def add(self, a, b):
        return a + b

    def multiply(self, a, b):
        return a * b

class IFoo(ISub):
    pass

class FooAdapterForMAA:

    __implements__ = IFoo

    def __init__(self, instance):
        self.instance = instance

    def add(self, a, b):
        return self.instance.add(a, b)

components.registerAdapter(FooAdapterForMAA, MultiplyAndAdd, IFoo)



class InterfacesTestCase(unittest.TestCase):
    """Test interfaces."""

    tuples = ([1, [1]],
              [(2, 3), [2, 3]],
              [(2, (3, (4,)), (1, 5)), [2, 3, 4, 1, 5]],
              [(), []],
              )
    def testTupleTrees(self):
        for tree, result in self.tuples:
            self.assertEquals(components.tupleTreeToList(tree), result)

    def testClasses(self):
        # is this a right thing to do?
        self.assert_( components.implements(MultiplyAndAdd, IMultiply) )
        self.assert_( components.implements(MultiplyAndAdd, IAdder) )
        self.assert_( components.implements(Sub, IAdder) )
        self.assert_( components.implements(Sub, ISub) )

    def testInstances(self):
        o = MultiplyAndAdd()
        self.assert_( components.implements(o, IMultiply) )
        self.assert_( components.implements(o, IMultiply) )

        o = Sub()
        self.assert_( components.implements(o, IAdder) )
        self.assert_( components.implements(o, ISub) )

    def testInstanceOnlyImplements(self):
        class Blah: pass
        o = Blah()
        o.__implements__ = IAdder
        self.assert_( components.implements(o, IAdder) )

    def testOther(self):
        self.assert_( not components.implements(3, ISub) )
        self.assert_( not components.implements("foo", ISub) )

    def testGetInterfaces(self):
        l = components.getInterfaces(Sub)
        l.sort()
        l2 = [IAdder, ISub]
        l2.sort()
        self.assertEquals(l, l2)

        l = components.getInterfaces(MultiplyAndAdd)
        l.sort()
        l2 = [IAdder, IMultiply]
        l2.sort()
        self.assertEquals(l, l2)

    def testSuperInterfaces(self):
        l = components.superInterfaces(ISub)
        l.sort()
        l2 = [ISub, IAdder]
        l2.sort()
        self.assertEquals(l, l2)


class Compo(components.Componentized):
    num = 0
    def inc(self):
        self.num = self.num + 1
        return self.num

class IAdept(components.Interface):
    def adaptorFunc(self):
        raise NotImplementedError()

class Adept:
    __implements__ = IAdept,
    def __init__(self, orig):
        self.orig = orig
        self.num = 0
    def adaptorFunc(self):
        self.num = self.num + 1
        return self.num, self.orig.inc()

components.registerAdapter(Adept, Compo, IAdept)

class AComp(components.Componentized):
    pass
class BComp(AComp):
    pass
class CComp(BComp):
    pass

class ITest(components.Interface):
    pass
class ITest2(components.Interface):
    pass
class ITest3(components.Interface):
    pass
class ITest4(components.Interface):
    pass
class Test(components.Adapter):
    __implements__ = ITest, ITest3, ITest4
    def __init__(self, orig):
        pass
class Test2:
    __implements__ = ITest2,
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

    def testInheritanceAdaptation(self):
        c = CComp()
        co1 = c.getComponent(ITest)
        co2 = c.getComponent(ITest)
        co3 = c.getComponent(ITest2)
        co4 = c.getComponent(ITest2)
        assert co1 is co2
        assert co3 is not co4

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

    def testNoAdapter(self):
        o = Sub()
        multiplier = components.getAdapter(o, IMultiply, None)
        self.assertEquals(multiplier, None)

    def testSelfIsAdapter(self):
        o = IntAdder()
        adder = components.getAdapter(o, IAdder, None)
        self.assert_( o is adder )

    def testGetAdapter(self):
        o = IntAdder()
        self.assertEquals(o.add(3, 4), 7)

        # get an object implementing IMultiply
        multiplier = components.getAdapter(o, IMultiply, None)

        # check that it complies with the IMultiply interface
        self.assertEquals(multiplier.multiply(3, 4), 12)

    def testGetAdapterClass(self):
        mklass = components.getAdapterClass(IntAdder, IMultiply, None)
        self.assertEquals(mklass, IntMultiplyWithAdder)

    def testGetSubAdapter(self):
        o = MultiplyAndAdd()
        self.assert_( not components.implements(o, IFoo) )
        foo = components.getAdapter(o, IFoo, None)
        self.assert_( isinstance(foo, FooAdapterForMAA) )

    def testParentInterface(self):
        o = Sub()
        adder = components.getAdapter(o, IAdder, None)
        self.assert_( o is adder )

    def testBadRegister(self):
        # should fail because Sub doesn't implement IMultiply
        self.assertRaises(ValueError, components.registerAdapter, Sub, MultiplyAndAdd, IMultiply)

        # should fail because we already registered an IMultiply adapter for IntAdder
        self.assertRaises(ValueError, components.registerAdapter, IntMultiplyWithAdder, IntAdder, IMultiply)
