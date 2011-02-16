# -*- test-case-name: twisted.vfs.test.test_sftp -*-

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import os, time

import zope.interface

from twisted.python import components, log, util
from twisted.conch.avatar import ConchUser
from twisted.conch.interfaces import ISession, ISFTPFile
from twisted.conch.ssh.filetransfer import ISFTPServer, FileTransferServer
from twisted.conch.ssh.filetransfer import FXF_READ, FXF_WRITE, FXF_APPEND, FXF_CREAT, FXF_TRUNC, FXF_EXCL
from twisted.conch.ssh.filetransfer import SFTPError
from twisted.conch.ssh.filetransfer import FX_PERMISSION_DENIED, FX_FAILURE
from twisted.conch.ssh.filetransfer import FX_NO_SUCH_FILE, FX_OP_UNSUPPORTED
from twisted.conch.ssh.filetransfer import FX_NOT_A_DIRECTORY
from twisted.conch.ssh.filetransfer import FX_FILE_IS_A_DIRECTORY
from twisted.conch.ssh.filetransfer import FX_FILE_ALREADY_EXISTS
from twisted.conch.ssh import session
from twisted.conch.ls import lsLine
from twisted.internet import defer

from twisted.vfs import ivfs, pathutils

def translateErrors(function):
    """Decorator that catches VFSErrors and re-raises them as the corresponding
    SFTPErrors."""

    def f(*args, **kwargs):
        try:
            result = function(*args, **kwargs)
            if isinstance(result, defer.Deferred):
                result.addErrback(_ebtranslateErrors)
            return result
        except ivfs.PermissionError, e:
            raise SFTPError(FX_PERMISSION_DENIED, str(e))
        except ivfs.NotFoundError, e:
            raise SFTPError(FX_NO_SUCH_FILE, e.args[0])
        except ivfs.AlreadyExistsError, e:
            raise SFTPError(FX_FILE_ALREADY_EXISTS, e.args[0])
        except ivfs.VFSError, e:
            raise SFTPError(FX_FAILURE, str(e))
        except NotImplementedError, e:
            raise SFTPError(FX_OP_UNSUPPORTED, str(e))

    util.mergeFunctionMetadata(function, f)
    return f


def _ebtranslateErrors(failure):
    """This just re-raises the failure so that the translateErrors decorator
    around this errback can intercept it if it wants to."""
    failure.raiseException()
_ebtranslateErrors = translateErrors(_ebtranslateErrors)


