# -*- test-case-name: twisted.test.test_util -*-
# Copyright (c) 2001-2004,2007 Twisted Matrix Laboratories.
# See LICENSE for details.

import os.path, sys
import shutil, errno

from zope.interface import Interface, implements, Attribute

from twisted.trial import unittest

from twisted.python import util
from twisted.python.util import proxyForInterface
from twisted.internet import reactor
from twisted.internet.interfaces import IReactorProcess
from twisted.internet.protocol import ProcessProtocol
from twisted.internet.defer import Deferred
from twisted.internet.error import ProcessDone


class UtilTestCase(unittest.TestCase):

    def testUniq(self):
        l = ["a", 1, "ab", "a", 3, 4, 1, 2, 2, 4, 6]
        self.assertEquals(util.uniquify(l), ["a", 1, "ab", 3, 4, 2, 6])

    def testRaises(self):
        self.failUnless(util.raises(ZeroDivisionError, divmod, 1, 0))
        self.failIf(util.raises(ZeroDivisionError, divmod, 0, 1))

        try:
            util.raises(TypeError, divmod, 1, 0)
        except ZeroDivisionError:
            pass
        else:
            raise unittest.FailTest, "util.raises didn't raise when it should have"

    def testUninterruptably(self):
        def f(a, b):
            self.calls += 1
            exc = self.exceptions.pop()
            if exc is not None:
                raise exc(errno.EINTR, "Interrupted system call!")
            return a + b

        self.exceptions = [None]
        self.calls = 0
        self.assertEquals(util.untilConcludes(f, 1, 2), 3)
        self.assertEquals(self.calls, 1)

        self.exceptions = [None, OSError, IOError]
        self.calls = 0
        self.assertEquals(util.untilConcludes(f, 2, 3), 5)
        self.assertEquals(self.calls, 3)

    def testUnsignedID(self):
        util.id = lambda x: x
        try:
            for i in range(1, 100):
                self.assertEquals(util.unsignedID(i), i)
            top = (sys.maxint + 1L) * 2L
            for i in range(-100, -1):
                self.assertEquals(util.unsignedID(i), top + i)
        finally:
            del util.id

    def testFunctionMetaMerge(self):
        o = object()
        p = object()
        def foo():
            return o
        def bar(x, y, (a, b), c=10, *d, **e):
            return p
        baz = util.mergeFunctionMetadata(foo, bar)
        self.assertIdentical(baz(1, 2, (3, 4), quux=10), p)

        # Now one without a closure
        def foo2(o=o):
            return o
        def bar2(x, y, (a, b), c=10, p=p, *d, **e):
            return p
        baz2 = util.mergeFunctionMetadata(foo2, bar2)
        self.assertIdentical(baz2(1, 2, (3, 4), quux=10), p)


    def testNameToLabel(self):
        """
        Test the various kinds of inputs L{nameToLabel} supports.
        """
        nameData = [
            ('f', 'F'),
            ('fo', 'Fo'),
            ('foo', 'Foo'),
            ('fooBar', 'Foo Bar'),
            ('fooBarBaz', 'Foo Bar Baz'),
            ]
        for inp, out in nameData:
            got = util.nameToLabel(inp)
            self.assertEquals(
                got, out,
                "nameToLabel(%r) == %r != %r" % (inp, got, out))



class OrderedDictTest(unittest.TestCase):
    def testOrderedDict(self):
        d = util.OrderedDict()
        d['a'] = 'b'
        d['b'] = 'a'
        d[3] = 12
        d[1234] = 4321
        self.assertEquals(repr(d), "{'a': 'b', 'b': 'a', 3: 12, 1234: 4321}")
        self.assertEquals(d.values(), ['b', 'a', 12, 4321])
        del d[3]
        self.assertEquals(repr(d), "{'a': 'b', 'b': 'a', 1234: 4321}")
        self.assertEquals(d, {'a': 'b', 'b': 'a', 1234:4321})
        self.assertEquals(d.keys(), ['a', 'b', 1234])
        self.assertEquals(list(d.iteritems()),
                          [('a', 'b'), ('b','a'), (1234, 4321)])
        item = d.popitem()
        self.assertEquals(item, (1234, 4321))

    def testInitialization(self):
        d = util.OrderedDict({'monkey': 'ook',
                              'apple': 'red'})
        self.failUnless(d._order)

        d = util.OrderedDict(((1,1),(3,3),(2,2),(0,0)))
        self.assertEquals(repr(d), "{1: 1, 3: 3, 2: 2, 0: 0}")

