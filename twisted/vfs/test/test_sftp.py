# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""Tests for the SFTP server VFS adapter."""

import os
import time

from twisted.conch.ssh.filetransfer import FXF_READ, FXF_WRITE, FXF_CREAT
from twisted.conch.ssh.filetransfer import FXF_APPEND, FXF_EXCL, FXF_TRUNC
from twisted.conch.ssh.filetransfer import SFTPError
from twisted.conch.ssh.filetransfer import FX_NO_SUCH_FILE, FX_FAILURE
from twisted.conch.ssh.filetransfer import FX_PERMISSION_DENIED
from twisted.conch.ssh.filetransfer import FX_OP_UNSUPPORTED, FX_NOT_A_DIRECTORY
from twisted.conch.ssh.filetransfer import FX_FILE_IS_A_DIRECTORY
from twisted.conch.ssh.filetransfer import FX_FILE_ALREADY_EXISTS
from twisted.conch.interfaces import ISFTPFile
from twisted.trial import unittest
from twisted.internet import defer

from twisted.vfs import ivfs, pathutils
from twisted.vfs.adapters import sftp
from twisted.vfs.backends import inmem, osfs

sftpAttrs = ['size', 'uid', 'gid', 'nlink', 'mtime', 'atime', 'permissions']
sftpAttrs.sort()


class SFTPErrorTranslationTests(unittest.TestCase):

    def assertTranslation(self, error, code):
        """Asserts that the translate_error decorator translates 'error' to an
        SFTPError with a code of 'code'."""
        message = 'test error message'
        def f():
            raise error(message)
        f = sftp.translateErrors(f)
        e = self.assertRaises(SFTPError, f)
        self.assertEqual(code, e.code)
        self.assertEqual(message, e.message)

    def testPermissionError(self):
        """PermissionError is translated to FX_PERMISSION_DENIED."""
        self.assertTranslation(ivfs.PermissionError, FX_PERMISSION_DENIED)

    def testNotFoundError(self):
        """NotFoundError is translated to FX_NO_SUCH_FILE."""
        self.assertTranslation(ivfs.NotFoundError, FX_NO_SUCH_FILE)

    def testVFSError(self):
        """VFSErrors that aren't otherwise caught are translated to
        FX_FAILURE."""
        self.assertTranslation(ivfs.VFSError, FX_FAILURE)

    def testNotImplementedError(self):
        """NotImplementedError is translated to FX_OP_UNSUPPORTED."""
        self.assertTranslation(NotImplementedError, FX_OP_UNSUPPORTED)

    def testTranslateDeferredError(self):
        """If the decorated function returns a Deferred, the error should still
        be translated."""
        def f():
            return defer.fail(ivfs.VFSError('error message'))
        f = sftp.translateErrors(f)
        d = f()
        return self.assertFailure(d, SFTPError)

    def testTranslateDeferredError2(self):
        """If the decorated function returns a Deferred that hasn't fired
        immediately, the error should still be translated."""
        d = defer.Deferred()
        def f():
            return d
        f = sftp.translateErrors(f)
        d2 = f()
        d.errback(ivfs.VFSError("foo"))
        return self.assertFailure(d2, SFTPError)


