"""In-memory VFS backend."""

import cStringIO
from zope.interface import implements
from twisted.vfs import ivfs, pathutils, decorator
from twisted.internet import defer

__all__ = ['InMemNode']

class InMemNodeSync(object):
    def __init__(self, segments=[], filesystem={}):
        self.segments = segments
        self.filesystem = filesystem

    def child(self, *segments):
        return InMemNodeSync(self.segments + list(segments), self.filesystem)

    def parent(self):
        if len(self.segments):
            return InMemNodeSync(self.segments[:-1], self.filesystem)
        return self

    def path(self):
        return self.segments

    def _getNode(self):
        try:
            curr = self.filesystem
            for segment in self.segments:
                curr = curr[segment]   
            return curr
        except KeyError:
            raise ivfs.NotFoundError("%s not found" % self)

    def children(self):
        try:
            return [(name, self.child(name)) for name in self._getNode().keys()]
        except AttributeError:
            raise ivfs.NotAContainerError(
                "%s doesn't implement children" % self)
            
    def isdir(self):
        return isinstance(self._getNode(), type({}))

    def isfile(self):
        return not isinstance(self._getNode(), type({}))
            
    def exists(self):
        try:
            self._getNode()
            return True
        except ivfs.NotFoundError:
            return False

    def createDirectory(self, name):
        node = self._getNode()
        if not self.isdir():
            raise ivfs.NotAContainerError(
                "%s doesn't implement createDirectory" % self)
        if node.has_key(name):
            raise ivfs.VFSError(
                "%s can't create %s - node already exists" % (
                    self, name))
        node[name] = {}

    def createFile(self, name, exclusive=True):
        node = self._getNode()
        if not self.isdir():
            raise ivfs.NotAContainerError(
                "%s doesn't implement createDirectory" % self)
        if node.has_key(name):
            raise ivfs.VFSError(
                "%s can't create %s - node already exists" % (
                    self, name))
        node[name] = ''

    def remove(self):
        if not len(self.segments):
            raise ivfs.PermissionError(
                "%s can't move root node" % self)
        if self.isdir() and len(self._getNode()):
            raise ivfs.VFSError(
                "%s cannot remove non-empty directory" % self)
        parentNode = self.parent()._getNode()
        del parentNode[self.segments[-1]]

    def rename(self, segments):
        targetParent = InMemNodeSync(segments[:-1], self.filesystem)
        if not targetParent.exists(): 
            raise ivfs.VFSError(
                "%s target parent does not exist" % targetParent)
        if not targetParent.isdir():
            raise ivfs.VFSError(
                "%s target parent is not a container" % targetParent)
        targetFile = targetParent.child(segments[-1])
        if targetFile.exists():
            if targetFile.isdir():
                raise ivfs.VFSError(
                    "%s rename can't clobber containers" % targetFile)
        targetParent._getNode()[segments[-1]] = self._getNode()
        del self.parent()._getNode()[self.segments[-1]]

    def __str__(self):
        return "inmem node: /%s" % "/".join(self.segments)
        
def InMemNode(*args, **kwargs):
    return decorator.CommonWrapperDecorator(
        InMemNodeSync(*args, **kwargs),
        factoryMethods = ['child'],
        wrapper = defer.execute,
        wrappedMethods = decorator.introspectMethods(
            InMemNodeSync,
            exceptMethods = ['child', 'parent', 'path']),
        wrapStyle = decorator.IndirectWrap)
    






#XXX - old inmem, getting axed soon, just here for reference


class _FakeNode:
    """Base class.  Don't instantiate directly."""
    def create(self):
        self.parent._children[self.name] = self

    def remove(self):
        del self.parent._children[self.name]

    def rename(self, newName):
        del self.parent._children[self.name]
        newParent = pathutils.fetch(pathutils.getRoot(self),
                                    pathutils.dirname(newName))
##         newParent = self.filesystem.fetch(self.filesystem.dirname(newName))
        if newParent.exists(pathutils.basename(newName)):
            raise ivfs.VFSError(
                "Cannot rename over the top of an existing directory")
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
        return self._children[childName]

    def getMetadata(self):
        return {
        }

    def createFile(self, childName, exclusive=False):
        if exclusive and self.exists(childName):
            raise ivfs.VFSError("%r already exists" % (childName,))
        child = FakeFile(childName, self)
        child.create()
        return child

    def createDirectory(self, childName):
        if self.exists(childName):
            raise ivfs.VFSError("%r already exists" % (childName,))
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
        return []