class InsensitiveDictTest(unittest.TestCase):
    def testPreserve(self):
        InsensitiveDict=util.InsensitiveDict
        dct=InsensitiveDict({'Foo':'bar', 1:2, 'fnz':{1:2}}, preserve=1)
        self.assertEquals(dct['fnz'], {1:2})
        self.assertEquals(dct['foo'], 'bar')
        self.assertEquals(dct.copy(), dct)
        self.assertEquals(dct['foo'], dct.get('Foo'))
        assert 1 in dct and 'foo' in dct
        self.assertEquals(eval(repr(dct)), dct)
        keys=['Foo', 'fnz', 1]
        for x in keys:
            assert x in dct.keys()
            assert (x, dct[x]) in dct.items()
        self.assertEquals(len(keys), len(dct))
        del dct[1]
        del dct['foo']

    def testNoPreserve(self):
        InsensitiveDict=util.InsensitiveDict
        dct=InsensitiveDict({'Foo':'bar', 1:2, 'fnz':{1:2}}, preserve=0)
        keys=['foo', 'fnz', 1]
        for x in keys:
            assert x in dct.keys()
            assert (x, dct[x]) in dct.items()
        self.assertEquals(len(keys), len(dct))
        del dct[1]
        del dct['foo']




class PasswordTestingProcessProtocol(ProcessProtocol):
    """
    Write the string C{"secret\n"} to a subprocess and then collect all of
    its output and fire a Deferred with it when the process ends.
    """
    def connectionMade(self):
        self.output = []
        self.transport.write('secret\n')

    def childDataReceived(self, fd, output):
        self.output.append((fd, output))

    def processEnded(self, reason):
        self.finished.callback((reason, self.output))


class GetPasswordTest(unittest.TestCase):
    if not IReactorProcess.providedBy(reactor):
        skip = "Process support required to test getPassword"

    def test_stdin(self):
        """
        Making sure getPassword accepts a password from standard input by
        running a child process which uses getPassword to read in a string
        which it then writes it out again.  Write a string to the child
        process and then read one and make sure it is the right string.
        """
        p = PasswordTestingProcessProtocol()
        p.finished = Deferred()
        reactor.spawnProcess(
            p,
            sys.executable,
            [sys.executable,
             '-c',
             ('import sys\n'
             'from twisted.python.util import getPassword\n'
              'sys.stdout.write(getPassword())\n'
              'sys.stdout.flush()\n')],
            env={'PYTHONPATH': os.pathsep.join(sys.path)})

        def processFinished((reason, output)):
            reason.trap(ProcessDone)
            self.assertIn((1, 'secret'), output)

        return p.finished.addCallback(processFinished)



class SearchUpwardsTest(unittest.TestCase):
    def testSearchupwards(self):
        os.makedirs('searchupwards/a/b/c')
        file('searchupwards/foo.txt', 'w').close()
        file('searchupwards/a/foo.txt', 'w').close()
        file('searchupwards/a/b/c/foo.txt', 'w').close()
        os.mkdir('searchupwards/bar')
        os.mkdir('searchupwards/bam')
        os.mkdir('searchupwards/a/bar')
        os.mkdir('searchupwards/a/b/bam')
        actual=util.searchupwards('searchupwards/a/b/c',
                                  files=['foo.txt'],
                                  dirs=['bar', 'bam'])
        expected=os.path.abspath('searchupwards') + os.sep
        self.assertEqual(actual, expected)
        shutil.rmtree('searchupwards')
        actual=util.searchupwards('searchupwards/a/b/c',
                                  files=['foo.txt'],
                                  dirs=['bar', 'bam'])
        expected=None
        self.assertEqual(actual, expected)

