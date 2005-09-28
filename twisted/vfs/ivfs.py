from zope.interface import Interface, Attribute

class VFSError(Exception):
    """Base class for all VFS errors."""


class IFileSystemNode(Interface):

    parent = Attribute(
        """parent node"""
    )

    def getMetadata(self):
        """
        returns a map of arbitrary metadata. As an example, here's what
        SFTP expects (but doesn't require):
        {
            'size'         : size of file in bytes,
            'uid'          : owner of the file,
            'gid'          : group owner of the file,
            'permissions'  : file permissions,
            'atime'        : last time the file was accessed,
            'mtime'        : last time the file was modified,
            'nlink'        : number of links to the file
        }

        Protocols that need metadata should handle the case when a
        particular value isn't available as gracefully as possible.
        """

    def remove(self):
        """
        Removes this node.
        An error is raised if the node is a directory and is not empty.
        """

    def rename(self, newName):
        """
        Renames this node to newName.  newName can be in a different
        directory.  If the destination is an existing directory, an
        error will be raised.
        """


class IFileSystemLeaf(IFileSystemNode):
    def open(self, flags):
        """
        Opens the file with flags. Flags should be a bitmask based on
        the os.O_* flags.
        """

    def close(self):
        """closes this node"""

    def readChunk(self, offset, length):
        """
        Leaf should have been previously opened with suitable flags.
        Reads length bytes or until the end of file from this leaf from
        the given offset.
        """

    def writeChunk(self, offset, data):
        """
        Leaf should have been previously opened with suitable flags.
        Writes data to leaf from the given offset.
        """

class IFileSystemContainer(IFileSystemNode):

    def children(self):
        """
        returns a list of 2 element tuples
        [ ( path, nodeObject ) ]
        """

    def child(self, childName):
        """
        returns a node object for child childName
        """

    def createDirectory(self, childName):
        """
        Creates a new folder named childName under this folder.
        An error is raised if the folder already exists.
        """

    def createFile(self, childName):
        """
        Creates a new file named childName under this folder.
        An error is raised if the file already exists.
        """

    def exists(self, childName):
        """
        returns True if container has a child childName, False otherwise
        """
