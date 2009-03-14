
"""
This module contains tests for L{twisted.python.memfs}.

Since the filesystem in L{twisted.python.memfs} is designed to replicate the
behavior of the 'real' filesystem, many of these tests are written in a style
where they verify the same behavior on both interfaces, and run against both
interfaces, to make it easy to verify that the in-memory implementation is
behaving the same as the real implementation.
"""

import sys
import os
from errno import ENOSPC

from twisted.trial.unittest import TestCase

from twisted.python.memfs import SEEK_SET, SEEK_CUR, SEEK_END, POSIXFilesystem

from twisted.python.test import iostub, blankmodule

from twisted.python import realfs



class FileTestsMixin:
    """
    Tests for an object like L{file}.

    @ivar filesystem: A provider of L{IFileSystem}.  This should be set in the
        C{setUp} of subclasses.
    """

    filesystem = None


    def test_fileno(self):
        """
        C{fileno} returns an integer value unique among open files.
        """
        first = self.filesystem.open("foo", "w")
        self.addCleanup(first.close)

        self.assertTrue(isinstance(first.fileno(), int))
        second = self.filesystem.open("bar", "w")
        self.addCleanup(second.close)

        self.assertTrue(isinstance(first.fileno(), int))
        self.assertNotEqual(first.fileno(), second.fileno())


    def test_closed(self):
        """
        C{fileno}, C{write}, C{read}, C{tell}, and C{flush} raise L{ValueError}
        when called on a closed file.  C{fsync} raises L{OSerror}.  C{close}
        does nothing.
        """
        fObj = self.filesystem.open("foo", "w")
        fd = fObj.fileno()
        fObj.close()
        self.assertRaises(ValueError, fObj.fileno)
        self.assertRaises(ValueError, fObj.write, '')
        self.assertRaises(ValueError, fObj.read)
        self.assertRaises(ValueError, fObj.flush)
        self.assertRaises(ValueError, fObj.tell)
        self.assertRaises(OSError, self.filesystem.fsync, fd)
        fObj.close()


    def test_closedFlag(self):
        """
        The L{closed} attribute on an open file is L{False}; on a closed file
        it is L{True}.
        """
        fObj = self.filesystem.open("foo", "w")
        self.assertEqual(fObj.closed, False)
        fObj.close()
        self.assertEqual(fObj.closed, True)


    def test_write(self):
        """
        C{write} adds bytes to a file.
        """
        outfile = self.filesystem.open("foo", "w")
        self.addCleanup(outfile.close)

        infile = self.filesystem.open("foo", "r")
        self.addCleanup(infile.close)

        # A boring write at the beginning of the file puts the bytes at the
        # beginning of the file.
        outfile.write("hello")
        outfile.flush()
        self.assertEqual(infile.read(), "hello")

        # A write somewhere in the middle of the file overwrites some of the
        # file.
        outfile.seek(3)
        outfile.write("world")
        outfile.flush()
        infile.seek(0)
        self.assertEqual(infile.read(), "helworld")

        # A write exactly at the end of the file appends the given bytes to the
        # file.
        outfile.seek(8)
        outfile.write(".")
        outfile.flush()
        infile.seek(0)
        self.assertEqual(infile.read(), "helworld.")

        # A write past the end of the file inserts 0s to fill the gap and
        # appends the given bytes.
        outfile.seek(11)
        outfile.write("zoop")
        outfile.flush()
        infile.seek(0)
        self.assertEqual(infile.read(), "helworld.\0\0zoop")


    def test_writeSeekRead(self):
        """
        If you write some bytes, then seek back to their beginning, then read
        them, you will get them back.
        """
        outfile = self.filesystem.open("out", "w+")
        outfile.write("foobar")
        outfile.seek(3)
        self.assertEqual(outfile.read(), "bar")


    def test_read(self):
        """
        C{read} with no arguments returns the entire current contents of a
        file.
        """
        bytes = "bytes"
        outfile = self.filesystem.open("out", "w")
        outfile.write(bytes)
        outfile.close()

        infile = self.filesystem.open("out", "r")
        self.addCleanup(infile.close)

        self.assertEqual(infile.read(), bytes)

        infile.seek(1)
        self.assertEqual(infile.read(), bytes[1:])

        infile.seek(1)
        self.assertEqual(infile.read(1), bytes[1])

        infile.seek(1)
        self.assertEqual(infile.read(-3), bytes[1:])

        infile.seek(1)
        self.assertEqual(infile.read(0), '')


    def test_consecutiveReads(self):
        """
        Consecutive limited-length reads from a file should result in portions
        of its contents being returned, and advance the file position.
        """
        f = self.filesystem.open("out", "w")
        f.write("abcdefg")
        f.close()
        f2 = self.filesystem.open("out", "r")
        self.assertEqual(f2.read(2), "ab")
        self.assertEqual(f2.tell(), 2)
        self.assertEqual(f2.read(2), "cd")
        self.assertEqual(f2.tell(), 4)
        self.assertEqual(f2.read(2), "ef")
        self.assertEqual(f2.tell(), 6)
        self.assertEqual(f2.read(2), "g")
        self.assertEqual(f2.tell(), 7)
        self.assertEqual(f2.read(2), "")


    def test_flush(self):
        """
        Data written to a file before a call to C{flush} is visible to another
        file object which refers to the same file.
        """
        bytes = "bytes"
        outfile = self.filesystem.open("out", "w")
        self.addCleanup(outfile.close)

        outfile.write(bytes)
        outfile.flush()
        infile = self.filesystem.open("out", "r")
        self.addCleanup(infile.close)
        self.assertEqual(bytes, infile.read())


    def test_tell(self):
        """
        The C{tell} method returns the current file position.
        """
        fObj = self.filesystem.open("foo", "w")
        fObj.write("hello")
        self.assertEqual(fObj.tell(), 5)
        fObj.write("world")
        self.assertEqual(fObj.tell(), 10)


    def test_seek(self):
        """
        The C{seek} method changes the current file position to the specified
        value.
        """
        fObj = self.filesystem.open("foo", "w")
        fObj.write("hello")
        fObj.seek(1)
        self.assertEqual(fObj.tell(), 1)
        fObj.seek(2)
        self.assertEqual(fObj.tell(), 2)
        fObj.seek(3, SEEK_SET)
        self.assertEqual(fObj.tell(), 3)
        fObj.seek(1, SEEK_CUR)
        self.assertEqual(fObj.tell(), 4)
        fObj.seek(1, SEEK_END)
        self.assertEqual(fObj.tell(), 6)


    def test_seekFlushes(self):
        """
        Using the C{seek} method also flushes the contents of the application
        buffer.
        """
        writer = self.filesystem.open("foo", "w")
        self.addCleanup(writer.close)

        reader = self.filesystem.open("foo", "r")
        self.addCleanup(reader.close)

        writer.write("foo")

        # Sanity check
        self.assertEqual(reader.read(), "")

        # Seek, causing a flush, causing the bytes to be visible elsewhere.
        writer.seek(0)
        self.assertEqual(reader.read(), "foo")


    def test_writeOpenTruncates(self, addMode=''):
        """
        If a file already exists with a given name, C{open} in 'w' mode
        immediately truncates that file.
        """
        writer = self.filesystem.open("foo", "w")
        writer.write("some data that you don't want")
        writer.flush()
        self.filesystem.fsync(writer.fileno())
        writer2 = self.filesystem.open("foo", "w"+addMode)
        writer2.write("information")
        writer2.close()
        reader = self.filesystem.open("foo", "r")
        self.assertEqual(reader.read(), "information")


    def test_writePlusOpenTruncates(self):
        """
        If a file already exists with a given name, C{open} in 'w+' mode
        immediately truncates that file.
        """
        self.test_writeOpenTruncates("+")


    def test_appendOpenDoesntTruncate(self):
        """
        If a file already exists with a given name, C{open} in 'w' mode
        immediately truncates that file.
        """
        writer = self.filesystem.open("foo", "w")
        writer.write("alpha")
        writer.flush()
        self.filesystem.fsync(writer.fileno())
        writer2 = self.filesystem.open("foo", "a")
        writer2.write(" beta gamma")
        writer2.close()
        reader = self.filesystem.open("foo", "r")
        self.assertEqual(reader.read(), "alpha beta gamma")


    def test_rename(self):
        """
        The C{rename} method changes the name by which a file is accessible.
        """
        fObj = self.filesystem.open("foo", "w")
        fObj.write("bytes")
        fObj.close()
        self.filesystem.rename("foo", "bar")
        fObj = self.filesystem.open("bar", "r")
        self.addCleanup(fObj.close)
        self.assertEqual(fObj.read(), "bytes")



