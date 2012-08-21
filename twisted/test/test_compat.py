# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Tests for L{twisted.python.compat}.
"""

from __future__ import division


import tempfile, socket, sys

# We will replace stdlib TestCase with SynchronousTestCase as part of ticket
# #5885:
import unittest

from twisted.python.compat import set, frozenset, reduce, execfile, _PY3



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
