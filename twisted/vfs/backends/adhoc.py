"""Ad-hoc backend for VFS."""

from zope.interface import implements

from twisted.vfs import ivfs

class AdhocDirectory:
    """Ad-hoc directory.

    Can contain arbitrary other directories (but not files) as children.
    """

    implements(ivfs.IFileSystemContainer)

    def __init__(self, children={}, name=None, parent=None):
        if not parent : self.parent = self
        else : self.parent = parent
        self.name = name
        self._children = children

    def children(self):
        return [ ('.', self), ('..', self.parent) ] + [
            ( childName, self.child(childName) )
            for childName in self._children.keys() ]

    def child(self, childName):
        return self._children[childName]

    def getMetadata(self):
        return {}

    def exists(self, childName):
        return self._children.has_key(childName)

    def putChild(self, name, node):
        node.parent = self
        self._children[name] = node

