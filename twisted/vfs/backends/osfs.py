# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""Filesystem backend for VFS."""

import os
import os.path
import errno

from twisted.vfs import ivfs

from zope.interface import implements

__all__ = ['OSDirectory', 'OSFile', 'RunWithPrivSep', 'SetUIDProxy',
           'ForceCreateModeProxy']

class OSNode:

    implements(ivfs.IFileSystemNode)

    def __init__(self, realPath, name=None, parent=None):

        self.name = name
        self.realPath = realPath

        if not parent: self.parent = self
        else: self.parent = parent

    def getMetadata(self):
        s = os.stat(self.realPath)
        return {
            "size"         : s.st_size,
            "uid"          : s.st_uid,
            "gid"          : s.st_gid,
            "permissions"  : s.st_mode,
            "atime"        : s.st_atime,
            "mtime"        : s.st_mtime,
            "nlink"        : s.st_nlink
        }

    def setMetadata(self, attrs):
        if 'uid' in attrs and 'gid' in attrs:
            os.chown(self.realPath, attrs["uid"], attrs["gid"])
        if 'permissions' in attrs:
            os.chmod(self.realPath, attrs["permissions"])
        if 'atime' in attrs or 'mtime' in attrs:
            if None in (attrs.get("atime"), attrs.get("mtime")):
                st = os.stat(self.realPath)
                atime = attrs.get("atime", st.st_atime)
                mtime = attrs.get("mtime", st.st_mtime)
            else:
                atime = attrs['atime']
                mtime = attrs['mtime']
            os.utime(self.realPath, (atime, mtime))

    def rename(self, newName):
        """
        Rename this node to C{newName}.

        @param newName: A valid filename for the current directory.
        @raise AlreadyExistsError: If C{newName} is a directory which already
            exists.
        """
        from twisted.vfs import pathutils
        newParent = pathutils.fetch(pathutils.getRoot(self),
                                    pathutils.dirname(newName))
        # XXX spiv 2005-12-15
        # assumes newParent is also an OSDirectory.  Probably should politely
        # decline (rather than break with an undefined error) if it's not.
        newPath = os.path.join(newParent.realPath, pathutils.basename(newName))
        try:
            os.rename(self.realPath, newPath)
        except OSError, e:
            if e.errno in (errno.EISDIR, errno.ENOTEMPTY, errno.EEXIST):
                raise ivfs.AlreadyExistsError(
                    "Can't rename %s to %s: %s already exists"
                    % (self.realPath, newPath, newPath))
            else:
                raise
        self.realPath = newPath
        self.name = newName
        self.parent = newParent

    def remove(self):
        raise NotImplementedError("Override me.")


class OSFile(OSNode):

    implements(ivfs.IFileSystemLeaf)

    def create(self, exclusive=True):
        flags = os.O_WRONLY | os.O_CREAT
        if exclusive:
            flags |= os.O_EXCL
        try:
            fd = os.open(self.realPath, flags)
        except OSError, e:
            if e.errno == errno.EEXIST:
                raise ivfs.AlreadyExistsError(self.name)

            # Something unexpected happened.  Let it propagate.
            raise
        f = os.fdopen(fd, "w")
        f.close()

    def open(self, flags):
        self.fd = os.open(self.realPath, flags)
        return self

    def readChunk(self, offset, length):
        os.lseek(self.fd, offset, 0)
        return os.read(self.fd, length)

    def writeChunk(self, offset, data):
        os.lseek(self.fd, offset, 0)
        return os.write(self.fd, data)

    def close(self):
        os.close(self.fd)

    def remove(self):
        os.remove(self.realPath)