class RealFileTests(TestCase, FileTestsMixin):
    """
    This implements FileTestsMixin to test Python's built-in implementation of
    the 'file' type, so that we can verify the behavior of alternate
    implementations is similar.
    """

    def setUp(self):
        """
        Create a temporary directory to house this test's files.
        """
        self.base = self.mktemp()
        os.makedirs(self.base)
        self.originalWorkingDirectory = os.getcwd()
        os.chdir(self.base)
        self.filesystem = realfs


    def tearDown(self):
        """
        Restore the directory.
        """
        os.chdir(self.originalWorkingDirectory)


    def test_seekFlushes(self):
        """
        Override to set custom attributes.
        """
        # See below.
        FileTestsMixin.test_seekFlushes(self)


    if sys.platform == 'darwin':
        test_seekFlushes.todo = (
            "OS X appears to violate POSIX: seek() does not imply flush()")



class MemoryFilesystemTests(TestCase, FileTestsMixin):
    """
    Test L{POSIXFilesystem} with the tests defined in L{FileTestsMixin}, to
    make sure that it provides parity with Python's built-in filesystem
    operations.
    """

    def setUp(self):
        """
        Set up a L{POSIXFilesystem} to test.
        """
        self.filesystem = POSIXFilesystem()


    def test_writeConsistency(self):
        """
        L{POSIXFilesystem.bytesOnDeviceFor} will return the bytes that have
        been written and synced to disk for a given filename.
        """
        name = "test.txt"
        f = self.filesystem.open(name, "w")
        f.write("some data")
        self.assertEqual(self.filesystem.bytesOnDeviceFor(name), "")
        f.flush()
        self.assertEqual(self.filesystem.bytesOnDeviceFor(name), "")
        self.filesystem.fsync(f.fileno())
        self.assertEqual(self.filesystem.bytesOnDeviceFor(name), "some data")
        f.close()
        self.assertEqual(self.filesystem.bytesOnDeviceFor(name), "some data")


    def test_closeStillInconsistent(self):
        """
        Since C{close} does not imply C{fsync}, closing a file without syncing
        will cause L{POSIXFilesystem.bytesOnDeviceFor} to return the empty
        string.
        """
        f = self.filesystem.open("test.txt", "w")
        f.write("some data")
        f.close()
        self.assertEqual(self.filesystem.bytesOnDeviceFor("test.txt"), "")


    def test_fullFilesystem(self):
        """
        A full filesystem rejects actual writes (i.e. flush() calls) with
        ENOSPC.  A filesystem 'full' in this manner will still allow creation
        of new files.

        Setting the C{full} attribute to C{True} on L{POSIXFilesystem} will
        cause it to behave as if it is full.

        I can't think of an automated to verify that this actually happens on
        the real filesystem implementation, but you can verify this for
        yourself on linux with::

            sudo mke2fs -m 0 /dev/ram0
            mkdir ramdisk
            sudo mount /dev/ram0 ramdisk
            cd ramdisk
            sudo chown $(id -u).$(id -g) .
            dd if=/dev/zero of=fillme
            python
            >>> f = file("full.txt", "w")
            >>> f.write("data")
            >>> f.flush()

        or, alternately, C{f.close()}.

        Doing a C{flush()} while the filesystem is full will empty the stream
        buffer while it raises this exception, so
        """
        self.filesystem.full = True
        f = self.filesystem.open("test.txt", "w+")
        f.write("some data")
        ioe = self.assertRaises(IOError, f.flush)
        self.assertEqual(ioe.errno, ENOSPC)
        self.assertEqual(ioe.strerror, os.strerror(ENOSPC))
        f.close()
        f = self.filesystem.open("test.txt", "r")
        self.assertEqual(f.read(), "")



