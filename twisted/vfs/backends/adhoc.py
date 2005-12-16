"""Ad-hoc backend for VFS."""

from zope.interface import implements

from twisted.vfs import ivfs

class AdhocDirectory:
    """Ad-hoc directory.

    Can contain arbitrary other directories (but not files) as children.
    """

    implements(ivfs.IFileSystemContainer)

    def __init__(self, children=None, name=None, parent=None):
        if not parent : self.parent = self
        else : self.parent = parent
        self.name = name
        if children is None:
            children = {}
        self._children = children

    def children(self):
        return [ ('.', self), ('..', self.parent) ] + [
            ( childName, self.child(childName) )
            for childName in self._children.keys() ]

    def child(self, childName):
        try:
            return self._children[childName]
        except KeyError:
            raise ivfs.NotFoundError(childName)

    def getMetadata(self):
        return {}

    def exists(self, childName):
        return self._children.has_key(childName)

    def putChild(self, name, node):
        node.parent = self
        self._children[name] = node

    def createDirectory(self, childName):
        # Users cannot add directories to an AdhocDirectory, so raise
        # PermissionError.
        raise ivfs.PermissionError()
    
    def createFile(self, childName, exclusive=True):
        # AdhocDirectories cannot contain files directly, so give permission
        # denied if someone tries to create one.
        raise ivfs.PermissionError()
        