class OSDirectory(OSNode):

    implements(ivfs.IFileSystemContainer)

    def children(self):
        """See IFileSystemContainer."""
        return ([('.', self), ('..', self.parent)] +
                [(childName, self.child(childName))
                 for childName in os.listdir(self.realPath)])

    def child(self, childName):
        """See IFileSystemContainer."""
        fullPath = os.path.join(self.realPath, childName)

        if not os.path.exists(fullPath):
            raise ivfs.NotFoundError(childName)

        if os.path.isdir(fullPath):
            nodeFactory = self.childDirFactory()
        else:
            nodeFactory = self.childFileFactory()

        return nodeFactory(fullPath, childName, self)

    def childDirFactory(cls):
        """Returns a callable that will be used to construct instances for
        subdirectories of this OSDirectory.  The callable should accept the same
        interface as OSDirectory.__init__; i.e. take three args (path, name,
        parent), and return an IFileSystemContainer.

        By default, this will be the class of the child's parent.  Override this
        method if you want a different behaviour.
        """
        # If you subclass OSDirectory, this will ensure children of OSDirectory
        # are also your subclass.
        return cls
    childDirFactory = classmethod(childDirFactory)

    def childFileFactory(self):
        """Returns a callable that will be used to construct instances for files
        in this OSDirectory.  The callable should accept the same interface as
        OSFile.__init__; i.e. take three args (path, name, parent), and return
        an IFileSystemLeaf.

        By default, this will be OSFile.  Override this method if you want a
        different behaviour.
        """
        return OSFile

    def createDirectory(self, childName):
        """See IFileSystemContainer."""
        child = self.childDirFactory()(os.path.join(self.realPath, childName),
                                       childName, self)
        child.create()
        return child

    def createFile(self, childName, exclusive=True):
        """See IFileSystemContainer."""
        child = self.childFileFactory()(os.path.join(self.realPath, childName),
                                        childName, self)
        child.create(exclusive=exclusive)
        return child

    def create(self):
        os.mkdir(self.realPath)

    def remove(self):
        os.rmdir(self.realPath)

    def exists(self, childName):
        """See IFileSystemContainer."""
        return os.path.exists(os.path.join(self.realPath, childName))


class WrapFunc:
    def __init__(self, func, wrapper):
        self.func = func
        self.wrapper = wrapper
    def __call__(self, *args, **kwargs):
        return self.wrapper(self.func(*args, **kwargs))

class _OSNodeProxy:
    def __init__(self, target):
        self.target = target
    def __getattr__(self, name):
        attr =  getattr(self.target, name)
        if name in ['child', 'createDirectory', 'createFile']:
            attr = WrapFunc(attr, self._wrapChild)
        return attr
    def _wrapChild(self, child):
        return _OSNodeProxy(child)


class RunWithPrivSep:
    def __init__(self, func, euid, egid):
        self.func = func
        self.euid = euid
        self.egid = egid

    def __call__(self, *args, **kwargs):
        cureuid = os.geteuid()
        curegid = os.getegid()

        os.setegid(0)
        os.seteuid(0)
        os.setegid(self.egid)
        os.seteuid(self.euid)

        try:
            result = self.func(*args, **kwargs)
        finally:
            os.setegid(0)
            os.seteuid(0)
            os.setegid(cureuid)
            os.seteuid(curegid)
        return result


class SetUIDProxy(_OSNodeProxy):
    def __init__(self, target, euid, egid):
        self.target = target
        self.euid   = euid
        self.egid   = egid

    def __getattr__(self, attrName):
        attr = _OSNodeProxy.__getattr__(self, attrName)
        if callable(attr):
            return RunWithPrivSep(attr, self.euid, self.egid)
        return attr

    def _wrapChild(self, child):
        return SetUIDProxy(child, self.euid, self.egid)


def getMode(mode):
    if type(mode) is str:
        mode = int(mode, 8)
    assert type(mode) is int, 'invalid mode: %s' % mode
    return mode


class ForceCreateModeProxy(_OSNodeProxy):
    def __init__(self, target, dirmode=None, filemode=None):
        self.target = target
        self.dirmode = None
        self.filemode = None
        if dirmode != None:
            self.dirmode = getMode(dirmode)
        if filemode != None:
            self.filemode = getMode(filemode)

    def createDirectory(self, *args, **kwargs):
        child = self.target.createDirectory(*args, **kwargs)
        if self.dirmode != None:
            os.chmod(child.realPath, self.dirmode)
        return self._wrapChild(child)

    def createFile(self, *args, **kwargs):
        child = self.target.createFile(*args, **kwargs)
        if self.filemode != None:
            os.chmod(child.realPath, self.filemode)
        return self._wrapChild(child)

    def _wrapChild(self, child):
        return ForceCreateModeProxy(child, self.dirmode, self.filemode)


