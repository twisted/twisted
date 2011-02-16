# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.vfs.backends}.
"""

import os

from twisted.trial import unittest

from twisted.vfs.backends import osfs, inmem
from twisted.python.filepath import FilePath


class OSVFSTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = self.mktemp()
        os.mkdir(self.tmpdir)
        os.mkdir(os.path.join(self.tmpdir, 'ned'))
        FilePath(self.tmpdir).child('file.txt').setContent('wobble\n')
        self.root = osfs.OSDirectory(self.tmpdir)

    def test_listdir(self):
        nodes = self.root.children()
        paths = [path for (path, node) in nodes]
        paths.sort()
        self.assertEquals(paths, ['.', '..', 'file.txt', 'ned'])

    def test_mkdir(self):
        new = self.root.createDirectory('fred')
        nodes = new.children()
        self.assertEquals([path for (path, node) in nodes], ['.', '..'])

    def test_rmdir(self):
        self.root.child('ned').remove()
        nodes = self.root.children()
        paths = [path for (path, node) in nodes]
        paths.sort()
        self.assertEquals(paths, ['.', '..', 'file.txt'])

    def test_rmfile(self):
        self.root.child('file.txt').remove()
        nodes = self.root.children()
        paths = [path for (path, node) in nodes]
        paths.sort()
        self.assertEquals(paths, ['.', '..', 'ned'])

    def test_rename(self):
        self.root.child('ned').rename('sed')
        nodes = self.root.children()
        paths = [path for (path, node) in nodes]
        paths.sort()
        self.assertEquals(paths, ['.', '..', 'file.txt', 'sed'])

    def test_mkfile(self):
        new = self.root.createFile('fred.txt')
        nodes = self.root.children()
        paths = [path for (path, node) in nodes]
        paths.sort()
        self.assertEquals(paths, ['.', '..', 'file.txt', 'fred.txt', 'ned'])

    def test_writefile(self):
        new = self.root.createFile('fred.txt')
        new.open(os.O_WRONLY)
        new.writeChunk(0, 'roar')
        new.close()
        new.open(os.O_RDONLY)
        text = new.readChunk(0, 100)
        new.close()
        self.assertEquals(text, 'roar')

    def test_readfile(self):
        fh = self.root.child('file.txt')
        fh.open(os.O_RDONLY)
        text = fh.readChunk(0, 100)
        fh.close()
        self.assertEquals(text, 'wobble\n')

    def test_exists(self):
        self.failUnless(self.root.exists('file.txt'))
        self.failIf(self.root.exists('noodle'))



class InMemVFSTest(OSVFSTest):

    def setUp(self):
        root = inmem.FakeDirectory()
        ned = inmem.FakeDirectory('ned', root)
        f = inmem.FakeFile('file.txt', root, 'wobble\n')
        root._children = { 'ned' : ned, 'file.txt' : f }
        self.root = root
