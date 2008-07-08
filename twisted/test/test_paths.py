# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases covering L{twisted.python.filepath} and L{twisted.python.zippath}.
"""

import os, time, pickle, errno, zipfile, stat

from twisted.python.compat import set
from twisted.python.win32 import WindowsError, ERROR_DIRECTORY
from twisted.python import filepath
from twisted.python.zippath import ZipArchive
from twisted.python.runtime import platform

from twisted.trial import unittest


class AbstractFilePathTestCase(unittest.TestCase):

    f1content = "file 1"
    f2content = "file 2"

    def _mkpath(self, *p):
        x = os.path.abspath(os.path.join(self.cmn, *p))
        self.all.append(x)
        return x


    def subdir(self, *dirname):
        os.mkdir(self._mkpath(*dirname))


    def subfile(self, *dirname):
        return open(self._mkpath(*dirname), "wb")


    def setUp(self):
        self.now = time.time()
        cmn = self.cmn = os.path.abspath(self.mktemp())
        self.all = [cmn]
        os.mkdir(cmn)
        self.subdir("sub1")
        f = self.subfile("file1")
        f.write(self.f1content)
        f.close()
        f = self.subfile("sub1", "file2")
        f.write(self.f2content)
        f.close()
        self.subdir('sub3')
        f = self.subfile("sub3", "file3.ext1")
        f.close()
        f = self.subfile("sub3", "file3.ext2")
        f.close()
        f = self.subfile("sub3", "file3.ext3")
        f.close()
        self.path = filepath.FilePath(cmn)


    def test_segmentsFromPositive(self):
        """
        Verify that the segments between two paths are correctly identified.
        """
        self.assertEquals(
            self.path.child("a").child("b").child("c").segmentsFrom(self.path),
            ["a", "b", "c"])

    def test_segmentsFromNegative(self):
        """Verify that segmentsFrom notices when the ancestor isn't an ancestor.
        """
        self.assertRaises(
            ValueError,
            self.path.child("a").child("b").child("c").segmentsFrom,
                self.path.child("d").child("c").child("e"))


    def test_walk(self):
        """
        Verify that walking the path gives the same result as the known file
        hierarchy.
        """
        x = [foo.path for foo in self.path.walk()]
        self.assertEquals(set(x), set(self.all))


    def test_validSubdir(self):
        """Verify that a valid subdirectory will show up as a directory, but not as a
        file, not as a symlink, and be listable.
        """
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


    def test_invalidSubdir(self):
        """
        Verify that a subdirectory that doesn't exist is reported as such.
        """
        sub2 = self.path.child('sub2')
        self.failIf(sub2.exists(),
                    "This directory does not exist.")

    def test_validFiles(self):
        """
        Make sure that we can read existent non-empty files.
        """
        f1 = self.path.child('file1')
        self.failUnlessEqual(f1.open().read(), self.f1content)
        f2 = self.path.child('sub1').child('file2')
        self.failUnlessEqual(f2.open().read(), self.f2content)


    def test_dictionaryKeys(self):
        """
        Verify that path instances are usable as dictionary keys.
        """
        f1 = self.path.child('file1')
        f1prime = self.path.child('file1')
        f2 = self.path.child('file2')
        dictoid = {}
        dictoid[f1] = 3
        dictoid[f1prime] = 4
        self.assertEquals(dictoid[f1], 4)
        self.assertEquals(dictoid.keys(), [f1])
        self.assertIdentical(dictoid.keys()[0], f1)
        self.assertNotIdentical(dictoid.keys()[0], f1prime) # sanity check
        dictoid[f2] = 5
        self.assertEquals(dictoid[f2], 5)
        self.assertEquals(len(dictoid), 2)


    def test_dictionaryKeyWithString(self):
        """
        Verify that path instances are usable as dictionary keys which do not clash
        with their string counterparts.
        """
        f1 = self.path.child('file1')
        dictoid = {f1: 'hello'}
        dictoid[f1.path] = 'goodbye'
        self.assertEquals(len(dictoid), 2)


    def test_childrenNonexistentError(self):
        """
        Verify that children raises the appropriate exception for non-existent
        directories.
        """
        self.assertRaises(filepath.UnlistableError,
                          self.path.child('not real').children)

    def test_childrenNotDirectoryError(self):
        """
        Verify that listdir raises the appropriate exception for attempting to list
        a file rather than a directory.
        """
        self.assertRaises(filepath.UnlistableError,
                          self.path.child('file1').children)


    def test_newTimesAreFloats(self):
        """
        Verify that all times returned from the various new time functions are ints
        (and hopefully therefore 'high precision').
        """
        for p in self.path, self.path.child('file1'):
            self.failUnlessEqual(type(p.getAccessTime()), float)
            self.failUnlessEqual(type(p.getModificationTime()), float)
            self.failUnlessEqual(type(p.getStatusChangeTime()), float)


    def test_oldTimesAreInts(self):
        """
        Verify that all times returned from the various time functions are
        integers, for compatibility.
        """
        for p in self.path, self.path.child('file1'):
            self.failUnlessEqual(type(p.getatime()), int)
            self.failUnlessEqual(type(p.getmtime()), int)
            self.failUnlessEqual(type(p.getctime()), int)



class FakeWindowsPath(filepath.FilePath):
    """
    A test version of FilePath which overrides listdir to raise L{WindowsError}.
    """

    def listdir(self):
        """
        @raise WindowsError: always.
        """
        raise WindowsError(
            ERROR_DIRECTORY,
            "A directory's validness was called into question")


class ListingCompatibilityTests(unittest.TestCase):
    """
    These tests verify compatibility with legacy behavior of directory listing.
    """

    def test_windowsErrorExcept(self):
        """
        Verify that when a WindowsError is raised from listdir, catching
        WindowsError works.
        """
        fwp = FakeWindowsPath(self.mktemp())
        self.assertRaises(filepath.UnlistableError, fwp.children)
        self.assertRaises(WindowsError, fwp.children)


    def test_alwaysCatchOSError(self):
        """
        Verify that in the normal case where a directory does not exist, we will
        get an OSError.
        """
        fp = filepath.FilePath(self.mktemp())
        self.assertRaises(OSError, fp.children)


    def test_keepOriginalAttributes(self):
        """
        Verify that the Unlistable exception raised will preserve the attributes of
        the previously-raised exception.
        """
        fp = filepath.FilePath(self.mktemp())
        ose = self.assertRaises(OSError, fp.children)
        d1 = ose.__dict__.keys()
        d1.remove('originalException')
        d2 = ose.originalException.__dict__.keys()
        d1.sort()
        d2.sort()
        self.assertEquals(d1, d2)



def zipit(dirname, zfname):
    """
    create a zipfile on zfname, containing the contents of dirname'
    """
    zf = zipfile.ZipFile(zfname, "w")
    basedir = os.path.basename(dirname)
    for root, dirs, files, in os.walk(dirname):
        for fname in files:
            fspath = os.path.join(root, fname)
            arcpath = os.path.join(root, fname)[len(dirname)+1:]
            # print fspath, '=>', arcpath
            zf.write(fspath, arcpath)
    zf.close()

class ZipFilePathTestCase(AbstractFilePathTestCase):

    def setUp(self):
        AbstractFilePathTestCase.setUp(self)
        zipit(self.cmn, self.cmn+'.zip')
        self.path = ZipArchive(self.cmn+'.zip')
        self.all = [x.replace(self.cmn, self.cmn+'.zip') for x in self.all]


class FilePathTestCase(AbstractFilePathTestCase):

    def test_chmod(self):
        """
        Make sure that calling L{FilePath.chmod} modifies the permissions of
        the passed file as expected (using C{os.stat} to check). We use some
        basic modes that should work everywhere (even on Windows).
        """
        for mode in (0555, 0777):
            self.path.child("sub1").chmod(mode)
            self.assertEquals(
                stat.S_IMODE(os.stat(self.path.child("sub1").path).st_mode),
                mode)


    def symlink(self, target, name):
        """
        Create a symbolic link named C{name} pointing at C{target}.

        @type target: C{str}
        @type name: C{str}
        @raise SkipTest: raised if symbolic links are not supported on the
            host platform.
        """
        if getattr(os, 'symlink', None) is None:
            raise unittest.SkipTest(
                "Platform does not support symbolic links.")
        os.symlink(target, name)


    def createLinks(self):
        """
        Create several symbolic links to files and directories.
        """
        subdir = self.path.child("sub1")
        self.symlink(subdir.path, self._mkpath("sub1.link"))
        self.symlink(subdir.child("file2").path, self._mkpath("file2.link"))
        self.symlink(subdir.child("file2").path,
                     self._mkpath("sub1", "sub1.file2.link"))


    def test_realpathSymlink(self):
        """
        L{FilePath.realpath} returns the path of the ultimate target of a
        symlink.
        """
        self.createLinks()
        self.symlink(self.path.child("file2.link").path,
                     self.path.child("link.link").path)
        self.assertEquals(self.path.child("link.link").realpath(),
                          self.path.child("sub1").child("file2"))


    def test_realpathCyclicalSymlink(self):
        """
        L{FilePath.realpath} raises L{filepath.LinkError} if the path is a
        symbolic link which is part of a cycle.
        """
        self.symlink(self.path.child("link1").path, self.path.child("link2").path)
        self.symlink(self.path.child("link2").path, self.path.child("link1").path)
        self.assertRaises(filepath.LinkError,
                          self.path.child("link2").realpath)


    def test_realpathNoSymlink(self):
        """
        L{FilePath.realpath} returns the path itself if the path is not a
        symbolic link.
        """
        self.assertEquals(self.path.child("sub1").realpath(),
                          self.path.child("sub1"))


    def test_walkCyclicalSymlink(self):
        """
        Verify that walking a path with a cyclical symlink raises an error
        """
        self.createLinks()
        self.symlink(self.path.child("sub1").path,
                     self.path.child("sub1").child("sub1.loopylink").path)
        def iterateOverPath():
            return [foo.path for foo in self.path.walk()]
        self.assertRaises(filepath.LinkError, iterateOverPath)


    def test_walkObeysDescend(self):
        """
        Verify that when the supplied C{descend} predicate returns C{False},
        the target is not traversed.
        """
        self.createLinks()
        def noSymLinks(path):
            return not path.islink()
        x = [foo.path for foo in self.path.walk(descend=noSymLinks)]
        self.assertEquals(set(x), set(self.all))


    def test_getAndSet(self):
        content = 'newcontent'
        self.path.child('new').setContent(content)
        newcontent = self.path.child('new').getContent()
        self.failUnlessEqual(content, newcontent)
        content = 'content'
        self.path.child('new').setContent(content, '.tmp')
        newcontent = self.path.child('new').getContent()
        self.failUnlessEqual(content, newcontent)


    def test_symbolicLink(self):
        """
        Verify the behavior of the C{isLink} method against links and
        non-links. Also check that the symbolic link shares the directory
        property with its target.
        """
        s4 = self.path.child("sub4")
        s3 = self.path.child("sub3")
        self.symlink(s3.path, s4.path)
        self.assertTrue(s4.islink())
        self.assertFalse(s3.islink())
        self.assertTrue(s4.isdir())
        self.assertTrue(s3.isdir())


    def test_linkTo(self):
        """
        Verify that symlink creates a valid symlink that is both a link and a
        file if its target is a file, or a directory if its target is a
        directory.
        """
        targetLinks = [
            (self.path.child("sub2"), self.path.child("sub2.link")),
            (self.path.child("sub2").child("file3.ext1"),
             self.path.child("file3.ext1.link"))
            ]
        for target, link in targetLinks:
            target.linkTo(link)
            self.assertTrue(link.islink(), "This is a link")
            self.assertEquals(target.isdir(), link.isdir())
            self.assertEquals(target.isfile(), link.isfile())


    def test_linkToErrors(self):
        """
        Verify C{linkTo} fails in the following case:
            - the target is in a directory that doesn't exist
            - the target already exists
        """
        self.assertRaises(OSError, self.path.child("file1").linkTo,
                          self.path.child('nosub').child('file1'))
        self.assertRaises(OSError, self.path.child("file1").linkTo,
                          self.path.child('sub1').child('file2'))


    if not getattr(os, "symlink", None):
        skipMsg = "Your platform does not support symbolic links."
        test_symbolicLink.skip = skipMsg
        test_linkTo.skip = skipMsg
        test_linkToErrors.skip = skipMsg


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
        # OOB removal: FilePath.remove() will automatically restat
        os.remove(p.path)
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

    def testComparison(self):
        self.assertEquals(filepath.FilePath('a'),
                          filepath.FilePath('a'))
        self.failUnless(filepath.FilePath('z') >
                        filepath.FilePath('a'))
        self.failUnless(filepath.FilePath('z') >=
                        filepath.FilePath('a'))
        self.failUnless(filepath.FilePath('a') >=
                        filepath.FilePath('a'))
        self.failUnless(filepath.FilePath('a') <=
                        filepath.FilePath('a'))
        self.failUnless(filepath.FilePath('a') <
                        filepath.FilePath('z'))
        self.failUnless(filepath.FilePath('a') <=
                        filepath.FilePath('z'))
        self.failUnless(filepath.FilePath('a') !=
                        filepath.FilePath('z'))
        self.failUnless(filepath.FilePath('z') !=
                        filepath.FilePath('a'))

        self.failIf(filepath.FilePath('z') !=
                    filepath.FilePath('z'))

    def testSibling(self):
        p = self.path.child('sibling_start')
        ts = p.sibling('sibling_test')
        self.assertEquals(ts.dirname(), p.dirname())
        self.assertEquals(ts.basename(), 'sibling_test')
        ts.createDirectory()
        self.assertIn(ts, self.path.children())

    def testTemporarySibling(self):
        ts = self.path.temporarySibling()
        self.assertEquals(ts.dirname(), self.path.dirname())
        self.assertNotIn(ts.basename(), self.path.listdir())
        ts.createDirectory()
        self.assertIn(ts, self.path.parent().children())

    def testRemove(self):
        self.path.remove()
        self.failIf(self.path.exists())


    def test_removeWithSymlink(self):
        """
        For a path which is a symbolic link, L{FilePath.remove} just deletes
        the link, not the target.
        """
        link = self.path.child("sub1.link")
        # setUp creates the sub1 child
        self.symlink(self.path.child("sub1").path, link.path)
        link.remove()
        self.assertFalse(link.exists())
        self.assertTrue(self.path.child("sub1").exists())


    def test_copyTo(self):
        self.assertRaises((OSError, IOError), self.path.copyTo, self.path.child('file1'))
        oldPaths = list(self.path.walk()) # Record initial state
        fp = filepath.FilePath(self.mktemp())
        self.path.copyTo(fp)
        self.path.remove()
        fp.copyTo(self.path)
        newPaths = list(self.path.walk()) # Record double-copy state
        newPaths.sort()
        oldPaths.sort()
        self.assertEquals(newPaths, oldPaths)


    def test_copyToWithSymlink(self):
        """
        Verify that copying with followLinks=True copies symlink targets
        instead of symlinks
        """
        self.symlink(self.path.child("sub1").path,
                     self.path.child("link1").path)
        fp = filepath.FilePath(self.mktemp())
        self.path.copyTo(fp)
        self.assertFalse(fp.child("link1").islink())
        self.assertEquals([x.basename() for x in fp.child("sub1").children()],
                          [x.basename() for x in fp.child("link1").children()])


    def test_copyToWithoutSymlink(self):
        """
        Verify that copying with followLinks=False copies symlinks as symlinks
        """
        self.symlink("sub1", self.path.child("link1").path)
        fp = filepath.FilePath(self.mktemp())
        self.path.copyTo(fp, followLinks=False)
        self.assertTrue(fp.child("link1").islink())
        self.assertEquals(os.readlink(self.path.child("link1").path),
                          os.readlink(fp.child("link1").path))


    def test_moveTo(self):
        """
        Verify that moving an entire directory results into another directory
        with the same content.
        """
        oldPaths = list(self.path.walk()) # Record initial state
        fp = filepath.FilePath(self.mktemp())
        self.path.moveTo(fp)
        fp.moveTo(self.path)
        newPaths = list(self.path.walk()) # Record double-move state
        newPaths.sort()
        oldPaths.sort()
        self.assertEquals(newPaths, oldPaths)


    def test_moveToError(self):
        """
        Verify error behavior of moveTo: it should raises one of OSError or
        IOError if you want to move a path into one of its child. It's simply
        the error raised by the underlying rename system call.
        """
        self.assertRaises((OSError, IOError), self.path.moveTo, self.path.child('file1'))


    def setUpFaultyRename(self):
        """
        Set up a C{os.rename} that will fail with L{errno.EXDEV} on first call.
        This is used to simulate a cross-device rename failure.

        @return: a list of pair (src, dest) of calls to C{os.rename}
        @rtype: C{list} of C{tuple}
        """
        invokedWith = []
        def faultyRename(src, dest):
            invokedWith.append((src, dest))
            if len(invokedWith) == 1:
                raise OSError(errno.EXDEV, 'Test-induced failure simulating '
                                           'cross-device rename failure')
            return originalRename(src, dest)

        originalRename = os.rename
        self.patch(os, "rename", faultyRename)
        return invokedWith


    def test_crossMountMoveTo(self):
        """
        C{moveTo} should be able to handle C{EXDEV} error raised by
        C{os.rename} when trying to move a file on a different mounted
        filesystem.
        """
        invokedWith = self.setUpFaultyRename()
        # Bit of a whitebox test - force os.rename, which moveTo tries
        # before falling back to a slower method, to fail, forcing moveTo to
        # use the slower behavior.
        self.test_moveTo()
        # A bit of a sanity check for this whitebox test - if our rename
        # was never invoked, the test has probably fallen into disrepair!
        self.assertTrue(invokedWith)


    def test_crossMountMoveToWithSymlink(self):
        """
        By default, when moving a symlink, it should follow the link and
        actually copy the content of the linked node.
        """
        invokedWith = self.setUpFaultyRename()
        f2 = self.path.child('file2')
        f3 = self.path.child('file3')
        self.symlink(self.path.child('file1').path, f2.path)
        f2.moveTo(f3)
        self.assertFalse(f3.islink())
        self.assertEquals(f3.getContent(), 'file 1')
        self.assertTrue(invokedWith)


    def test_crossMountMoveToWithoutSymlink(self):
        """
        Verify that moveTo called with followLinks=False actually create
        another symlink.
        """
        invokedWith = self.setUpFaultyRename()
        f2 = self.path.child('file2')
        f3 = self.path.child('file3')
        self.symlink(self.path.child('file1').path, f2.path)
        f2.moveTo(f3, followLinks=False)
        self.assertTrue(f3.islink())
        self.assertEquals(f3.getContent(), 'file 1')
        self.assertTrue(invokedWith)


    def testOpen(self):
        # Opening a file for reading when it does not already exist is an error
        nonexistent = self.path.child('nonexistent')
        e = self.assertRaises(IOError, nonexistent.open)
        self.assertEquals(e.errno, errno.ENOENT)

        # Opening a file for writing when it does not exist is okay
        writer = self.path.child('writer')
        f = writer.open('w')
        f.write('abc\ndef')
        f.close()

        # Make sure those bytes ended up there - and test opening a file for
        # reading when it does exist at the same time
        f = writer.open()
        self.assertEquals(f.read(), 'abc\ndef')
        f.close()

        # Re-opening that file in write mode should erase whatever was there.
        f = writer.open('w')
        f.close()
        f = writer.open()
        self.assertEquals(f.read(), '')
        f.close()

        # Put some bytes in a file so we can test that appending does not
        # destroy them.
        appender = self.path.child('appender')
        f = appender.open('w')
        f.write('abc')
        f.close()

        f = appender.open('a')
        f.write('def')
        f.close()

        f = appender.open('r')
        self.assertEquals(f.read(), 'abcdef')
        f.close()

        # read/write should let us do both without erasing those bytes
        f = appender.open('r+')
        self.assertEquals(f.read(), 'abcdef')
        # ANSI C *requires* an fseek or an fgetpos between an fread and an
        # fwrite or an fwrite and a fread.  We can't reliable get Python to
        # invoke fgetpos, so we seek to a 0 byte offset from the current
        # position instead.  Also, Python sucks for making this seek
        # relative to 1 instead of a symbolic constant representing the
        # current file position.
        f.seek(0, 1)
        # Put in some new bytes for us to test for later.
        f.write('ghi')
        f.close()

        # Make sure those new bytes really showed up
        f = appender.open('r')
        self.assertEquals(f.read(), 'abcdefghi')
        f.close()

        # write/read should let us do both, but erase anything that's there
        # already.
        f = appender.open('w+')
        self.assertEquals(f.read(), '')
        f.seek(0, 1) # Don't forget this!
        f.write('123')
        f.close()

        # super append mode should let us read and write and also position the
        # cursor at the end of the file, without erasing everything.
        f = appender.open('a+')

        # The order of these lines may seem surprising, but it is necessary.
        # The cursor is not at the end of the file until after the first write.
        f.write('456')
        f.seek(0, 1) # Asinine.
        self.assertEquals(f.read(), '')

        f.seek(0, 0)
        self.assertEquals(f.read(), '123456')
        f.close()

        # Opening a file exclusively must fail if that file exists already.
        nonexistent.requireCreate(True)
        nonexistent.open('w').close()
        existent = nonexistent
        del nonexistent
        self.assertRaises((OSError, IOError), existent.open)


    def test_existsCache(self):
        """
        Check that C{filepath.FilePath.exists} correctly restat the object if
        an operation has occurred in the mean time.
        """
        fp = filepath.FilePath(self.mktemp())
        self.assertEquals(fp.exists(), False)

        fp.makedirs()
        self.assertEquals(fp.exists(), True)



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

