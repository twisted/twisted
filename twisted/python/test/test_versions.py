# Copyright (c) 2006-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

import sys
from cStringIO import StringIO

from twisted.python.versions import getVersionString, IncomparableVersions
from twisted.python.versions import Version
from twisted.python.filepath import FilePath

from twisted.trial import unittest



VERSION_4_ENTRIES = """\
<?xml version="1.0" encoding="utf-8"?>
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
"""



VERSION_8_ENTRIES = """\
8

dir
22715
svn+ssh://svn.twistedmatrix.com/svn/Twisted/trunk
"""



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


    def test_goodSVNEntries_4(self):
        """
        Version should be able to parse an SVN format 4 entries file.
        """
        version = Version("dummy", 1, 0, 0)
        self.assertEquals(
            version._parseSVNEntries_4(StringIO(VERSION_4_ENTRIES)), '18211')


    def test_goodSVNEntries_8(self):
        """
        Version should be able to parse an SVN format 8 entries file.
        """
        version = Version("dummy", 1, 0, 0)
        self.assertEqual(
            version._parseSVNEntries_8(StringIO(VERSION_8_ENTRIES)), '22715')


    def test_getVersionString(self):
        """
        L{getVersionString} returns a string with the package name and the
        short version number.
        """
        self.assertEqual(
            'Twisted 8.0.0', getVersionString(Version('Twisted', 8, 0, 0)))



class FormatDiscoveryTests(unittest.TestCase):
    """
    Tests which discover the parsing method based on the imported module name.
    """

    def setUp(self):
        """
        Create a temporary directory with a package structure in it.
        """
        self.entry = FilePath(self.mktemp())
        self.preTestModules = sys.modules.copy()
        sys.path.append(self.entry.path)
        pkg = self.entry.child("twisted_python_versions_package")
        pkg.makedirs()
        pkg.child("__init__.py").setContent(
            "from twisted.python.versions import Version\n"
            "version = Version('twisted_python_versions_package', 1, 0, 0)\n")
        self.svnEntries = pkg.child(".svn")
        self.svnEntries.makedirs()


    def tearDown(self):
        """
        Remove the imported modules and sys.path modifications.
        """
        sys.modules.clear()
        sys.modules.update(self.preTestModules)
        sys.path.remove(self.entry.path)


    def checkSVNFormat(self, formatVersion, entriesText, expectedRevision):
        """
        Check for the given revision being detected after setting the SVN
        entries text and format version of the test directory structure.
        """
        self.svnEntries.child("format").setContent(formatVersion+"\n")
        self.svnEntries.child("entries").setContent(entriesText)
        self.assertEqual(self.getVersion()._getSVNVersion(), expectedRevision)


    def getVersion(self):
        """
        Import and retrieve the Version object from our dynamically created
        package.
        """
        import twisted_python_versions_package
        return twisted_python_versions_package.version


    def test_detectVersion4(self):
        """
        Verify that version 4 format file will be properly detected and parsed.
        """
        self.checkSVNFormat("4", VERSION_4_ENTRIES, '18211')


    def test_detectVersion8(self):
        """
        Verify that version 8 format files will be properly detected and
        parsed.
        """
        self.checkSVNFormat("8", VERSION_8_ENTRIES, '22715')


    def test_detectUnknownVersion(self):
        """
        Verify that a new version of SVN will result in the revision 'Unknown'.
        """
        self.checkSVNFormat("some-random-new-version", "ooga booga!", 'Unknown')


