# -*- test-case-name: twisted.test.test_util -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.trial import unittest

from twisted.python import util
from twisted.python.runtime import platformType
import os.path, sys
import shutil, errno

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




def reversePassword():
    password = util.getPassword()
    return reverseString(password)

def reverseString(s):
    s = list(s)
    s.reverse()
    s = ''.join(s)
    return s

class GetPasswordTest(unittest.TestCase):
    def testStdIn(self):
        """Making sure getPassword accepts a password from standard input.
        """
        from os import path
        import twisted
        # Fun path games because for my sub-process, 'import twisted'
        # doesn't always point to the package containing this test
        # module.
        script = """\
import sys
sys.path.insert(0, \"%(dir)s\")
from twisted.test import test_util
print test_util.util.__version__
print test_util.reversePassword()
""" % {'dir': path.dirname(path.dirname(twisted.__file__))}
        cmd_in, cmd_out, cmd_err = os.popen3("%(python)s -c '%(script)s'" %
                                             {'python': sys.executable,
                                              'script': script})
        cmd_in.write("secret\n")
        cmd_in.close()
        try:
            errors = cmd_err.read()
        except IOError, e:
            # XXX: Improper kludge to appease buildbot!  I'm not really sure
            # why this happens, and without that knowledge, I SHOULDN'T be
            # just catching and discarding this error.
            import errno
            if e.errno == errno.EINTR:
                errors = ''
            else:
                raise
        self.failIf(errors, errors)
        uversion = cmd_out.readline()[:-1]
        self.failUnlessEqual(uversion, util.__version__,
                             "I want to test module version %r, "
                             "but the subprocess is using version %r." %
                             (util.__version__, uversion))
        # stripping print's trailing newline.
        secret = cmd_out.read()[:-1]
        # The reversing trick it so make sure that there's not some weird echo
        # thing just sending back what we type in.
        self.failUnlessEqual(reverseString(secret), "secret")

    if platformType != "posix":
        testStdIn.skip = "unix only"


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