iostubOriginalNamespace = iostub.__dict__.copy()

class PatchingTest(TestCase):
    """
    These tests cover various cases for L{POSIXFilesystem.redirect} to alter
    the behavior of a module.
    """

    def setUp(self):
        """
        Create a L{POSIXFilesystem} for testing.
        """
        self.filename = self.mktemp()
        self.filesystem = POSIXFilesystem()
        self.unpatcher = None


    def patchIt(self):
        """
        Patch the 'iostub' module.
        """
        self.unpatcher = self.filesystem.redirect(iostub)


    def unpatchIt(self):
        """
        Unpatch the 'iostub' module if it is currently patched.
        """
        if self.unpatcher is not None:
            unpatcher = self.unpatcher
            self.unpatcher = None
            unpatcher()


    def tearDown(self):
        """
        Unpatch the 'iostub' module.
        """
        self.unpatchIt()


    def test_simpleWrite(self):
        """
        A function defined in a module which simply uses the 'open' built-in
        will write to a file in my L{POSIXFilesystem}, not the real filesystem.
        """
        self.patchIt()
        for thunk, data in ((iostub.writeWithOpen, "foo"),
                            (iostub.writeWithFile, "bar")):
            thunk(self.filename, data)
            self.assertEqual(self.filesystem.open(self.filename).read(), data)
            self.assertRaises(IOError, open, self.filename)


    def test_unpatching(self):
        """
        When the callable returned from L{POSIXFilesystem.redirect} is invoked,
        all patches should be removed from the target module.
        """
        # Make sure we start the test in an unmolested state (since other test
        # methods do patching).
        self.assertClean()
        self.patchIt()
        self.unpatchIt()
        self.assertClean()


    def test_unpatchingEmpty(self):
        """
        Unpatching a module which is empty should leave the module in a
        pristine state; new names should not be added by the patch/unpatch
        process.
        """
        origNamespace = blankmodule.__dict__.copy()
        self.filesystem.redirect(blankmodule)()
        self.assertEqualNamespace(origNamespace, blankmodule.__dict__)


    def assertEqualNamespace(self, a, b):
        """
        a (a module global namespace) should equal b (another global
        namespace).  Assert that and produce a helpful message if not.
        """
        messages = []
        allkeys = set(a.keys()).union(set(b.keys()))
        for k in allkeys:
            if k == '__warningregistry__':
                continue
            if k not in a:
                messages.append("%r added" % (k,))
            elif k not in b:
                messages.append("%r removed" % (k,))
            elif a[k] != b[k]:
                messages.append("%r changed" % (k,))
        if messages:
            self.fail(', '.join(messages))


    def assertClean(self):
        """
        Make sure that the 'iostub' module is in a pristine state.
        """
        self.assertEqualNamespace(iostubOriginalNamespace, iostub.__dict__)


    def test_rename(self):
        """
        'os.rename' should rename a file in the redirected filesystem.
        """
        self.patchIt()
        for renamer, uniquename in ([
                (iostub.rename_moduleImport, "foo"),
                (iostub.rename_functionImport, "bar")]):
            self.filesystem.open(uniquename, "w").close()
            newname = uniquename+".new"
            renamer(uniquename, newname)
            self.assertEqual(self.filesystem.exists(uniquename), False)
            self.assertEqual(self.filesystem.exists(newname), True)


    def test_fsync(self):
        """
        'os.fsync' should sync the buffers in the redirected filesystem.
        """
        self.patchIt()
        for syncer, somedata in ([
                (iostub.fsync_moduleImport, "some data"),
                (iostub.fsync_functionImport, "some other data")]):
            syncer(self.filename, somedata)
            self.assertEqual(self.filesystem.bytesOnDeviceFor(self.filename),
                             somedata)


    def test_otherAttributes(self):
        """
        Other attributes of the 'os' module should remain unchanged.
        """
        self.patchIt()
        self.assertEqual(iostub.os.name, os.name)
