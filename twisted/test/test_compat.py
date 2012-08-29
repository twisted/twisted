# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Tests for L{twisted.python.compat}.
"""

from __future__ import division, absolute_import

import tempfile, socket, sys, traceback

# We will replace stdlib TestCase with SynchronousTestCase as part of ticket
# #5885:
import unittest

from twisted.python.compat import set, frozenset, reduce, execfile, _PY3
from twisted.python.compat import comparable, cmp, nativeString
from twisted.python.compat import unicode as unicodeCompat
from twisted.python.compat import reraise


class CompatTestCase(unittest.TestCase):
    """
    Various utility functions in C{twisted.python.compat} provide same
    functionality as modern Python variants.
    """

    def test_set(self):
        """
        L{set} should behave like the expected set interface.
        """
        a = set()
        a.add('b')
        a.add('c')
        a.add('a')
        b = list(a)
        b.sort()
        self.assertEqual(b, ['a', 'b', 'c'])
        a.remove('b')
        b = list(a)
        b.sort()
        self.assertEqual(b, ['a', 'c'])

        a.discard('d')

        b = set(['r', 's'])
        d = a.union(b)
        b = list(d)
        b.sort()
        self.assertEqual(b, ['a', 'c', 'r', 's'])


    def test_frozenset(self):
        """
        L{frozenset} should behave like the expected frozenset interface.
        """
        a = frozenset(['a', 'b'])
        self.assertRaises(AttributeError, getattr, a, "add")
        self.assertEqual(sorted(a), ['a', 'b'])

        b = frozenset(['r', 's'])
        d = a.union(b)
        b = list(d)
        b.sort()
        self.assertEqual(b, ['a', 'b', 'r', 's'])


    def test_reduce(self):
        """
        L{reduce} should behave like the builtin reduce.
        """
        self.assertEqual(15, reduce(lambda x, y: x + y, [1, 2, 3, 4, 5]))
        self.assertEqual(16, reduce(lambda x, y: x + y, [1, 2, 3, 4, 5], 1))



class IPv6Tests(unittest.TestCase):
    """
    C{inet_pton} and C{inet_ntop} implementations support IPv6.
    """

    def testNToP(self):
        from twisted.python.compat import inet_ntop

        f = lambda a: inet_ntop(socket.AF_INET6, a)
        g = lambda a: inet_ntop(socket.AF_INET, a)

        self.assertEqual('::', f('\x00' * 16))
        self.assertEqual('::1', f('\x00' * 15 + '\x01'))
        self.assertEqual(
            'aef:b01:506:1001:ffff:9997:55:170',
            f('\x0a\xef\x0b\x01\x05\x06\x10\x01\xff\xff\x99\x97\x00\x55\x01\x70'))

        self.assertEqual('1.0.1.0', g('\x01\x00\x01\x00'))
        self.assertEqual('170.85.170.85', g('\xaa\x55\xaa\x55'))
        self.assertEqual('255.255.255.255', g('\xff\xff\xff\xff'))

        self.assertEqual('100::', f('\x01' + '\x00' * 15))
        self.assertEqual('100::1', f('\x01' + '\x00' * 14 + '\x01'))

    def testPToN(self):
        from twisted.python.compat import inet_pton

        f = lambda a: inet_pton(socket.AF_INET6, a)
        g = lambda a: inet_pton(socket.AF_INET, a)

        self.assertEqual('\x00\x00\x00\x00', g('0.0.0.0'))
        self.assertEqual('\xff\x00\xff\x00', g('255.0.255.0'))
        self.assertEqual('\xaa\xaa\xaa\xaa', g('170.170.170.170'))

        self.assertEqual('\x00' * 16, f('::'))
        self.assertEqual('\x00' * 16, f('0::0'))
        self.assertEqual('\x00\x01' + '\x00' * 14, f('1::'))
        self.assertEqual(
            '\x45\xef\x76\xcb\x00\x1a\x56\xef\xaf\xeb\x0b\xac\x19\x24\xae\xae',
            f('45ef:76cb:1a:56ef:afeb:bac:1924:aeae'))

        self.assertEqual('\x00' * 14 + '\x00\x01', f('::1'))
        self.assertEqual('\x00' * 12 + '\x01\x02\x03\x04', f('::1.2.3.4'))
        self.assertEqual(
            '\x00\x01\x00\x02\x00\x03\x00\x04\x00\x05\x00\x06\x01\x02\x03\xff',
            f('1:2:3:4:5:6:1.2.3.255'))

        for badaddr in ['1:2:3:4:5:6:7:8:', ':1:2:3:4:5:6:7:8', '1::2::3',
                        '1:::3', ':::', '1:2', '::1.2', '1.2.3.4::',
                        'abcd:1.2.3.4:abcd:abcd:abcd:abcd:abcd',
                        '1234:1.2.3.4:1234:1234:1234:1234:1234:1234',
                        '1.2.3.4']:
            self.assertRaises(ValueError, f, badaddr)

# No skip support until SynchronousTestCase is available; ticket #5885 will
# involve switching this to using skipping. Ticket #5895 covers deprecating
# the tested functions, since they are no longer needed anywhere.
if _PY3:
    del IPv6Tests



class ExecfileCompatTestCase(unittest.TestCase):
    """
    Tests for the Python 3-friendly L{execfile} implementation.
    """

    # We haven't ported FilePath to Python 3.3 yet; once we do, we can change
    # this class back to using FilePath (see ticket #5884).
    class FakeFilePath(object):
        def __init__(self, path):
            self.path = path


    # We haven't ported unittest to Python 3.3 yet; once we can subclass from
    # SynchronousTestCase we can delete this (see ticket #5885).
    def mktemp(self):
        return tempfile.mktemp()


    def writeScript(self, content):
        """
        Write L{content} to a new temporary file, returning the L{FilePath}
        for the new file.
        """
        path = self.mktemp()
        with open(path, "wb") as f:
            f.write(content.encode("ascii"))
        return self.FakeFilePath(path)


    def test_execfileGlobals(self):
        """
        L{execfile} executes the specified file in the given global namespace.
        """
        script = self.writeScript(u"foo += 1\n")
        globalNamespace = {"foo": 1}
        execfile(script.path, globalNamespace)
        self.assertEqual(2, globalNamespace["foo"])


    def test_execfileGlobalsAndLocals(self):
        """
        L{execfile} executes the specified file in the given global and local
        namespaces.
        """
        script = self.writeScript(u"foo += 1\n")
        globalNamespace = {"foo": 10}
        localNamespace = {"foo": 20}
        execfile(script.path, globalNamespace, localNamespace)
        self.assertEqual(10, globalNamespace["foo"])
        self.assertEqual(21, localNamespace["foo"])


    def test_execfileUniversalNewlines(self):
        """
        L{execfile} reads in the specified file using universal newlines so
        that scripts written on one platform will work on another.
        """
        for lineEnding in u"\n", u"\r", u"\r\n":
            script = self.writeScript(u"foo = 'okay'" + lineEnding)
            globalNamespace = {"foo": None}
            execfile(script.path, globalNamespace)
            self.assertEqual("okay", globalNamespace["foo"])



class PY3Tests(unittest.TestCase):
    """
    Identification of Python 2 vs. Python 3.
    """

    def test_python2(self):
        """
        On Python 2, C{_PY3} is False.
        """
        if sys.version.startswith("2."):
            self.assertFalse(_PY3)


    def test_python3(self):
        """
        On Python 3, C{_PY3} is True.
        """
        if sys.version.startswith("3."):
            self.assertTrue(_PY3)



@comparable
class Comparable(object):
    """
    Objects that can be compared to each other, but not others.
    """
    def __init__(self, value):
        self.value = value


    def __cmp__(self, other):
        if not isinstance(other, Comparable):
            return NotImplemented
        return cmp(self.value, other.value)



class ComparableTests(unittest.TestCase):
    """
    L{comparable} decorated classes emulate Python 2's C{__cmp__} semantics.
    """

    def test_equality(self):
        """
        Instances of a class that is decorated by C{comparable} support
        equality comparisons.
        """
        # Make explicitly sure we're using ==:
        self.assertTrue(Comparable(1) == Comparable(1))
        self.assertFalse(Comparable(2) == Comparable(1))


    def test_nonEquality(self):
        """
        Instances of a class that is decorated by C{comparable} support
        inequality comparisons.
        """
        # Make explicitly sure we're using !=:
        self.assertFalse(Comparable(1) != Comparable(1))
        self.assertTrue(Comparable(2) != Comparable(1))


    def test_greaterThan(self):
        """
        Instances of a class that is decorated by C{comparable} support
        greater-than comparisons.
        """
        self.assertTrue(Comparable(2) > Comparable(1))
        self.assertFalse(Comparable(0) > Comparable(3))


    def test_greaterThanOrEqual(self):
        """
        Instances of a class that is decorated by C{comparable} support
        greater-than-or-equal comparisons.
        """
        self.assertTrue(Comparable(1) >= Comparable(1))
        self.assertTrue(Comparable(2) >= Comparable(1))
        self.assertFalse(Comparable(0) >= Comparable(3))


    def test_lessThan(self):
        """
        Instances of a class that is decorated by C{comparable} support
        less-than comparisons.
        """
        self.assertTrue(Comparable(0) < Comparable(3))
        self.assertFalse(Comparable(2) < Comparable(0))


    def test_lessThanOrEqual(self):
        """
        Instances of a class that is decorated by C{comparable} support
        less-than-or-equal comparisons.
        """
        self.assertTrue(Comparable(3) <= Comparable(3))
        self.assertTrue(Comparable(0) <= Comparable(3))
        self.assertFalse(Comparable(2) <= Comparable(0))



class Python3ComparableTests(unittest.TestCase):
    """
    Python 3-specific functionality of C{comparable}.
    """

    def test_notImplementedEquals(self):
        """
        Instances of a class that is decorated by C{comparable} support
        returning C{NotImplemented} from C{__eq__} if it is returned by the
        underlying C{__cmp__} call.
        """
        self.assertEqual(Comparable(1).__eq__(object()), NotImplemented)


    def test_notImplementedNotEquals(self):
        """
        Instances of a class that is decorated by C{comparable} support
        returning C{NotImplemented} from C{__ne__} if it is returned by the
        underlying C{__cmp__} call.
        """
        self.assertEqual(Comparable(1).__ne__(object()), NotImplemented)


    def test_notImplementedGreaterThan(self):
        """
        Instances of a class that is decorated by C{comparable} support
        returning C{NotImplemented} from C{__gt__} if it is returned by the
        underlying C{__cmp__} call.
        """
        self.assertEqual(Comparable(1).__gt__(object()), NotImplemented)


    def test_notImplementedLessThan(self):
        """
        Instances of a class that is decorated by C{comparable} support
        returning C{NotImplemented} from C{__lt__} if it is returned by the
        underlying C{__cmp__} call.
        """
        self.assertEqual(Comparable(1).__lt__(object()), NotImplemented)


    def test_notImplementedGreaterThanEquals(self):
        """
        Instances of a class that is decorated by C{comparable} support
        returning C{NotImplemented} from C{__ge__} if it is returned by the
        underlying C{__cmp__} call.
        """
        self.assertEqual(Comparable(1).__ge__(object()), NotImplemented)


    def test_notImplementedLessThanEquals(self):
        """
        Instances of a class that is decorated by C{comparable} support
        returning C{NotImplemented} from C{__le__} if it is returned by the
        underlying C{__cmp__} call.
        """
        self.assertEqual(Comparable(1).__le__(object()), NotImplemented)

if not _PY3:
    # On Python 2, we just use __cmp__ directly, so checking detailed
    # comparison methods doesn't makes sense; this should be replaced with
    # skip as part of ticket #5885.
    del Python3ComparableTests



class CmpTests(unittest.TestCase):
    """
    L{cmp} should behave like the built-in Python 2 C{cmp}.
    """

    def test_equals(self):
        """
        L{cmp} returns 0 for equal objects.
        """
        self.assertEqual(cmp(u"a", u"a"), 0)
        self.assertEqual(cmp(1, 1), 0)
        self.assertEqual(cmp([1], [1]), 0)


    def test_greaterThan(self):
        """
        L{cmp} returns 1 if its first argument is bigger than its second.
        """
        self.assertEqual(cmp(4, 0), 1)
        self.assertEqual(cmp(b"z", b"a"), 1)


    def test_lessThan(self):
        """
        L{cmp} returns -1 if its first argument is smaller than its second.
        """
        self.assertEqual(cmp(0.1, 2.3), -1)
        self.assertEqual(cmp(b"a", b"d"), -1)



class StringTests(unittest.TestCase):
    """
    Compatability functions and types for strings.
    """
    # This can be deleted when we switch back to trial.  #5885.
    def assertIsInstance(self, instance, classOrTuple, message=None):
        """
        Fail if C{instance} is not an instance of the given class or of
        one of the given classes.

        @param instance: the object to test the type (first argument of the
            C{isinstance} call).
        @type instance: any.
        @param classOrTuple: the class or classes to test against (second
            argument of the C{isinstance} call).
        @type classOrTuple: class, type, or tuple.

        @param message: Custom text to include in the exception text if the
            assertion fails.
        """
        if not isinstance(instance, classOrTuple):
            if message is None:
                suffix = ""
            else:
                suffix = ": " + message
            self.fail("%r is not an instance of %s%s" % (
                    instance, classOrTuple, suffix))


    def assertNativeString(self, original, expected):
        """
        Raise an exception indicating a failed test if the output of
        C{nativeString(original)} is unequal to the expected string, or is not
        a native string.
        """
        self.assertEqual(nativeString(original), expected)
        self.assertIsInstance(nativeString(original), str)


    def test_nonASCIIBytesToString(self):
        """
        C{nativeString} raises a C{UnicodeError} if input bytes are not ASCII
        decodable.
        """
        self.assertRaises(UnicodeError, nativeString, b"\xFF")


    def test_nonASCIIUnicodeToString(self):
        """
        C{nativeString} raises a C{UnicodeError} if input Unicode is not ASCII
        encodable.
        """
        self.assertRaises(UnicodeError, nativeString, u"\u1234")


    def test_bytesToString(self):
        """
        C{nativeString} converts bytes to the native string format, assuming
        an ASCII encoding if applicable.
        """
        self.assertNativeString(b"hello", "hello")


    def test_unicodeToString(self):
        """
        C{nativeString} converts unicode to the native string format, assuming
        an ASCII encoding if applicable.
        """
        self.assertNativeString(u"Good day", "Good day")


    def test_stringToString(self):
        """
        C{nativeString} leaves native strings as native strings.
        """
        self.assertNativeString("Hello!", "Hello!")


    def test_unexpectedType(self):
        """
        C{nativeString} raises a C{TypeError} if given an object that is not a
        string of some sort.
        """
        self.assertRaises(TypeError, nativeString, 1)


    def test_unicode(self):
        """
        C{compat.unicode} is C{str} on Python 3, C{unicode} on Python 2.
        """
        if _PY3:
            expected = str
        else:
            expected = unicode
        self.assertTrue(unicodeCompat is expected)



class ReraiseTests(unittest.TestCase):
    """
    L{reraise} re-raises exceptions on both Python 2 and Python 3.
    """

    def test_reraiseWithNone(self):
        """
        Calling L{reraise} with an exception instance and a traceback of
        C{None} re-raises it with a new traceback.
        """
        try:
            1/0
        except:
            typ, value, tb = sys.exc_info()
        try:
            reraise(value, None)
        except:
            typ2, value2, tb2 = sys.exc_info()
            self.assertEqual(typ2, ZeroDivisionError)
            self.assertTrue(value is value2)
            self.assertNotEqual(traceback.format_tb(tb)[-1],
                                traceback.format_tb(tb2)[-1])
        else:
            self.fail("The exception was not raised.")


    def test_reraiseWithTraceback(self):
        """
        Calling L{reraise} with an exception instance and a traceback
        re-raises the exception with the given traceback.
        """
        try:
            1/0
        except:
            typ, value, tb = sys.exc_info()
        try:
            reraise(value, tb)
        except:
            typ2, value2, tb2 = sys.exc_info()
            self.assertEqual(typ2, ZeroDivisionError)
            self.assertTrue(value is value2)
            self.assertEqual(traceback.format_tb(tb)[-1],
                             traceback.format_tb(tb2)[-1])
        else:
            self.fail("The exception was not raised.")
