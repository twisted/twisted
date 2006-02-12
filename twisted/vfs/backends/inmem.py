"""In-memory VFS backend."""

import cStringIO
from zope.interface import implements
from twisted.vfs import ivfs, pathutils
from twisted.internet import defer

__all__ = ['InMemNode']

class InMemNode(object):
    implements(ivfs.IFileSystemNode)
    def __init__(self, segments=[], filesystem={}):
        self.segments = segments
        self.filesystem = filesystem

    def child(self, *segments):
        return InMemNode(self.segments + list(segments), self.filesystem)

    def parent(self):
        if len(self.segments):
            return InMemNode(self.segments[:-1], self.filesystem)
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
            return None

    def remove(self):
        if not len(self.segments):
            return defer.fail(ivfs.PermissionError(
                "%s can't move root node" % self))
        def _go(isdir):
            if isdir and len(self._getNode()):
                return defer.fail(ivfs.VFSError(
                    "%s cannot remove non-empty directory" % self))
            parentNode = self.parent()._getNode()
            del parentNode[self.segments[-1]]
            return defer.succeed(None)
        return self.isdir().addCallback(_go)

    def rename(self, segments):
        node = self._getNode()
        if node is None: 
            return defer.fail(ivfs.NotFoundError("%s not found" % self))

        targetParent = InMemNode(segments[:-1], self.filesystem)

        def _checkParentIsDir(isdir):
            if not isdir:
                return defer.fail(ivfs.VFSError(
                    "%s target parent is not a container" % targetParent))

            targetFile = targetParent.child(segments[-1])

            def _checkTargetExists(exists):
                def _doRename():



                def _checkTargetIsFile(isfile):
                    if not isfile:
                        return defer.fail(ivfs.VFSError(
                            "%s rename can't clobber containers" % targetFile))
                    return _doRename()
                if exists:
                    return targetFile.isfile().addCallback(_checkTargetIsFile)
                return _doRename()

            return targetFile.exists().addCallback(_checkTargetExists)

        return targetParent.isdir().addCallback(_checkParentIsDir)



targetParent._getNode()[segments[-1]] = node
del self.parent()._getNode()[self.segments[-1]]
return defer.succeed(None)        




        

    def children(self):
        node = self._getNode()
        if node is None: 
            return defer.fail(ivfs.NotFoundError("%s not found" % self))
        try:
            return defer.succeed(
                [(name, self.child(name)) for name in node.keys()])
        except AttributeError:
            return defer.fail(ivfs.NotAContainerError(
                "%s doesn't implement children" % self))
            
    def isdir(self):
        node = self._getNode()
        if node is None: 
            return defer.fail(ivfs.NotFoundError(
                "%s not found" % self))
        return defer.succeed(isinstance(node, type({})))

    def isfile(self):
        node = self._getNode()
        if node is None: 
            return defer.fail(ivfs.NotFoundError(
                "%s not found" % self))
        return defer.succeed(not isinstance(node, type({})))
            
    def exists(self):
        return (self._getNode() is None
            ) and defer.succeed(False) or defer.succeed(True)

    def createDirectory(self, name):
        node = self._getNode()
        if node is None: 
            return defer.fail(ivfs.NotFoundError(
                "%s not found" % self))
        try:
            if node.has_key(name):
                return defer.fail(ivfs.VFSError(
                    "%s can't create %s - node already exists" % (
                        self, name)))
            node[name] = {}
        except AttributeError:
            return defer.fail(ivfs.NotAContainerError(
                "%s doesn't implement createDirectory" % self))
        return defer.succeed(None)

    def createFile(self, name, exclusive=True):
        node = self._getNode()
        if node is None: 
            return defer.fail(ivfs.NotFoundError(
                "%s not found" % self))
        def _go(isfile):
            try:
                if node.has_key(name) and (exclusive or isfile):
                    return defer.fail(ivfs.VFSError(
                        "%s can't create %s - node already exists" % (
                            self, name)))
                node[name] = ''
            except AttributeError:
                return defer.fail(ivfs.NotAContainerError(
                    "%s doesn't implement createDirectory" % self))
            return defer.succeed(None)
        return self.isfile().addCallback(_go)

    def __str__(self):
        return "inmem node: /%s" % "/".join(self.segments)
        




        

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
        print "this might break and if it does we should fix the caller"
        return []


