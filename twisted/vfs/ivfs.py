# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Various interfaces and exceptions for vfs.
"""

from zope.interface import Interface, Attribute



class VFSError(Exception):
    """
    Base class for all VFS errors.
    """



class PermissionError(VFSError):
    """
    The user does not have permission to perform the requested operation.
    """



class NotFoundError(VFSError):
    """
    The file or directory does not exist.
    """



class AlreadyExistsError(VFSError):
    """
    The file or directory already exists.
    """



class IFileSystemNode(Interface):

    parent = Attribute(
        """parent node"""
    )

    def getMetadata():
        """
        Feturns a map of arbitrary metadata. As an example, here's what SFTP
        expects (but doesn't require):

            - C{'size'}: size of file in bytes
            - C{'uid'}: owner of the file
            - C{'gid'}: group owner of the file
            - C{'permissions'}: file permissions
            - C{'atime'}: last time the file was accessed
            - C{'mtime'}: last time the file was modified
            - C{'nlink'}: number of links to the file

        Protocols that need metadata should handle the case when a particular
        value isn't available as gracefully as possible.
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
        """
        Closes this node.
        """


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
        Returns a list of 2 element tuples [ ( path, nodeObject ) ]. The first
        two elements of the list are B{'.'} (the node itself), and B{'..'} (the
        node parent).
        """


    def child(childName):
        """
        Returns a node object for child C{childName}.

        @raises: NotFoundError if no child with that name exists.
        """


    def createDirectory(childName):
        """
        Creates a new folder named childName under this folder.
        An error is raised if the folder already exists.
        """


    def createFile(childName, exclusive=True):
        """
        Creates a new file named childName under this folder.

        If exclusive is True (the default), an L{AlreadyExistsError} is raised
        if the file already exists.
        """


    def exists(childName):
        """
        Returns C{True} if container has a child childName, C{False} otherwise.
        """

