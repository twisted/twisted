from zope.interface import implements
from twisted.web2.stream import SimpleStream, IByteStream
from twisted.vfs.ivfs import IFileSystemLeaf
from twisted.python import components

class FileSystemLeafStream(SimpleStream):
    implements(IByteStream)
    """A stream that reads data from a FileSystemLeaf."""
    # 65K, minus some slack
    CHUNK_SIZE = 2 ** 2 ** 2 ** 2 - 32

    def __init__(self, leaf, start=0, length=None):
        """
        Create the stream from leaf. If you specify start and length,
        use only that portion of the leaf.
        """
        self.leaf = leaf
        self.start = start
        if length is None:
            self.length = leaf.getMetadata()['size']
        else:
            self.length = length

    def read(self):
        if self.leaf is None:
            return None

        length = self.length
        if length == 0:
            self.leaf = None
            return None

        readSize = min(length, self.CHUNK_SIZE)
        b = self.leaf.readChunk(self.start, readSize)
        bytesRead = len(b)

        if bytesRead != readSize:
            raise RuntimeError(
                "Ran out of data reading vfs leaf %r, expected %d more bytes" %
                    (self.leaf, length))
        else:
            self.length -= bytesRead
            self.start += bytesRead
            return b

    def close(self):
        self.leaf = None
        SimpleStream.close(self)

components.registerAdapter(FileSystemLeafStream, IFileSystemLeaf, IByteStream)