class Foo:
    def __init__(self, x):
        self.x = x

class DSU(unittest.TestCase):
    def testDSU(self):
        L = [Foo(x) for x in range(20, 9, -1)]
        L2 = util.dsu(L, lambda o: o.x)
        self.assertEquals(range(10, 21), [o.x for o in L2])

class IntervalDifferentialTestCase(unittest.TestCase):
    def testDefault(self):
        d = iter(util.IntervalDifferential([], 10))
        for i in range(100):
            self.assertEquals(d.next(), (10, None))

    def testSingle(self):
        d = iter(util.IntervalDifferential([5], 10))
        for i in range(100):
            self.assertEquals(d.next(), (5, 0))

    def testPair(self):
        d = iter(util.IntervalDifferential([5, 7], 10))
        for i in range(100):
            self.assertEquals(d.next(), (5, 0))
            self.assertEquals(d.next(), (2, 1))
            self.assertEquals(d.next(), (3, 0))
            self.assertEquals(d.next(), (4, 1))
            self.assertEquals(d.next(), (1, 0))
            self.assertEquals(d.next(), (5, 0))
            self.assertEquals(d.next(), (1, 1))
            self.assertEquals(d.next(), (4, 0))
            self.assertEquals(d.next(), (3, 1))
            self.assertEquals(d.next(), (2, 0))
            self.assertEquals(d.next(), (5, 0))
            self.assertEquals(d.next(), (0, 1))

    def testTriple(self):
        d = iter(util.IntervalDifferential([2, 4, 5], 10))
        for i in range(100):
            self.assertEquals(d.next(), (2, 0))
            self.assertEquals(d.next(), (2, 0))
            self.assertEquals(d.next(), (0, 1))
            self.assertEquals(d.next(), (1, 2))
            self.assertEquals(d.next(), (1, 0))
            self.assertEquals(d.next(), (2, 0))
            self.assertEquals(d.next(), (0, 1))
            self.assertEquals(d.next(), (2, 0))
            self.assertEquals(d.next(), (0, 2))
            self.assertEquals(d.next(), (2, 0))
            self.assertEquals(d.next(), (0, 1))
            self.assertEquals(d.next(), (2, 0))
            self.assertEquals(d.next(), (1, 2))
            self.assertEquals(d.next(), (1, 0))
            self.assertEquals(d.next(), (0, 1))
            self.assertEquals(d.next(), (2, 0))
            self.assertEquals(d.next(), (2, 0))
            self.assertEquals(d.next(), (0, 1))
            self.assertEquals(d.next(), (0, 2))

    def testInsert(self):
        d = iter(util.IntervalDifferential([], 10))
        self.assertEquals(d.next(), (10, None))
        d.addInterval(3)
        self.assertEquals(d.next(), (3, 0))
        self.assertEquals(d.next(), (3, 0))
        d.addInterval(6)
        self.assertEquals(d.next(), (3, 0))
        self.assertEquals(d.next(), (3, 0))
        self.assertEquals(d.next(), (0, 1))
        self.assertEquals(d.next(), (3, 0))
        self.assertEquals(d.next(), (3, 0))
        self.assertEquals(d.next(), (0, 1))

    def testRemove(self):
        d = iter(util.IntervalDifferential([3, 5], 10))
        self.assertEquals(d.next(), (3, 0))
        self.assertEquals(d.next(), (2, 1))
        self.assertEquals(d.next(), (1, 0))
        d.removeInterval(3)
        self.assertEquals(d.next(), (4, 0))
        self.assertEquals(d.next(), (5, 0))
        d.removeInterval(5)
        self.assertEquals(d.next(), (10, None))
        self.assertRaises(ValueError, d.removeInterval, 10)


class EQ(object, util.FancyEqMixin):
    compareAttributes = ('a', 'b')
    def __init__(self, a, b):
        self.a, self.b = a, b

