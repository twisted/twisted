
import os, time, pickle

from twisted.python import filepath
from twisted.python.runtime import platform
from twisted.trial import unittest

class FilePathTestCase(unittest.TestCase):

    f1content = "file 1"
    f2content = "file 2"

    def setUp(self):
        self.now = time.time()
        cmn = self.mktemp()
        os.mkdir(cmn)
        os.mkdir(os.path.join(cmn,"sub1"))
        f = open(os.path.join(cmn, "file1"),"wb")
        f.write(self.f1content)
        f = open(os.path.join(cmn, "sub1", "file2"),"wb")
        f.write(self.f2content)
        os.mkdir(os.path.join(cmn, 'sub3'))
        f = open(os.path.join(cmn, "sub3", "file3.ext1"),"wb")
        f = open(os.path.join(cmn, "sub3", "file3.ext2"),"wb")
        f = open(os.path.join(cmn, "sub3", "file3.ext3"),"wb")
        self.path = filepath.FilePath(cmn)

    def testGetAndSet(self):
        content = 'newcontent'
        self.path.child('new').setContent(content)
        newcontent = self.path.child('new').getContent()
        self.failUnlessEqual(content, newcontent)
        content = 'content'
        self.path.child('new').setContent(content, '.tmp')
        newcontent = self.path.child('new').getContent()
        self.failUnlessEqual(content, newcontent)

    if platform.getType() == 'win32':
        testGetAndSet.todo = "os.rename in FilePath.setContent doesn't work too well on Windows"

    def testValidSubdir(self):
        sub1 = self.path.child('sub1')
        self.failUnless(sub1.exists(),
                        "This directory does exist.")
        self.failUnless(sub1.isdir(),
                        "It's a directory.")
        self.failUnless(not sub1.isfile(),
                        "It's a directory.")
        self.failUnless(not sub1.islink(),
                        "It's a directory.")
        self.failUnlessEqual(sub1.listdir(),
                             ['file2'])

    def testMultiExt(self):
        f3 = self.path.child('sub3').child('file3')
        exts = '.foo','.bar', 'ext1','ext2','ext3'
        self.failIf(f3.siblingExtensionSearch(*exts))
        f3e = f3.siblingExtension(".foo")
        f3e.touch()
        self.failIf(not f3.siblingExtensionSearch(*exts).exists())
        self.failIf(not f3.siblingExtensionSearch('*').exists())
        f3e.remove()
        self.failIf(f3.siblingExtensionSearch(*exts))

    def testInvalidSubdir(self):
        sub2 = self.path.child('sub2')
        self.failIf(sub2.exists(),
                    "This directory does not exist.")

    def testValidFiles(self):
        f1 = self.path.child('file1')
        self.failUnlessEqual(f1.open().read(), self.f1content)
        f2 = self.path.child('sub1').child('file2')
        self.failUnlessEqual(f2.open().read(), self.f2content)

    def testPreauthChild(self):
        fp = filepath.FilePath('.')
        fp.preauthChild('foo/bar')
        self.assertRaises(filepath.InsecurePath, fp.child, '/foo')

    def testStatCache(self):
        p = self.path.child('stattest')
        p.touch()
        self.failUnlessEqual(p.getsize(), 0)
        self.failUnlessEqual(abs(p.getmtime() - time.time()) // 20, 0)
        self.failUnlessEqual(abs(p.getctime() - time.time()) // 20, 0)
        self.failUnlessEqual(abs(p.getatime() - time.time()) // 20, 0)
        self.failUnlessEqual(p.exists(), True)
        self.failUnlessEqual(p.exists(), True)
        p.remove()
        # test caching
        self.failUnlessEqual(p.exists(), True)
        p.restat(reraise=False)
        self.failUnlessEqual(p.exists(), False)
        self.failUnlessEqual(p.islink(), False)
        self.failUnlessEqual(p.isdir(), False)
        self.failUnlessEqual(p.isfile(), False)

    def testPersist(self):
        newpath = pickle.loads(pickle.dumps(self.path))
        self.failUnlessEqual(self.path.__class__, newpath.__class__)
        self.failUnlessEqual(self.path.path, newpath.path)

    def testInsecureUNIX(self):
        self.assertRaises(filepath.InsecurePath, self.path.child, "..")
        self.assertRaises(filepath.InsecurePath, self.path.child, "/etc")
        self.assertRaises(filepath.InsecurePath, self.path.child, "../..")

    def testInsecureWin32(self):
        self.assertRaises(filepath.InsecurePath, self.path.child, r"..\..")
        self.assertRaises(filepath.InsecurePath, self.path.child, r"C:randomfile")

    if platform.getType() != 'win32':
        testInsecureWin32.skip = "Consider yourself lucky."
    else:
        testInsecureWin32.todo = "Hrm, broken"

    def testInsecureWin32Whacky(self):
        """Windows has 'special' filenames like NUL and CON and COM1 and LPR
        and PRN and ... god knows what else.  They can be located anywhere in
        the filesystem.  For obvious reasons, we do not wish to normally permit
        access to these.
        """
        self.assertRaises(filepath.InsecurePath, self.path.child, "CON")
        self.assertRaises(filepath.InsecurePath, self.path.child, "C:CON")
        self.assertRaises(filepath.InsecurePath, self.path.child, r"C:\CON")

    if platform.getType() != 'win32':
        testInsecureWin32Whacky.skip = "Consider yourself lucky."
    else:
        testInsecureWin32Whacky.todo = "Broken, no checking for whacky devices"


from twisted.python import urlpath


class URLPathTestCase(unittest.TestCase):
    def setUp(self):
        self.path = urlpath.URLPath.fromString("http://example.com/foo/bar?yes=no&no=yes#footer")

    def testStringConversion(self):
        self.assertEquals(str(self.path), "http://example.com/foo/bar?yes=no&no=yes#footer")

    def testChildString(self):
        self.assertEquals(str(self.path.child('hello')), "http://example.com/foo/bar/hello")
        self.assertEquals(str(self.path.child('hello').child('')), "http://example.com/foo/bar/hello/")

    def testSiblingString(self):
        self.assertEquals(str(self.path.sibling('baz')), 'http://example.com/foo/baz')
        
        # The sibling of http://example.com/foo/bar/
        #     is http://example.comf/foo/bar/baz
        # because really we are constructing a sibling of
        # http://example.com/foo/bar/index.html
        self.assertEquals(str(self.path.child('').sibling('baz')), 'http://example.com/foo/bar/baz')

    def testParentString(self):
        # parent should be equivalent to '..'
        # 'foo' is the current directory, '/' is the parent directory
        self.assertEquals(str(self.path.parent()), 'http://example.com/')
        self.assertEquals(str(self.path.child('').parent()), 'http://example.com/foo/')
        self.assertEquals(str(self.path.child('baz').parent()), 'http://example.com/foo/')
        self.assertEquals(str(self.path.parent().parent().parent().parent().parent()), 'http://example.com/')

    def testHereString(self):
        # here should be equivalent to '.'
        self.assertEquals(str(self.path.here()), 'http://example.com/foo/')
        self.assertEquals(str(self.path.child('').here()), 'http://example.com/foo/bar/')

