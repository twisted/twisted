# Copyright (c) 2001-2005 Twisted Matrix Laboratories.
# See LICENSE for details.

import os
import os.path
import shutil

from twisted.trial import unittest

from twisted.vfs.backends import osfs, inmem
from twisted.vfs.ivfs import IFileSystemContainer, IFileSystemLeaf, VFSError
from twisted.vfs import pathutils


class OSVFSTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = self.mktemp()
        os.mkdir(self.tmpdir)
        os.mkdir(os.path.join(self.tmpdir, 'somedir'))

    def tearDown(self):
        shutil.rmtree( self.tmpdir )

    def test_subclassing(self):
        # The children of a subclassed OSDirectory will also be instances of
        # the subclass (unless childDirFactory is explicitly overridden).
        
        # Define a subclass of OSDirectory
        class OSDirSubclass(osfs.OSDirectory):
            pass

        # Subdirectories, both existing and newly created, will be instances of
        # the subclass.
        osdir = OSDirSubclass(self.tmpdir)
        self.assert_(isinstance(osdir.child('somedir'), OSDirSubclass))
        self.assert_(isinstance(osdir.createDirectory('new'), OSDirSubclass))

    def test_childDirFactory(self):
        # The class of subdirectories can be overridden using childDirFactory
        
        # Define a subclass of OSDirectory that overrides childDirFactory
        class OSDirSubclass(osfs.OSDirectory):
            def childDirFactory(self):
                return osfs.OSDirectory

        # Subdirectories, both existing and newly created, will be instances of
        # osfs.OSDirectory, but not OSDirSubclass.
        osdir = OSDirSubclass(self.tmpdir)
        self.assert_(isinstance(osdir.child('somedir'), osfs.OSDirectory))
        self.assertNot(isinstance(osdir.child('somedir'), OSDirSubclass))
        self.assert_(isinstance(osdir.createDirectory('new'), osfs.OSDirectory))
        self.assertNot(isinstance(osdir.createDirectory('new2'), OSDirSubclass))
        
    def test_createFileExclusive(self):
        osdir = osfs.OSDirectory(self.tmpdir)

        # Creating a new file with exclusivity should pass
        child = osdir.createFile('foo', exclusive=True)
        self.failUnless(IFileSystemLeaf.providedBy(child))
        self.assertIn('foo', [name for name, child in osdir.children()])

        # Creating an existing file with exclusivity should fail.
        self.assertRaises(VFSError, osdir.createFile, 'foo', exclusive=True)

        # Creating an existing file unexclusively should pass.
        child = osdir.createFile('foo', exclusive=False)
        self.failUnless(IFileSystemLeaf.providedBy(child))
        self.assertIn('foo', [name for name, child in osdir.children()])

