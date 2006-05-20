# Copyright (c) 2001-2006 Twisted Matrix Laboratories.
# See LICENSE for details.

"""In-memory VFS backend."""

import cStringIO

from zope.interface import implements

from twisted.vfs import ivfs, pathutils

__all__ = ['FakeDirectory', 'FakeFile']

class _FakeNode:
    """Base class.  Don't instantiate directly."""
    def create(self):
        self.parent._children[self.name] = self

    def remove(self):
        del self.parent._children[self.name]

    def rename(self, newName):
        newParent = pathutils.fetch(pathutils.getRoot(self),
                                    pathutils.dirname(newName))
        if newParent.exists(pathutils.basename(newName)):
            raise ivfs.VFSError(
                "Cannot rename over the top of an existing directory")
            
        del self.parent._children[self.name]
        self.name = pathutils.basename(pathutils.basename(newName))
        newParent._children[self.name] = self
        self.parent = newParent


class FakeDirectory(_FakeNode):
    """In-memory directory."""

    implements(ivfs.IFileSystemContainer)

    def __init__(self, name=None, parent=None, children=None):
        self.name = name
        children = children or {}
        if not parent:
            self.parent = self
        else:
            self.parent = parent
        self._children = children

    def children( self ) :
        implicit =  [('.', self), ('..', self.parent)]
        others = [(childName, self.child(childName))
                  for childName in self._children.keys() ]
        return implicit + others

    def child(self, childName):
        try:
            return self._children[childName]
        except KeyError:
            raise ivfs.NotFoundError(childName)

    def getMetadata(self):
        return {
        }

    def createFile(self, childName, exclusive=False):
        if exclusive and self.exists(childName):
            raise ivfs.AlreadyExistsError(childName)
        child = FakeFile(childName, self)
        child.create()
        return child

    def createDirectory(self, childName):
        if self.exists(childName):
            raise ivfs.AlreadyExistsError(childName)
        child = FakeDirectory(childName, self)
        child.create()
        return child

    def exists(self, childName):
        return self._children.has_key(childName)


class FakeFile(_FakeNode):
    """In-memory file."""

    implements(ivfs.IFileSystemLeaf)

    def __init__(self, name=None, parent=None, data=''):
        self.data = cStringIO.StringIO()
        self.data.write(data)
        self.parent = parent
        self.name = name

    def open(self, flags):
        return self

    def getMetadata(self):
        size = len(self.data.getvalue())
        self.data.seek(0)
        return {
            'size': size
        }

    def readChunk(self, offset, length):
        self.data.seek(offset)
        return self.data.read(length)

    def writeChunk(self, offset, data):
        self.data.seek(offset)
        self.data.write(data)

    def close(self):
        pass

    def children(self):
        print "this might break and if it does we should fix the caller"
        return []