class SFTPAdapterTest(unittest.TestCase):

    def rootDir(self):
        return inmem.FakeDirectory()

    def setUp(self):
        root = self.rootDir()

        # Create a subdirectory 'ned'
        self.ned = ned = root.createDirectory('ned')

        # Create a file 'file.txt'
        self.f = f = root.createFile('file.txt')
        flags = os.O_WRONLY
        flags |= getattr(os, 'O_BINARY', 0)  # for windows
        f.open(flags).writeChunk(0, 'wobble\n')
        f.close()

        self.root = root
        self.avatar = sftp.VFSConchUser('radix', root)
        self.sftp = sftp.AdaptFileSystemUserToISFTP(self.avatar)

    def _assertNodes(self, dir, mynodes):
        nodes = [x[0] for x in pathutils.fetch(self.root, dir).children()]
        nodes.sort()
        mynodes.sort()
        return self.assertEquals(nodes, mynodes)

    def test_openFile(self):
        child = self.sftp.openFile('file.txt', 0, None)
        self.failUnless(ISFTPFile.providedBy(child))

    def test_openNewFile(self):
        # Opening a new file with FXF_READ alone should fail with
        # FX_NO_SUCH_FILE.
        e = self.assertRaises(SFTPError,
           self.sftp.openFile, 'new file.txt', FXF_READ, None)
        self.assertEqual(FX_NO_SUCH_FILE, e.code)

    def test_openNewFileCreate(self):
        # Opening a new file should work if FXF_CREAT is passed.
        child = self.sftp.openFile('new file.txt', FXF_READ|FXF_CREAT, None)
        self.failUnless(ISFTPFile.providedBy(child))

    def test_openNewFileWrite(self):
        # The FXF_WRITE flag alone can create a file.
        child = self.sftp.openFile('new file.txt', FXF_WRITE, None)
        self.failUnless(ISFTPFile.providedBy(child))

    def test_openNewFileReadWrite(self):
        # So, of course FXF_WRITE plus FXF_READ can create a file too.
        child = self.sftp.openFile('new file.txt', FXF_WRITE|FXF_READ, None)
        self.failUnless(ISFTPFile.providedBy(child))

    def test_openNewFileAppend(self):
        # The FXF_APPEND flag alone can create a file.
        child = self.sftp.openFile('new file.txt', FXF_APPEND, None)
        self.failUnless(ISFTPFile.providedBy(child))

    def test_openNewFileExclusive(self):
        flags = FXF_WRITE|FXF_CREAT|FXF_EXCL
        # But if the file doesn't exist, then it should work.
        child = self.sftp.openFile('new file.txt', flags, None)
        self.failUnless(ISFTPFile.providedBy(child))

    def test_openExistingFileExclusive(self):
        # Creating a file should fail if the FXF_EXCL flag is given and the file
        # already exists.  This fails with FX_FILE_ALREADY_EXISTS (which is
        # actually just FX_FAILURE for now, see the comment in
        # twisted/conch/ssh/filetransfer.py).
        flags = FXF_WRITE|FXF_CREAT|FXF_EXCL
        e = self.assertRaises(SFTPError,
                              self.sftp.openFile, 'file.txt', flags, None)
        self.assertEqual(FX_FILE_ALREADY_EXISTS, e.code)

    def test_openFileTrunc(self):
        # The FXF_TRUNC flag causes an existing file to be truncated.
        child = self.sftp.openFile('file.txt', FXF_WRITE|FXF_TRUNC, None)
        self.failUnless(ISFTPFile.providedBy(child))

        # The file should have been truncated to 0 size.
        attrs = child.getAttrs()
        self.failUnlessEqual(0, attrs['size'])

    def test_removeFile(self):
        self.sftp.removeFile('/file.txt')
        self._assertNodes('/', ['.', '..', 'ned'])

    def test_removeFileMissing(self):
        # Trying to remove a file that doesn't exist should fail with
        # FX_NO_SUCH_FILE.
        e = self.assertRaises(SFTPError,
           self.sftp.removeFile, 'file-that-does-not-exist.txt')
        self.assertEqual(FX_NO_SUCH_FILE, e.code)

    def test_renameFile(self):
        self.sftp.renameFile('/file.txt', '/radixiscool.txt')
        self._assertNodes('/', ['.', '..', 'ned', 'radixiscool.txt'])

    def test_renameFileRelative(self):
        self.sftp.renameFile('file.txt', 'radixiscool.txt')
        self._assertNodes('/', ['.', '..', 'ned', 'radixiscool.txt'])

    def test_renameFileToExistingDirectory(self):
        """
        Renaming a file to an existing directory should fail.
        """
        e = self.assertRaises(SFTPError,
                              self.sftp.renameFile, '/file.txt', '/ned')
        self.assertEqual(FX_FILE_ALREADY_EXISTS, e.code)

    def test_renameDirectoryToExistingDirectory(self):
        """
        Renaming a directory to an existing directory should fail.
        """
        self.ned.createDirectory('foo').createFile('a')
        self.ned.createDirectory('bar').createFile('b')
        e = self.assertRaises(SFTPError,
                              self.sftp.renameFile, '/ned/foo', '/ned/bar')
        self.assertEqual(FX_FILE_ALREADY_EXISTS, e.code)

    def test_makeDirectory(self):
        self.sftp.makeDirectory('/dir', None)
        self._assertNodes('/', ['.', '..', 'file.txt', 'ned', 'dir'])
        self._assertNodes('/dir', ['.', '..'])

    def test_makeSubDirectory(self):
        self.sftp.makeDirectory('/dir', None)
        self.sftp.makeDirectory('/dir/subdir', None)
        self._assertNodes('/', ['.', '..', 'file.txt', 'ned', 'dir'])
        self._assertNodes('/dir', ['.', '..', 'subdir'])
        self._assertNodes('/dir/subdir', ['.', '..'])

    def test_removeDirectory(self):
        self.sftp.makeDirectory('/dir', None)
        self.sftp.removeDirectory('/dir')
        self._assertNodes('/', ['.', '..', 'file.txt', 'ned'])

    def test_openDirectory(self):
        for name, lsline, attrs in self.sftp.openDirectory('/ned'):
            keys = attrs.keys()
            keys.sort()
            self.failUnless(sftpAttrs, keys)

    def test_getAttrsPath(self):
        # getAttrs by path name
        attrs = self.sftp.getAttrs('/ned', None).keys()
        attrs.sort()
        self.failUnless(sftpAttrs, attrs)

    def test_getAttrsFile(self):
        # getAttrs on an open file
        path = 'file.txt'
        child = self.sftp.openFile(path, 0, None)
        attrs = child.getAttrs()
        self.failUnlessEqual(7, attrs['size'])

    def test_setAttrsPath(self):
        # setAttrs on a path name
        for mtime in [86401, 200000, int(time.time())]:
            try:
                self.sftp.setAttrs('/file.txt', {'mtime': mtime})
            except SFTPError, e:
                if e.code == FX_OP_UNSUPPORTED:
                    raise unittest.SkipTest(
                        "The VFS backend %r doesn't support setAttrs"
                        % (self.root,))
                else:
                    raise
            else:
                self.assertEqual(
                    mtime, self.sftp.getAttrs('/file.txt', False)['mtime'])

    def test_setAttrsFile(self):
        # setAttrs on an open file
        file = self.sftp.openFile('file.txt', 0, None)
        for mtime in [86401, 200000, int(time.time())]:
            try:
                file.setAttrs({'mtime': mtime})
            except NotImplementedError:
                raise unittest.SkipTest(
                    "The VFS backend %r doesn't support setAttrs"
                    % (self.root,))
            else:
                self.assertEqual(
                    mtime, file.getAttrs()['mtime'])

    def test_dirlistWithoutAttrs(self):
        self.ned.getMetadata = self.f.getMetadata = lambda: {}
        for name, lsline, attrs in self.sftp.openDirectory('/'):
            keys = attrs.keys()
            keys.sort()
            self.failUnless(sftpAttrs, keys)

    def test_openDirectoryAsFile(self):
        # http://www.ietf.org/internet-drafts/draft-ietf-secsh-filexfer-12.txt
        # 8.1.1.1 says: "If 'filename' is a directory file, the server MUST
        # return an SSH_FX_FILE_IS_A_DIRECTORY error."
        e = self.assertRaises(SFTPError, self.sftp.openFile, 'ned', 0, None)
        self.assertEqual(FX_FILE_IS_A_DIRECTORY, e.code)

    def test_openFileAsDirectory(self):
        # 8.1.2: "If 'path' does not refer to a directory, the server MUST
        # return SSH_FX_NOT_A_DIRECTORY."
        e = self.assertRaises(SFTPError, self.sftp.openDirectory, 'file.txt')
        self.assertEqual(FX_NOT_A_DIRECTORY, e.code)

    def test_removeDirectoryAsFile(self):
        # 8.3: "This request cannot be used to remove directories.  The server
        # MUST return SSH_FX_FILE_IS_A_DIRECTORY in this case."
        e = self.assertRaises(SFTPError, self.sftp.removeFile, 'ned')
        self.assertEqual(FX_FILE_IS_A_DIRECTORY, e.code)

    def test_removeDirectoryMissing(self):
        # Trying to remove a directory that doesn't exist should give
        # FX_NO_SUCH_FILE.
        e = self.assertRaises(SFTPError, self.sftp.removeDirectory, 'missing')
        self.assertEqual(FX_NO_SUCH_FILE, e.code)

    def test_getAttrsMissing(self):
        # getAttrs on a file that doesn't exist gives FX_NO_SUCH_FILE.
        e = self.assertRaises(SFTPError, self.sftp.getAttrs, 'missing', None)
        self.assertEqual(FX_NO_SUCH_FILE, e.code)

    def test_setAttrsMissing(self):
        # setAttrs on a file that doesn't exist gives FX_NO_SUCH_FILE.
        e = self.assertRaises(SFTPError, self.sftp.setAttrs, 'missing', {})
        self.assertEqual(FX_NO_SUCH_FILE, e.code)


