# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the FTP server VFS adapter.
"""

from twisted.trial import unittest
from twisted.test.test_ftp import IFTPShellTestsMixin, IReadWriteTestsMixin

from twisted.vfs.backends import inmem
from twisted.vfs import pathutils, ivfs
from twisted.vfs.adapters.ftp import FileSystemToIFTPShellAdaptor



class FTPAdapterTestCase(unittest.TestCase, IFTPShellTestsMixin):
    """
    Test methods of L{FileSystemToIFTPShellAdaptor}, the adapter from a vfs
    filesystem to a L{twisted.protocols.ftp.IFTPShell}: it should pass the same
    tests that the standard read-write ftp shell implementation.
    """

    def setUp(self):
        """
        Create a filesystem for tests and instantiate a FTP shell.
        """
        self.root = inmem.FakeDirectory()

        filesystem = pathutils.FileSystem(self.root)
        self.shell = FileSystemToIFTPShellAdaptor(filesystem)


    def directoryExists(self, path):
        """
        Test if the directory exists at C{path}.
        """
        return (self.root.exists(path) and
                ivfs.IFileSystemContainer.providedBy(self.root.child(path)))


    def createDirectory(self, path):
        """
        Create a directory in C{path}.
        """
        return self.root.createDirectory(path)


    def fileExists(self, path):
        """
        Test if the file exists at C{path}.
        """
        return (self.root.exists(path) and
                ivfs.IFileSystemLeaf.providedBy(self.root.child(path)))


    def createFile(self, path, fileContent=''):
        """
        Create a file named C{path} with some content.
        """
        f = self.root.createFile(path)
        f.writeChunk(0, fileContent)
        return f



class ReadWriteVFSTestCase(unittest.TestCase, IReadWriteTestsMixin):
    """
    Tests for L{twisted.vfs.adapters.ftp.FTPReadVFS} and
    L{twisted.vfs.adapters.ftp.FTPWriteVFS}, objects returned by the shell in
    C{openforReading} and C{openForWriting}
    """

    def setUp(self):
        """
        Create a filesystem for tests.
        """
        self.root = inmem.FakeDirectory()
        self.f = self.root.createFile('file.txt')

        filesystem = pathutils.FileSystem(self.root)
        self.shell = FileSystemToIFTPShellAdaptor(filesystem)


    def getFileReader(self, content):
        """
        Return a C{FTPReadVFS} instance via C{openForReading}.
        """
        self.f.writeChunk(0, content)
        return self.shell.openForReading(('file.txt',))


    def getFileWriter(self):
        """
        Return a C{FTPWriteVFS} instance via C{openForWriting}.
        """
        return self.shell.openForWriting(('file.txt',))


    def getFileContent(self):
        """
        Return the content of the inmem file.
        """
        return self.f.readChunk(0, -1)

