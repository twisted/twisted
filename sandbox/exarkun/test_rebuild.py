
# -*- coding: Latin-1 -*-

from twisted.python.plugin import DropIn

d = DropIn("x")
execfile("plugins.tml", {'register': d.register})

import ctd
from rebuild import rebuild

from twisted.trial import unittest

class RebuildTest(unittest.TestCase):
    def testBuiltinTypes(self):
        L = [1, 1.0, 1L, 1j]
        L.append(["Foo", u"Foo", ("Bar",), {'baz': 10}])
        
        newL = rebuild(L)
        
        self.failIfIdentical(L, newL)
        self.assertEquals(L, newL)
    
    def testFile(self):
        F = file(self.mktemp(), 'w')
        newF = rebuild(F)
        self.assertEquals(F, newF)
    
    def testBoundMethod(self):
        M = ctd.Class().method
        reload(ctd)
        newM = rebuild(M)
        self.failIfIdentical(M, newM)

    def testUnboundMethod(self):
        M = ctd.Class.method
        reload(ctd)
        newM = rebuild(M)
        self.failIfIdentical(M, newM)

    def testFunction(self):
        F = ctd.Function
        reload(ctd)
        newF = rebuild(F)
        self.failIfIdentical(F, newF)

    def testStaticMethod(self):
        S = ctd.Class.smethod
        newS = rebuild(S)
        self.failIfIdentical(S, newS)

    def testClassMethod(self):
        C = ctd.Class.cmethod
        newC = rebuild(C)
        self.failIfIdentical(C, newC)

    def testInstance(self):
        i = ctd.Class()
        i.x = 10
        i.y = 20
        i.z = ctd.Class()
        i.z.x = ["Foo"]

        newI = rebuild(i)

        self.failIfIdentical(i, newI)

        self.assertEqual(i.x, newI.x)
        self.assertEqual(i.y, newI.y)
        self.assertEqual(i.z.x, newI.z.x)
        self.failIfIdentical(i.z, newI.z)
        self.failIfIdentical(i.z.x, newI.z.x)

    




