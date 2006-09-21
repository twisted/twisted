# Copyright (c) 2006 Twisted Matrix Laboratories.
# See LICENSE for details.

from cStringIO import StringIO

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


    def test_goodSVNEntries(self):
        """
        Version should be able to parse an SVN entries file.
        """
        version = Version("dummy", 1, 0, 0)
        crap = '''<?xml version="1.0" encoding="utf-8"?>
<wc-entries
   xmlns="svn:">
<entry
   committed-rev="18210"
   name=""
   committed-date="2006-09-21T04:43:09.542953Z"
   url="svn+ssh://svn.twistedmatrix.com/svn/Twisted/trunk/twisted"
   last-author="exarkun"
   kind="dir"
   uuid="bbbe8e31-12d6-0310-92fd-ac37d47ddeeb"
   repos="svn+ssh://svn.twistedmatrix.com/svn/Twisted"
   revision="18211"/>
</wc-entries>
'''
        self.assertEquals(version._parseSVNEntries(StringIO(crap)), '18211')


    def test_parseBrokenSVNEntries(self):
        """
        If there is a broken SVN entries file, it should return an SVN
        revision of "Unknown".
        """
        version = Version("dummy", 1, 0, 0)
        self.assertEquals(version._parseSVNEntries(StringIO('I like puppies')), 
                          "Unknown")
