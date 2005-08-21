
import os
import os.path
import shutil

from twisted.trial import unittest

from twisted.vfs.backends import osfs, inmem
from twisted.vfs.ivfs import IFileSystemContainer, IFileSystemLeaf
from twisted.vfs import pathutils


class OSVFSTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = self.mktemp()
        os.mkdir(self.tmpdir)
        os.mkdir(os.path.join(self.tmpdir, 'ned'))
        open(os.path.join(self.tmpdir, 'file.txt'), 'w').write('wobble\n')
        self.filesystem = pathutils.FileSystem(
            osfs.OSDirectory(self.tmpdir)
        )

    def tearDown(self):
        shutil.rmtree( self.tmpdir )

    def test_listdir(self):
        nodes = self.filesystem.fetch( '/' ).children()
        paths = [path for (path, node) in nodes]
        paths.sort()
        self.assertEquals(paths, ['.', '..', 'file.txt', 'ned'])

    def test_mkdir(self):
        self.filesystem.fetch( '/' ).createDirectory('fred')
        nodes = self.filesystem.fetch( '/fred' ).children()
        self.assertEquals( [ path for (path, node) in nodes ], [ '.', '..' ] )

    def test_rmdir(self):
        self.filesystem.fetch( '/ned' ).remove()
        nodes = self.filesystem.fetch( '/' ).children()
        paths = [path for (path, node) in nodes]
        paths.sort()
        self.assertEquals(paths, ['.', '..', 'file.txt'])

    def test_rmfile(self):
        self.filesystem.fetch( '/file.txt' ).remove()
        nodes = self.filesystem.fetch( '/' ).children()
        paths = [path for (path, node) in nodes]
        paths.sort()
        self.assertEquals(paths, ['.', '..', 'ned'])

    def test_rename(self):
        self.filesystem.fetch( '/ned' ).rename('sed')
        nodes = self.filesystem.fetch( '/' ).children()
        paths = [path for (path, node) in nodes]
        paths.sort()
        self.assertEquals(paths, ['.', '..', 'file.txt', 'sed'])

    def test_mkfile(self):
        new = self.filesystem.fetch( '/' ).createFile( 'fred.txt')
        nodes = self.filesystem.fetch( '/' ).children()
        paths = [path for (path, node) in nodes]
        paths.sort()
        self.assertEquals(paths, ['.', '..', 'file.txt', 'fred.txt', 'ned'])

    def test_writefile(self):
        new = self.filesystem.fetch( '/' ).createFile('fred.txt')
        new.open(os.O_WRONLY)
        new.writeChunk( 0, 'roar' )
        new.close()
        new.open(os.O_RDONLY)
        text = new.readChunk( 0, 100 )
        new.close()
        self.assertEquals( text, 'roar' )

    def test_readfile(self):
        fh = self.filesystem.fetch( '/file.txt' )
        fh.open(os.O_RDONLY)
        text = fh.readChunk( 0, 100 )
        fh.close()
        self.assertEquals( text, 'wobble\n' )

    def test_exists(self):
        root = self.filesystem.fetch('/')
        self.failUnless(root.exists('file.txt'))
        self.failIf(root.exists('noodle'))



class InMemVFSTest(OSVFSTest):

    def setUp(self):
        root = inmem.FakeDirectory()
        filesystem = pathutils.FileSystem( root )
        ned = inmem.FakeDirectory('ned', root)
        f = inmem.FakeFile('file.txt', root, 'wobble\n')
        root._children = { 'ned' : ned, 'file.txt' : f }
        self.filesystem = filesystem

    def tearDown(self):
        pass

