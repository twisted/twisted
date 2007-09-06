# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the FTP server VFS adapter.
"""

from twisted.trial import unittest
from twisted.test.test_ftp import IFTPShellTestCase, IReadWriteTestCase

from twisted.vfs.backends import inmem
from twisted.vfs import pathutils, ivfs
from twisted.vfs.adapters.ftp import FileSystemToIFTPShellAdaptor
from twisted.vfs.adapters.ftp import FTPReadVFS, FTPWriteVFS



class DirectFTPAdapterTestCase(unittest.TestCase, IFTPShellTestCase):
    """
    Test direct calls on L{FileSystemToIFTPShellAdaptor}.
    """

    def setUp(self):
        """
        Create a filesystem for tests and intantiate a FTP shell.
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


    def createFile(self, path):
        """
        Create a file named C{path} with some content.
        """
        f = self.root.createFile(path)
        f.writeChunk(0, 'wobble\n')
        return f



class ReadWriteVFSTestCase(unittest.TestCase, IReadWriteTestCase):
    """
    Tests for L{FTPReadVFS} and L{FTPWriteVFS}.
    """

    def setUp(self):
        """
        Create a filesystem for tests.
        """
        self.root = inmem.FakeDirectory()
        self.f = self.root.createFile('file.txt')
        self.f.writeChunk(0, 'wobble\n')


    def getFileReader(self, content):
        """
        Return a C{FTPReadVFS} instance.
        """
        self.f.writeChunk(0, content)
        return FTPReadVFS(self.f)


    def getFileWriter(self):
        """
        Return a C{FTPWriteVFS} instance.
        """
        return FTPWriteVFS(self.f)


    def getFileContent(self):
        """
        Return the content of the inmem file.
        """
        return self.f.readChunk(0, -1)