class Bar(object):
    pass

class TestFancyEqMixin(unittest.TestCase):

    def testIsInstance(self):
        eq = EQ(8, 9)
        f = Bar()
        self.failIfEqual(eq, f)

    def testEquality(self):
        ea, eb = EQ(1, 2), EQ(1, 2)

        self.failUnlessEqual(ea, eb)
        self.failUnlessEqual(eb, ea)
        self.failUnlessEqual((ea != eb), False)
        self.failUnlessEqual((eb != ea), False)



class IProxiedInterface(Interface):
    """
    An interface class for use by L{proxyForInterface}.
    """

    ifaceAttribute = Attribute("""
        An example declared attribute, which should be proxied.""")

    def yay(*a, **kw):
        """
        A sample method which should be proxied.
        """

class IProxiedSubInterface(IProxiedInterface):
    """
    An interface that derives from another for use with L{proxyForInterface}.
    """

    def boo(self):
        """
        A different sample method which should be proxied.
        """



class Yayable(object):
    """
    A provider of L{IProxiedInterface} which increments a counter for
    every call to C{yay}.

    @ivar yays: The number of times C{yay} has been called.
    """
    implements(IProxiedInterface)

    def __init__(self):
        self.yays = 0
        self.yayArgs = []

    def yay(self, *a, **kw):
        """
        Increment C{self.yays}.
        """
        self.yays += 1
        self.yayArgs.append((a, kw))
        return self.yays


class Booable(object):
    """
    An implementation of IProxiedSubInterface
    """
    implements(IProxiedSubInterface)
    yayed = False
    booed = False
    def yay(self):
        """
        Mark the fact that 'yay' has been called.
        """
        self.yayed = True


    def boo(self):
        """
        Mark the fact that 'boo' has been called.1
        """
        self.booed = True



class IMultipleMethods(Interface):
    """
    An interface with multiple methods.
    """

    def methodOne():
        """
        The first method. Should return 1.
        """

    def methodTwo():
        """
        The second method. Should return 2.
        """



class MultipleMethodImplementor(object):
    """
    A precise implementation of L{IMultipleMethods}.
    """

    def methodOne(self):
        """
        @return: 1
        """
        return 1


    def methodTwo(self):
        """
        @return: 2
        """
        return 2



