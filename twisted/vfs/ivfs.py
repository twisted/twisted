from zope.interface import Interface, Attribute

class VFSError(Exception):
    """Base class for all VFS errors."""

class PermissionError(VFSError):
    """The user does not have permission to perform the requested operation."""

class NotFoundError(VFSError):
    """The file or directory does not exist."""

class NotAContainerError(VFSError):
    """A container-like method called on a non-container-like node"""


class IFileSystemNode(Interface):

    parent = Attribute(
        """parent node"""
    )

    def getMetadata():
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

    # XXX: There should be a setMetadata, probably taking a map of the same form
    # returned by getMetadata (although obviously keys like 'nlink' aren't
    # settable.  Something like:
    # def setMetadata(metadata):
    #     """Sets metadata for a node.
    #
    #     Unrecognised keys will be ignored (but invalid values for a recognised
    #     key may cause an error to be raised).
    #     
    #     Typical keys are 'permissions', 'uid', 'gid', 'atime' and 'mtime'.
    #     
    #     @param metadata: a dict, like the one getMetadata returns.
    #     """
    # osfs.OSNode implements this; other backends should be similarly updated.
    #   -- spiv, 2006-06-02

    def remove():
        """
        Removes this node.
        An error is raised if the node is a directory and is not empty.
        """

    def rename(newName):
        """
        Renames this node to newName.  newName can be in a different
        directory.  If the destination is an existing directory, an
        error will be raised.
        """


class IFileSystemLeaf(IFileSystemNode):
    def open(flags):
        """
        Opens the file with flags. Flags should be a bitmask based on
        the os.O_* flags.
        """

    def close():
        """closes this node"""

    def readChunk(offset, length):
        """
        Leaf should have been previously opened with suitable flags.
        Reads length bytes or until the end of file from this leaf from
        the given offset.
        """

    def writeChunk(offset, data):
        """
        Leaf should have been previously opened with suitable flags.
        Writes data to leaf from the given offset.
        """



class IFileSystemContainer(IFileSystemNode):

    def children():
        """
        @returns: a Deferred which will fire with a list of 2 element tuples
            [(segment, nodeObject)]

        @raises ivfs.NotAContainerError: if this node isn't a container
        @raises ivfs.NotFoundError: if this node does not exist
        """

    def child(*segments):
        """
        @returns: immediately with a node object representing a
            filesystem resource at the path pointed to by segments.
            note this resource may not even actually exist.
        """

    def createDirectory(childName):
        """Creates a new folder named childName under this folder.

        @raises ivfs.VFSError: if the node already exists.
        @raises ivfs.NotAContainerError: if this node isn't a container
        @raises ivfs.NotFoundError: if this node does not exist
        """

    def createFile(childName, exclusive=True):
        """Creates a new file named childName under this folder.

        @raises ivfs.VFSError: if the node already exists and is a container or
            if exclusive is True (the default) and the node already exists 
            and is a leaf
        @raises ivfs.NotAContainerError: if this node isn't a container
        @raises ivfs.NotFoundError: if this node does not exist
        """

    def isdir():
        """
        @returns: a Deferred which will fire with True is this node
            is a container or False otherwise

        @raises ivfs.NotFoundError: if this node does not exist
        """

    def isfile():
        """
        @returns: a Deferred which will fire with True is this node
            is a leaf or False otherwise

        @raises ivfs.NotFoundError: if this node does not exist
        """

    def exists():
        """
        @returns: a Deferred which will callback with True if this node exists
            or False otherwise
        """

