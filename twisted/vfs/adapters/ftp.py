# -*- test-case-name: twisted.vfs.test.test_ftp -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Adapter for FTP protocol.
"""

import os, time

from twisted.protocols import ftp
from twisted.internet import defer
from twisted.internet.interfaces import IConsumer
from twisted.web2.stream import StreamProducer, IByteStream

from zope.interface import implements

from twisted.python import components
from twisted.vfs import ivfs, pathutils

# XXX: Import this to make sure the adapter registration has happened.
from twisted.vfs.adapters import stream



def vfsToFtpError(vfsError):
    """
    Map vfs errors to the corresponding ftp errors, if it exists.
    """
    if isinstance(vfsError, ivfs.NotFoundError):
        return defer.fail(ftp.FileNotFoundError(vfsError))
    elif isinstance(vfsError, ivfs.AlreadyExistsError):
        return defer.fail(ftp.FileExistsError(vfsError))
    return defer.fail(vfsError)



class FileSystemToIFTPShellAdaptor(object):
    """
    Wrap a VFS filesystem to an L{ftpIFTPShell} interface.
    """
    implements(ftp.IFTPShell)

    def __init__(self, filesystem):
        """
        @param filesystem: the root of the FTP server.
        @type filesystem: L{ivfs.IFileSystemContainer}.
        """
        self.filesystem = filesystem


    def _makePath(segments):
        """
        Make a path from its segments.
        """
        return '/'.join(segments)
    _makePath = staticmethod(_makePath)


    def makeDirectory(self, path):
        """
        Create a directory named C{path}.
        """
        if len(path) == 1:
            path = ('.', path[0])
        dirname, basename = path[:-1], path[-1]
        parent = self.filesystem.fetch(self._makePath(dirname))
        try:
            parent.createDirectory(basename)
        except ivfs.VFSError, e:
            return vfsToFtpError(e)
        except:
            return defer.fail()
        else:
            return defer.succeed(None)


    def removeDirectory(self, path):
        """
        Remove the given directory.
        """
        try:
            node = self.filesystem.fetch(self._makePath(path))
            if not ivfs.IFileSystemContainer.providedBy(node):
                raise ftp.IsNotADirectoryError(
                    "removeDirectory can only remove directories.")
            node.remove()
        except ivfs.VFSError, e:
            return vfsToFtpError(e)
        except:
            return defer.fail()
        else:
            return defer.succeed(None)


    def removeFile(self, path):
        """
        Remove the file at C{path}.
        """
        try:
            node = self.filesystem.fetch(self._makePath(path))
            if not ivfs.IFileSystemLeaf.providedBy(node):
                raise ftp.IsADirectoryError(
                    "removeFile can only remove files.")
            node.remove()
        except ivfs.VFSError, e:
            return vfsToFtpError(e)
        except:
            return defer.fail()
        else:
            return defer.succeed(None)


    def list(self, path, keys=()):
        """
        List all files and directories in C{path}.

        @param keys: the name of the metadatas to return.
        @type keys: C{tuple} of C{str}.
        """
        try:
            node = self.filesystem.fetch(self._makePath(path))
        except ivfs.VFSError, e:
            return vfsToFtpError(e)
        except:
            return defer.fail()

        result = []
        try:
            if ivfs.IFileSystemContainer.providedBy(node):
                for childName, childNode in node.children()[2:]:
                    attrs = self._attrify(childNode, keys)
                    result.append((childName, attrs))
            else:
                attrs = self._attrify(node, keys)
                result.append((node.name, attrs))
        except KeyError, e:
            return defer.fail(AttributeError(e.args[0]))

        return defer.succeed(result)


    # XXX - this should probably go in a helper somewhere
    def _attrify(self, node, keys):
        meta = node.getMetadata()
        permissions = meta.get('permissions', None)
        directory = ivfs.IFileSystemContainer.providedBy(node)
        if permissions is None:
            # WTF
            if ivfs.IFileSystemContainer.providedBy(node):
                permissions = 16877
            else:
                permissions = 33188

        d = {'permissions': permissions,
             'directory': directory,
             'size': meta.get('size', 0),
             'owner': str(meta.get('uid', 'user')),
             'group': str(meta.get('gid', 'user')),
             'modified': meta.get('mtime', time.time()),
             'hardlinks': meta.get('nlink', 1)
             }
        return [d[k] for k in keys]


    def access(self, path):
        """
        Check if C{path} is accessible.
        """
        # XXX: we only fetch it for now, that's a first step, but it's not
        # sufficient to say if the path is really accessible.
        # See ticket 2875 in the tracker
        try:
            node = self.filesystem.fetch(self._makePath(path))
        except ivfs.VFSError, e:
            return vfsToFtpError(e)
        except:
            return defer.fail()
        else:
            return defer.succeed(None)


    def openForReading(self, path):
        """
        Open file at C{path} for reading.
        """
        try:
            node = self.filesystem.fetch(self._makePath(path))
            if ivfs.IFileSystemContainer.providedBy(node):
                raise ftp.IsADirectoryError("Can only open file for reading.")
        except ivfs.VFSError, e:
            return vfsToFtpError(e)
        except:
            return defer.fail()
        else:
            frvfs = FTPReadVFS(node)
            return defer.succeed(frvfs)


    def openForWriting(self, path):
        """
        Open file at C{path} for writing.
        """
        if len(path) == 1:
            path = ('.', path[0])
        dirname, basename = path[:-1], path[-1]
        try:
            node = self.filesystem.fetch(self._makePath(dirname))
            if (node.exists(basename) and
                 ivfs.IFileSystemContainer.providedBy(node.child(basename))):
                raise ftp.IsADirectoryError("Can only open file for writing.")
            node = node.createFile(basename, exclusive=False)
        except ivfs.VFSError, e:
            return vfsToFtpError(e)
        except:
            return defer.fail()
        else:
            fwvfs = FTPWriteVFS(node)
            return defer.succeed(fwvfs)


    def stat(self, path, keys=()):
        """
        Stat C{path} for metadatas C{keys}.
        """
        try:
            node = self.filesystem.fetch(self._makePath(path))
        except ivfs.VFSError, e:
            return vfsToFtpError(e)
        except:
            return defer.fail()
        else:
            try:
                attrs = self._attrify(node, keys)
            except KeyError, e:
                return defer.fail(AttributeError(e.args[0]))
            return defer.succeed(attrs)


    def rename(self, fromPath, toPath):
        """
        Rename C{fromPath} to C{toPath}.
        """
        if len(toPath) != 1:
            return defer.fail(NotImplementedError(
                "Renaming into other directories isn't supported yet."))
        try:
            self.filesystem.fetch(self._makePath(fromPath)).rename(toPath[0])
        except ivfs.VFSError, e:
            return vfsToFtpError(e)
        except:
            return defer.fail()
        else:
            return defer.succeed(None)



class FTPReadVFS(object):
    """
    Read a file source.
    """
    implements(ftp.IReadFile)

    def __init__(self, node):
        """
        Use C{node} as source of data.
        """
        self.node = node


    def send(self, consumer):
        """
        Start producing data using L{StreamProducer}.
        """
        return StreamProducer(IByteStream(self.node)).beginProducing(consumer)



class FTPWriteVFS(object):
    """
    Write to a file source.
    """
    implements(ftp.IWriteFile)

    def __init__(self, node):
        """
        Use C{node} as destination of data.
        """
        self.node = node


    def receive(self):
        """
        Return an consumer object able to write the data.
        """
        return defer.succeed(IConsumer(self.node))

    def close(self):
        """
        Perform post-write actions.
        """
        return defer.succeed(None)


class _FileToConsumerAdapter(object):
    """
    An adapter for writing to a VFS file.
    """
    implements(IConsumer)

    def __init__(self, original):
        """
        @param original: the vfs node.
        @type original: C{ivfs.IFileSystemLeaf}.
        """
        self.original = original
        self.offset = 0


    def registerProducer(self, producer, streaming):
        """
        Register the producer, and open original resource.
        """
        if not streaming:
            raise NotImplementedError("Non-streaming producer not supported.")
        self.producer = producer
        self.original.open(os.O_WRONLY)


    def unregisterProducer(self):
        """
        Unregister producer and close original resource.
        """
        self.producer = None
        self.original.close()


    def write(self, bytes):
        """
        Write data to the resource.
        """
        self.original.writeChunk(self.offset, bytes)
        self.offset += len(bytes)



components.registerAdapter(FileSystemToIFTPShellAdaptor,
                           pathutils.IFileSystem, ftp.IFTPShell)

components.registerAdapter(_FileToConsumerAdapter,
                           ivfs.IFileSystemLeaf, IConsumer)


