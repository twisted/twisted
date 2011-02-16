# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{inmem} vfs backend.
"""

import os

from twisted.trial import unittest

from twisted.vfs.backends import inmem
from twisted.vfs import ivfs



class InmemTestCase(unittest.TestCase):
    """
    Test operations on L{inmem.FakeDirectory} and L{inmem.FakeFile}.
    """

    def test_renameFailure(self):
        """
        Renaming a file into an existing directory should fail.
        """
        # Make some VFS sample data
        root = inmem.FakeDirectory()
        fakedir = inmem.FakeDirectory('fakedir', root)
        f = inmem.FakeFile('file.txt', root, 'wobble\n')
        root._children = {'fakedir': fakedir, 'file.txt': f}

        # Trying to rename a file over a directory fails
        self.assertRaises(ivfs.VFSError, f.rename, 'fakedir')

        # The original file should still exist.
        self.failUnless(root.child('file.txt') is f)


    def test_nonExclusive(self):
        """
        Opening a file in non-exclusive mode should result in the same file.
        """
        root = inmem.FakeDirectory()
        testFile1 = root.createFile("foo")
        testFile2 = root.createFile("foo")
        self.assertIdentical(testFile1, testFile2)


    def test_truncate(self):
        """
        Opening an inmem file with C{os.O_TRUNC} flag should reset its content.
        """
        root = inmem.FakeDirectory()
        testFile = root.createFile("foo")
        testFile.open(0)
        testFile.writeChunk(0, "bar")
        self.assertEquals(testFile.readChunk(0, 3), "bar")
        testFile.open(os.O_TRUNC)
        self.assertEquals(testFile.readChunk(0, 3), "")


    def test_createFileExclusive(self):
        """
        If the C{createFile} method is called with the keyword C{exclusive}
        and that the file already exists, it should fail with a
        L{ivfs.AlreadyExistsError} exception.
        """
        root = inmem.FakeDirectory()
        testFile = root.createFile("foo")
        self.assertRaises(ivfs.AlreadyExistsError,
            root.createFile, "foo", exclusive=True)


    def test_createFileOverDirectory(self):
        """
        Creating a file with the name of an existing directory should fail
        with an C{IOError}.
        """
        root = inmem.FakeDirectory()
        testDir = root.createDirectory("bar")
        self.assertRaises(IOError, root.createFile, "bar")


