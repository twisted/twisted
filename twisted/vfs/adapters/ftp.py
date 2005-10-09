import os, time
from cStringIO import StringIO

from twisted.protocols.ftp import IFTPShell, IReadFile, IWriteFile
from twisted.internet import defer
from twisted.internet.interfaces import IConsumer
from twisted.web2.stream import StreamProducer, IByteStream

from zope.interface import implements

from twisted.python import components
from twisted.vfs import ivfs, pathutils

# XXX: Import this to make sure the adapter registration has happened.
from twisted.vfs.adapters import stream


class FileSystemToIFTPShellAdaptor:

    implements(IFTPShell)

    def __init__(self, filesystem):
        self.filesystem = filesystem

    def _makePath(segments):
        return '/'.join(segments)
    _makePath = staticmethod(_makePath)

    def makeDirectory(self, path):
        dirname, basename = path[:-1], path[-1]
        parent = self.filesystem.fetch(self._makePath(dirname))
        try:
            parent.createDirectory(basename)
        except:
            return defer.fail()
        else:
            return defer.succeed(None)

    def removeDirectory(self, path):
        try:
            node = self.filesystem.fetch(self._makePath(path))
            if not ivfs.IFileSystemContainer.providedBy(node):
                raise IOError("removeDirectory can only remove directories.")
            node.remove()
        except:
            return defer.fail()
        else:
            return defer.succeed(None)

    def removeFile(self, path):
        try:
            node = self.filesystem.fetch(self._makePath(path))
            if ivfs.IFileSystemContainer.providedBy(node):
                raise IOError("removeFile cannot remove directories.")
            node.remove()
        except:
            return defer.fail()
        else:
            return defer.succeed(None)

    def list(self, path, keys=()):
        node = self.filesystem.fetch(self._makePath(path))

        result = []
        for childName, childNode in node.children():
            attrs = self._attrify(childNode)
            result.append((childName, [attrs[attrName] for attrName in keys]))

        return defer.succeed(result)

    # XXX - this should probably go in a helper somewhere
    def _attrify(self, node):
        meta = node.getMetadata()
        permissions = meta.get('permissions', None)
        directory = ivfs.IFileSystemContainer.providedBy(node)
        if permissions is None:
            # WTF
            if ivfs.IFileSystemContainer.providedBy(node):
                permissions = 16877
            else:
                permissions = 33188

        return {'permissions': permissions,
                'directory': directory,
                'size': meta.get('size', 0),
                'owner': str(meta.get('uid', 'user')),
                'group': str(meta.get('gid', 'user')),
                'modified': meta.get('mtime', time.time()),
                'hardlinks': meta.get('nlink', 1)
                }

    def access(self, path):
        # XXX: stubbed out to always succeed.
        return defer.succeed(None)

    def openForReading(self, segs):
        node = self.filesystem.fetch(self._makePath(segs))
        frvfs = FTPReadVFS(node)
        return defer.succeed(frvfs)

    def openForWriting(self, segs):
        # XXX: this method is way too ugly
        dirname, basename = segs[:-1], segs[-1]
        node = self.filesystem.fetch(
            self._makePath(dirname)).createFile(basename)
        fwvfs = FTPWriteVFS(node)
        return defer.succeed(fwvfs)

    def stat(self, path, keys=()):
        node = self.filesystem.fetch(self._makePath(path))
        attrs = self._attrify(node)
        return defer.succeed([attrs[attrName] for attrName in keys])

    def rename(self, from_, to):
        assert len(to) == 1, (
            "renaming into other directories isn't supported yet.")
        try:
            self.filesystem.fetch(self._makePath(from_)).rename(to[0])
        except:
            return defer.fail()
        else:
            return defer.succeed(None)


class FTPReadVFS(object):
    implements(IReadFile)

    def __init__(self, node):
        self.node = node

    def send(self, consumer):
        return StreamProducer(IByteStream(self.node)).beginProducing(consumer)


class FTPWriteVFS(object):
    implements(IWriteFile)

    def __init__(self, node):
        self.node = node

    def receive(self):
        return defer.succeed(IConsumer(self.node))


class _FileToConsumerAdapter:
    implements(IConsumer)

    def __init__(self, original):
        self.original = original
        self.offset = 0

    def write(self, bytes):
        self.original.writeChunk(self.offset, bytes)
        self.offset += len(bytes)



components.registerAdapter(FileSystemToIFTPShellAdaptor,
                           pathutils.IFileSystem, IFTPShell)
components.registerAdapter(_FileToConsumerAdapter,
                           ivfs.IFileSystemLeaf, IConsumer)


