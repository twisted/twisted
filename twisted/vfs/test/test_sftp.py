from twisted.conch.ssh.filetransfer import FXF_READ, FXF_WRITE, FXF_CREAT, FXF_APPEND, FXF_EXCL
from twisted.trial import unittest

from twisted.vfs import ivfs, pathutils
from twisted.vfs.adapters import sftp
from twisted.vfs.backends import inmem

sftpAttrs = ['size', 'uid', 'gid', 'nlink', 'mtime', 'atime', 'permissions']
sftpAttrs.sort()

class SFTPAdapterTest(unittest.TestCase):
    def setUp(self):
        root = inmem.FakeDirectory()
        filesystem = pathutils.FileSystem( root )
        self.ned = ned = inmem.FakeDirectory('ned', root)
        self.f = f = inmem.FakeFile('file.txt', root, 'wobble\n')
        root._children = { 'ned' : ned, 'file.txt' : f }
        self.filesystem = filesystem
        self.avatar = sftp.VFSConchUser('radix', root)
        self.sftp = sftp.AdaptFileSystemUserToISFTP(self.avatar)

    def _assertNodes(self, dir, mynodes):
        nodes = [x[0] for x in self.filesystem.fetch(dir).children()]
        nodes.sort()
        mynodes.sort()
        return self.assertEquals(nodes, mynodes)

    def test_openFile(self):
        child = self.sftp.openFile('file.txt', 0, None)
        self.failUnless(ivfs.IFileSystemNode.providedBy(child))

    def test_openNewFile(self):
        # Opening a new file should work if FXF_CREAT is passed
        child = self.sftp.openFile('new file.txt', FXF_READ|FXF_CREAT, None)
        self.failUnless(ivfs.IFileSystemNode.providedBy(child))

        # But not with FXF_READ alone.
        self.assertRaises(IOError,
                       self.sftp.openFile, 'new file 2.txt', FXF_READ, None)

        # The FXF_WRITE flag alone can create a file.
        child = self.sftp.openFile('new file 3.txt', FXF_WRITE, None)
        self.failUnless(ivfs.IFileSystemNode.providedBy(child))

        # So, of course FXF_WRITE plus FXF_READ can too.
        child = self.sftp.openFile('new file 4.txt', FXF_WRITE|FXF_READ, None)
        self.failUnless(ivfs.IFileSystemNode.providedBy(child))

        # The FXF_APPEND flag alone can create a file.
        child = self.sftp.openFile('new file 5.txt', FXF_APPEND, None)
        self.failUnless(ivfs.IFileSystemNode.providedBy(child))

    def test_openNewFileExclusive(self):
        # Creating a file should fail if the FXF_EXCL flag is given and the file
        # already exists.
        flags = FXF_WRITE|FXF_CREAT|FXF_EXCL
        self.assertRaises(ivfs.VFSError,
                       self.sftp.openFile, 'file.txt', flags, None)

    def test_removeFile(self):
        self.sftp.removeFile('/file.txt')
        self._assertNodes('/', ['.', '..', 'ned'])

    def test_renameFile(self):
        self.sftp.renameFile('/file.txt', '/radixiscool.txt')
        self._assertNodes('/', ['.', '..', 'ned', 'radixiscool.txt'])

    def test_renameToDirectory(self):
        self.sftp.renameFile('/file.txt', '/ned')
        self._assertNodes('/', ['.', '..', 'ned'])
        self._assertNodes('/ned', ['.', '..', 'file.txt'])

    def test_makeDirectory(self):
        self.sftp.makeDirectory('/dir', None)
        self._assertNodes('/', ['.', '..', 'file.txt', 'ned', 'dir'])
        self._assertNodes('/dir', ['.', '..'])

    def test_removeDirectory(self):
        self.sftp.makeDirectory('/dir', None)
        self.sftp.removeDirectory('/dir')
        self._assertNodes('/', ['.', '..', 'file.txt', 'ned'])

    def test_openDirectory(self):
        for name, lsline, attrs in self.sftp.openDirectory('/ned'):
            keys = attrs.keys()
            keys.sort()
            self.failUnless(sftpAttrs, keys)

    def test_getAttrs(self):
        attrs = self.sftp.getAttrs('/ned', None).keys()
        attrs.sort()
        self.failUnless(sftpAttrs, attrs)

    def test_dirlistWithoutAttrs(self):
        self.ned.getMetadata = self.f.getMetadata = lambda: {}
        for name, lsline, attrs in self.sftp.openDirectory('/'):
            keys = attrs.keys()
            keys.sort()
            self.failUnless(sftpAttrs, keys)

