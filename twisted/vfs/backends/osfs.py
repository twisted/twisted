"""Filesystem backend for VFS."""

import sys
import os
import os.path
import stat
import time

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


    def rename(self, newName):
        newName = os.path.join(os.path.dirname(self.realPath), newName)
        os.rename(self.realPath, newName)
        self.realPath = newName
        self.name = newName

    def remove(self):
        raise NotImplementedError("Override me.")


class OSFile(OSNode):

    implements(ivfs.IFileSystemLeaf)

    def create(self):
        f = open(self.realPath, "w")
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
        return ([('.', self), ('..', self.parent)] +
                [(childName, self.child(childName))
                 for childName in os.listdir(self.realPath)])

    def child(self, childName):

        fullPath = os.path.join(self.realPath, childName)

        if not os.path.exists(fullPath):
            raise ivfs.VFSError("path not found: %s" % childName)

        if os.path.isdir(fullPath): Node = OSDirectory
        else: Node = OSFile

        return Node(fullPath, childName, self)

    def createDirectory(self, childName):
        child = OSDirectory(os.path.join(self.realPath, childName), childName, self)
        child.create()
        return child

    def createFile(self, childName):
        child = OSFile(os.path.join(self.realPath, childName), childName, self)
        child.create()
        return child

    def create(self):
        os.mkdir(self.realPath)

    def remove(self):
        os.rmdir(self.realPath)

    def exists(self, childName):
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