class SFTPAdapterOSFSTest(SFTPAdapterTest):
    def rootDir(self):
        path = self.mktemp()
        os.mkdir(path)
        return osfs.OSDirectory(path)


class DummyDir(inmem.FakeDirectory):
    def createDirectory(self, childName):
        d = defer.Deferred()
        d2 = defer.maybeDeferred(inmem.FakeDirectory.createDirectory,
                                 self, childName)
        from twisted.internet import reactor
        reactor.callLater(1, d2.chainDeferred, d)
        return d

class SFTPAdapterDeferredTestCase(unittest.TestCase):
    def setUp(self):
        root = DummyDir()
        filesystem = pathutils.FileSystem(root)
        self.filesystem = filesystem

        avatar = sftp.VFSConchUser('radix', root)
        self.sftp = sftp.AdaptFileSystemUserToISFTP(avatar)

    def _assertNodes(self, dir, mynodes):
        nodes = [x[0] for x in self.filesystem.fetch(dir).children()]
        nodes.sort()
        mynodes.sort()
        return self.assertEquals(nodes, mynodes)

    def test_makeDirectoryDeferred(self):
        # Allow Deferreds to be returned from createDirectory
        d = defer.maybeDeferred(self.sftp.makeDirectory, '/dir', None)
        def cb(result):
            self._assertNodes('/', ['.', '..', 'dir'])
        return d.addCallback(cb)

