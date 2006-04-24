# Copyright (c) 2006 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.python.versions import Version, IncomparableVersions

from twisted.trial import unittest

class VersionsTest(unittest.TestCase):
    def testVersionComparison(self):
        va = Version("dummy", 1, 0, 0)
        vb = Version("dummy", 0, 1, 0)
        self.failUnless(va > vb)
        self.failUnless(vb < va)
        self.failUnless(va >= vb)
        self.failUnless(vb <= va)
        self.failUnless(va != vb)
        self.failUnless(vb == Version("dummy", 0, 1, 0))
        self.failUnless(vb == vb)

        # BREAK IT DOWN@!!
        self.failIf(va < vb)
        self.failIf(vb > va)
        self.failIf(va <= vb)
        self.failIf(vb >= va)
        self.failIf(va == vb)
        self.failIf(vb != Version("dummy", 0, 1, 0))
        self.failIf(vb != vb)

    def testDontAllowBuggyComparisons(self):
        self.assertRaises(IncomparableVersions,
                          cmp,
                          Version("dummy", 1, 0, 0),
                          Version("dumym", 1, 0, 0))

    def testRepr(self):
        repr(Version("dummy", 1, 2, 3))

    def testStr(self):
        str(Version("dummy", 1, 2, 3))

    def testShort(self):
        self.assertEquals(Version('dummy', 1, 2, 3).short(),
                          '1.2.3')