class ProxyForInterfaceTests(unittest.TestCase):
    """
    Tests for L{proxyForInterface}.
    """

    def test_original(self):
        """
        Proxy objects should have an C{original} attribute which refers to the
        original object passed to the constructor.
        """
        original = object()
        proxy = proxyForInterface(IProxiedInterface)(original)
        self.assertIdentical(proxy.original, original)


    def test_proxyMethod(self):
        """
        The class created from L{proxyForInterface} passes methods on an
        interface to the object which is passed to its constructor.
        """
        klass = proxyForInterface(IProxiedInterface)
        yayable = Yayable()
        proxy = klass(yayable)
        proxy.yay()
        self.assertEquals(proxy.yay(), 2)
        self.assertEquals(yayable.yays, 2)


    def test_proxyAttribute(self):
        """
        Proxy objects should proxy declared attributes, but not other
        attributes.
        """
        yayable = Yayable()
        yayable.ifaceAttribute = object()
        proxy = proxyForInterface(IProxiedInterface)(yayable)
        self.assertIdentical(proxy.ifaceAttribute, yayable.ifaceAttribute)
        self.assertRaises(AttributeError, lambda: proxy.yays)


    def test_proxySetAttribute(self):
        """
        The attributes that proxy objects proxy should be assignable and affect
        the original object.
        """
        yayable = Yayable()
        proxy = proxyForInterface(IProxiedInterface)(yayable)
        thingy = object()
        proxy.ifaceAttribute = thingy
        self.assertIdentical(yayable.ifaceAttribute, thingy)


    def test_proxyDeleteAttribute(self):
        """
        The attributes that proxy objects proxy should be deletable and affect
        the original object.
        """
        yayable = Yayable()
        yayable.ifaceAttribute = None
        proxy = proxyForInterface(IProxiedInterface)(yayable)
        del proxy.ifaceAttribute
        self.assertFalse(hasattr(yayable, 'ifaceAttribute'))


    def test_multipleMethods(self):
        """
        [Regression test] The proxy should send its method calls to the correct
        method, not the incorrect one.
        """
        multi = MultipleMethodImplementor()
        proxy = proxyForInterface(IMultipleMethods)(multi)
        self.assertEquals(proxy.methodOne(), 1)
        self.assertEquals(proxy.methodTwo(), 2)


    def test_subclassing(self):
        """
        It is possible to subclass the result of L{proxyForInterface}.
        """

        class SpecializedProxy(proxyForInterface(IProxiedInterface)):
            """
            A specialized proxy which can decrement the number of yays.
            """
            def boo(self):
                """
                Decrement the number of yays.
                """
                self.original.yays -= 1

        yayable = Yayable()
        special = SpecializedProxy(yayable)
        self.assertEquals(yayable.yays, 0)
        special.boo()
        self.assertEquals(yayable.yays, -1)


    def test_proxyName(self):
        """
        The name of a proxy class indicates which interface it proxies.
        """
        proxy = proxyForInterface(IProxiedInterface)
        self.assertEquals(
            proxy.__name__,
            "(Proxy for twisted.test.test_util.IProxiedInterface)")


    def test_provides(self):
        """
        The resulting proxy provides the Interface that it proxies.
        """
        proxy = proxyForInterface(IProxiedInterface)
        self.assertTrue(IProxiedInterface.providedBy(proxy))


    def test_proxyDescriptorGet(self):
        """
        _ProxyDescriptor's __get__ method should return the appropriate
        attribute of its argument's 'original' attribute if it is invoked with
        an object.  If it is invoked with None, it should return a false
        class-method emulator instead.

        For some reason, Python's documentation recommends to define
        descriptors' __get__ methods with the 'type' parameter as optional,
        despite the fact that Python itself never actually calls the descriptor
        that way.  This is probably do to support 'foo.__get__(bar)' as an
        idiom.  Let's make sure that the behavior is correct.  Since we don't
        actually use the 'type' argument at all, this test calls it the
        idiomatic way to ensure that signature works; test_proxyInheritance
        verifies the how-Python-actually-calls-it signature.
        """
        class Sample:
            called = False
            def hello(self):
                self.called = True
        fakeProxy = Sample()
        testObject = Sample()
        fakeProxy.original = testObject
        pd = util._ProxyDescriptor("hello")
        self.assertEquals(pd.__get__(fakeProxy), testObject.hello)
        fakeClassMethod = pd.__get__(None)
        fakeClassMethod(fakeProxy)
        self.failUnless(testObject.called)


    def test_proxyInheritance(self):
        """
        Subclasses of the class returned from L{proxyForInterface} should be
        able to upcall methods by reference to their superclass, as any normal
        Python class can.
        """
        class YayableWrapper(proxyForInterface(IProxiedInterface)):
            """
            This class does not override any functionality.
            """

        class EnhancedWrapper(YayableWrapper):
            """
            This class overrides the 'yay' method.
            """
            wrappedYays = 1
            def yay(self, *a, **k):
                self.wrappedYays += 1
                return YayableWrapper.yay(self, *a, **k) + 7

        yayable = Yayable()
        wrapper = EnhancedWrapper(yayable)
        self.assertEquals(wrapper.yay(3, 4, x=5, y=6), 8)
        self.assertEquals(yayable.yayArgs,
                          [((3, 4), dict(x=5, y=6))])


    def test_interfaceInheritance(self):
        """
        Proxies of subinterfaces generated with proxyForInterface should allow
        access to attributes of both the child and the base interfaces.
        """
        proxyClass = proxyForInterface(IProxiedSubInterface)
        booable = Booable()
        proxy = proxyClass(booable)
        proxy.yay()
        proxy.boo()
        self.failUnless(booable.yayed)
        self.failUnless(booable.booed)
