# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.persisted.aot}.
"""

import sys
import StringIO

from twisted.trial.unittest import SynchronousTestCase
from twisted.persisted.aot import (
    AOTJellier, unjellyFromSource, jellyToSource, jellyToAOT, unjellyFromAOT)


class A:
    """
    dummy class
    """
    def amethod(self):
        pass



class B:
    """
    dummy class
    """
    def bmethod(self):
        pass



def funktion():
    pass



class NonDictState:
    def __getstate__(self):
        return self.state
    def __setstate__(self, state):
        self.state = state



class EvilSourceror:
    def __init__(self, x):
        self.a = self
        self.a.b = self
        self.a.b.c = x



class AOTTestCase(SynchronousTestCase):
    def testSimpleTypes(self):
        obj = (1, 2.0, 3j, True, slice(1, 2, 3), 'hello', u'world', sys.maxint + 1, None, Ellipsis)
        rtObj = unjellyFromSource(jellyToSource(obj))
        self.assertEqual(obj, rtObj)

    def testMethodSelfIdentity(self):
        a = A()
        b = B()
        a.bmethod = b.bmethod
        b.a = a
        im_ = unjellyFromSource(jellyToSource(b)).a.bmethod
        self.assertEqual(im_.im_class, im_.im_self.__class__)


    def test_methodNotSelfIdentity(self):
        """
        If a class change after an instance has been created,
        L{unjellyFromSource} shoud raise a C{TypeError} when trying to
        unjelly the instance.
        """
        a = A()
        b = B()
        a.bmethod = b.bmethod
        b.a = a
        savedbmethod = B.bmethod
        del B.bmethod
        try:
            self.assertRaises(TypeError, unjellyFromSource,
                              jellyToSource(b))
        finally:
            B.bmethod = savedbmethod


    def test_unsupportedType(self):
        """
        L{jellyToSource} should raise a C{TypeError} when trying to jelly
        an unknown type.
        """
        try:
            set
        except:
            from sets import Set as set
        self.assertRaises(TypeError, jellyToSource, set())


    def testBasicIdentity(self):
        # Anyone wanting to make this datastructure more complex, and thus this
        # test more comprehensive, is welcome to do so.
        import twisted
        aj = AOTJellier().jellyToAO
        d = {'hello': 'world', "method": aj}
        l = [1, 2, 3,
             "he\tllo\n\n\"x world!",
             u"goodbye \n\t\u1010 world!",
             1, 1.0, 100 ** 100l, twisted, AOTJellier, d,
             funktion
             ]
        t = tuple(l)
        l.append(l)
        l.append(t)
        l.append(t)
        uj = unjellyFromSource(jellyToSource([l, l]))
        assert uj[0] is uj[1]
        assert uj[1][0:5] == l[0:5]


    def testNonDictState(self):
        a = NonDictState()
        a.state = "meringue!"
        assert unjellyFromSource(jellyToSource(a)).state == a.state

    def testCopyReg(self):
        s = "foo_bar"
        sio = StringIO.StringIO()
        sio.write(s)
        uj = unjellyFromSource(jellyToSource(sio))
        # print repr(uj.__dict__)
        assert uj.getvalue() == s

    def testFunkyReferences(self):
        o = EvilSourceror(EvilSourceror([]))
        j1 = jellyToAOT(o)
        oj = unjellyFromAOT(j1)

        assert oj.a is oj
        assert oj.a.b is oj.b
        assert oj.c is not oj.c.c