class AdaptFileSystemUserToISFTP:

    zope.interface.implements(ISFTPServer)

    def __init__(self, avatar):
        self.avatar = avatar
        self.openFiles = {}
        self.openDirs = {}
        self.filesystem = avatar.filesystem

    def _setAttrs(self, path, attrs):
        """
        NOTE: this function assumes it runs as the logged-in user:
        i.e. under _runAsUser()
        """
        if attrs.has_key("uid") and attrs.has_key("gid"):
            os.lchown(path, attrs["uid"], attrs["gid"])
        if attrs.has_key("permissions"):
            os.chmod(path, attrs["permissions"])
        if attrs.has_key("atime") and attrs.has_key("mtime"):
            os.utime(path, (attrs["atime"]. attrs["mtime"]))

    def gotVersion(self, otherVersion, extData):
        return {}

    def openFile(self, filename, flags, attrs):
        createPlease = False
        exclusive = False
        openFlags = 0
        if flags & FXF_READ == FXF_READ and flags & FXF_WRITE == 0:
            openFlags = os.O_RDONLY
        if flags & FXF_WRITE == FXF_WRITE and flags & FXF_READ == 0:
            createPlease = True
            openFlags = os.O_WRONLY
        if flags & FXF_WRITE == FXF_WRITE and flags & FXF_READ == FXF_READ:
            createPlease = True
            openFlags = os.O_RDWR
        if flags & FXF_APPEND == FXF_APPEND:
            createPlease = True
            openFlags |= os.O_APPEND
        if flags & FXF_CREAT == FXF_CREAT:
            createPlease = True
            openFlags |= os.O_CREAT
        if flags & FXF_TRUNC == FXF_TRUNC:
            openFlags |= os.O_TRUNC
        if flags & FXF_EXCL == FXF_EXCL:
            exclusive = True

        # XXX Once we change readChunk/writeChunk we'll have to wrap
        # child in something that implements those.

        pathSegments = self.filesystem.splitPath(filename)
        dirname, basename = pathSegments[:-1], pathSegments[-1]
        parentNode = self.filesystem.fetch('/'.join(dirname))
        if createPlease:
            child = parentNode.createFile(basename, exclusive)
        elif parentNode.exists(basename):
            child = parentNode.child(basename)
            if not ivfs.IFileSystemLeaf.providedBy(child):
                raise SFTPError(FX_FILE_IS_A_DIRECTORY, filename)
        else:
            raise SFTPError(FX_NO_SUCH_FILE, filename)
        child.open(openFlags)
        return AdaptFileSystemLeafToISFTPFile(child)
    openFile = translateErrors(openFile)

    def removeFile(self, filename):
        node = self.filesystem.fetch(filename)
        if not ivfs.IFileSystemLeaf.providedBy(node):
            raise SFTPError(FX_FILE_IS_A_DIRECTORY, filename)
        node.remove()
    removeFile = translateErrors(removeFile)

    def renameFile(self, oldpath, newpath):
        """
        Rename C{oldpath} to C{newpath}.

        See L{twisted.conch.interfaces.ISFTPServer.renameFile}.
        """
        old = self.filesystem.fetch(oldpath)
        old.rename(newpath)
    renameFile = translateErrors(renameFile)

    def makeDirectory(self, path, attrs):
        dirname  = self.filesystem.dirname(path)
        basename = self.filesystem.basename(path)
        return self.filesystem.fetch(dirname).createDirectory(basename)
    makeDirectory = translateErrors(makeDirectory)

    def removeDirectory(self, path):
        self.filesystem.fetch(path).remove()
    removeDirectory = translateErrors(removeDirectory)

    def openDirectory(self, path):
        directory = self.filesystem.fetch(path)
        if not ivfs.IFileSystemContainer.providedBy(directory):
            raise SFTPError(FX_NOT_A_DIRECTORY, path)
        class DirList:
            def __init__(self, iter):
                self.iter = iter
            def __iter__(self):
                return self

            def next(self):

                (name, attrs) = self.iter.next()

                class st:
                    pass

                s = st()
                s.st_mode   = attrs["permissions"]
                s.st_uid    = attrs["uid"]
                s.st_gid    = attrs["gid"]
                s.st_size   = attrs["size"]
                s.st_mtime  = attrs["mtime"]
                s.st_nlink  = attrs["nlink"]
                return ( name, lsLine(name, s), attrs )

            def close(self):
                return

        return DirList(
            iter([(name, _attrify(file))
                  for (name, file) in self.filesystem.fetch(path).children()]))
    openDirectory = translateErrors(openDirectory)

    def getAttrs(self, path, followLinks):
        node = self.filesystem.fetch(path)
        return _attrify(node)
    getAttrs = translateErrors(getAttrs)

    def setAttrs(self, path, attrs):
        node = self.filesystem.fetch(path)
        try:
            # XXX: setMetadata isn't yet part of the IFileSystemNode interface
            # (but it should be).  So we catch AttributeError, and translate it
            # to NotImplementedError because it's slightly nicer for clients.
            node.setMetadata(attrs)
        except AttributeError:
            raise NotImplementedError("NO SETATTR")
    setAttrs = translateErrors(setAttrs)

    def readLink(self, path):
        raise NotImplementedError("NO LINK")

    def makeLink(self, linkPath, targetPath):
        raise NotImplementedError("NO LINK")

    def realPath(self, path):
        return self.filesystem.absPath(path)


class AdaptFileSystemLeafToISFTPFile:
    zope.interface.implements(ISFTPFile)

    def __init__(self, original):
        self.original = original

    def close(self):
        return self.original.close()

    def readChunk(self, offset, length):
        return self.original.readChunk(offset, length)

    def writeChunk(self, offset, data):
        return self.original.writeChunk(offset, data)

    def getAttrs(self):
        return _attrify(self.original)

    def setAttrs(self, attrs):
        try:
            # XXX: setMetadata isn't yet part of the IFileSystemNode interface
            # (but it should be).  So we catch AttributeError, and translate it
            # to NotImplementedError because it's slightly nicer for clients.
            self.original.setMetadata(attrs)
        except AttributeError:
            raise NotImplementedError("NO SETATTR")


class VFSConchSession:
    zope.interface.implements(ISession)
    def __init__(self, avatar):
        self.avatar = avatar
    def openShell(self, proto):
        self.avatar.conn.transport.transport.loseConnection()
    def getPty(self, term, windowSize, modes):
        pass
    def closed(self):
        log.msg('shell closed')


class VFSConchUser(ConchUser):
    def __init__(self, username, root):
        ConchUser.__init__(self)
        self.username = username
        self.filesystem = pathutils.FileSystem(root)

        self.listeners = {}  # dict mapping (interface, port) -> listener
        self.channelLookup.update(
                {"session": session.SSHSession})
        self.subsystemLookup.update(
                {"sftp": FileTransferServer})

    def logout(self):
        # XXX - this may be broken
        log.msg('avatar %s logging out (%i)' % (self.username, len(self.listeners)))


def _attrify(node):
    meta = node.getMetadata()
    permissions = meta.get('permissions', None)
    if permissions is None:
        if ivfs.IFileSystemContainer.providedBy(node):
            permissions = 16877
        else:
            permissions = 33188

    return {'permissions': permissions,
            'size': meta.get('size', 0),
            'uid': meta.get('uid', 0),
            'gid': meta.get('gid', 0),
            'atime': meta.get('atime', time.time()),
            'mtime': meta.get('mtime', time.time()),
            'nlink': meta.get('nlink', 1)
            }



components.registerAdapter(AdaptFileSystemUserToISFTP, VFSConchUser, ISFTPServer)
components.registerAdapter(VFSConchSession, VFSConchUser, ISession)

