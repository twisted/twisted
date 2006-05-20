# Copyright (c) 2001-2006 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.trial import unittest

from twisted.vfs.backends import inmem
from twisted.vfs import ivfs, pathutils


class InmemTestCase(unittest.TestCase):

    def test_renameFailure(self):
        # Make some VFS sample data
        root = inmem.FakeDirectory()
        filesystem = pathutils.FileSystem(root)
        fakedir = inmem.FakeDirectory('fakedir', root)
        f = inmem.FakeFile('file.txt', root, 'wobble\n')
        root._children = {'fakedir': fakedir, 'file.txt': f}

        # Trying to rename a file over a directory fails
        self.assertRaises(ivfs.VFSError, f.rename, 'fakedir')

        # The original file should still exist.
        self.failUnless(root.child('file.txt') is f)
