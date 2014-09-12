# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.cred import portal
from twisted.python import components, log, win32
from zope import interface
from ssh import session, forwarding, filetransfer
from ssh.filetransfer import FXF_READ, FXF_WRITE, FXF_APPEND, FXF_CREAT, FXF_TRUNC, FXF_EXCL
from twisted.conch.ls import lsLine

from avatar import ConchUser
from interfaces import ISession, ISFTPServer, ISFTPFile

import os, posixpath

# TODO: forwarding support

class WindowsSSHRealm:

    interface.implements(portal.IRealm)

    def requestAvatar(self, username, mind, *interfaces):
        user = WindowsConchUser(username)
        return interfaces[0], user, user.logout


class WindowsConchUser(ConchUser):

    def __init__(self, username):
        ConchUser.__init__(self)
        self.username = username
        self.listeners = {}  # dict mapping (interface, port) -> listener
        self.channelLookup.update({"session": session.SSHSession})
        self.subsystemLookup.update({"sftp": filetransfer.FileTransferServer})

    def getHomeDir(self):
        basepath = os.path.expanduser("~")
        path = os.path.splitdrive(basepath)[1]    # remove drive spec.
        unixpath = path.replace('\\','/')+"/"
        return posixpath.abspath(unixpath)

    def logout(self):
        # remove all listeners
        for listener in self.listeners.itervalues():
            self._runAsUser(listener.stopListening)
        log.msg('avatar %s logging out (%i)' % (self.username, len(self.listeners)))

    def _runAsUser(self, f, *args, **kw):
        try:
            f = iter(f)
        except TypeError:
            f = [(f, args, kw)]
        for i in f:
            func = i[0]
            args = len(i)>1 and i[1] or ()
            kw = len(i)>2 and i[2] or {}
            r = func(*args, **kw)
        return r


class SSHSessionForWindowsConchUser:

    interface.implements(ISession)

    def __init__(self, avatar):
        self.avatar = avatar

    def openShell(self, proto):
        proto.transport.write = self._writeHack
        self.avatar.conn.transport.transport.setTcpNoDelay(1)

    def execCommand(self, proto, cmd):
        self.avatar.conn.transport.transport.setTcpNoDelay(1)

    def eofReceived(self):
        pass

    def closed(self):
        log.msg('shell closed')

    def windowChanged(self, winSize):
        self.winSize = winSize


class SFTPServerForWindowsConchUser:

    interface.implements(ISFTPServer)

    def __init__(self, avatar):
        self.avatar = avatar

    def _setAttrs(self, path, attrs):
        """
        NOTE: this function assumes it runs as the logged-in user:
        i.e. under _runAsUser()
        """
        if "permissions" in attrs:
            os.chmod(path, attrs["permissions"])
        if "atime" in attrs and "mtime" in attrs:
            os.utime(path, (attrs["atime"], attrs["mtime"]))

    def _getAttrs(self, s):
        return {
            "size"          : s.st_size,
            "uid"           : s.st_uid,
            "gid"           : s.st_gid,
            "permissions"   : s.st_mode,
            "atime"         : int(s.st_atime),
            "mtime"         : int(s.st_mtime)
        }

    def _absPath(self, path):
        home = self.avatar.getHomeDir()
        return posixpath.abspath(posixpath.join(home, path))

    def gotVersion(self, otherVersion, extData):
        return {}

    def openFile(self, filename, flags, attrs):
        return WindowsSFTPFile(self, self._absPath(filename), flags, attrs)

    def removeFile(self, filename):
        filename = self._absPath(filename)
        return self.avatar._runAsUser(os.remove, filename)

    def renameFile(self, oldpath, newpath):
        oldpath = self._absPath(oldpath)
        newpath = self._absPath(newpath)
        return self.avatar._runAsUser(os.rename, oldpath, newpath)

    def makeDirectory(self, path, attrs):
        path = self._absPath(path)
        return self.avatar._runAsUser([(os.mkdir, (path,)),
                                (self._setAttrs, (path, attrs))])

    def removeDirectory(self, path):
        path = self._absPath(path)
        self.avatar._runAsUser(os.rmdir, path)

    def openDirectory(self, path):
        return WindowsSFTPDirectory(self, self._absPath(path))

    def getAttrs(self, path, followLinks):
        path = self._absPath(path)
        if followLinks:
            s = self.avatar._runAsUser(os.stat, path)
        else:
            s = self.avatar._runAsUser(os.lstat, path)
        return self._getAttrs(s)

    def setAttrs(self, path, attrs):
        path = self._absPath(path)
        self.avatar._runAsUser(self._setAttrs, path, attrs)

    def readLink(self, path):
        raise NotImplementedError

    def makeLink(self, linkPath, targetPath):
        raise NotImplementedError

    def realPath(self, path):
        return posixpath.realpath(self._absPath(path))

    def extendedRequest(self, extName, extData):
        raise NotImplementedError


class WindowsSFTPFile:

    interface.implements(ISFTPFile)

    def __init__(self, server, filename, flags, attrs):
        self.server = server
        openFlags = 0
        if flags & FXF_READ == FXF_READ and flags & FXF_WRITE == 0:
            openFlags = os.O_RDONLY
        if flags & FXF_WRITE == FXF_WRITE and flags & FXF_READ == 0:
            openFlags = os.O_WRONLY
        if flags & FXF_WRITE == FXF_WRITE and flags & FXF_READ == FXF_READ:
            openFlags = os.O_RDWR
        if flags & FXF_APPEND == FXF_APPEND:
            openFlags |= os.O_APPEND
        if flags & FXF_CREAT == FXF_CREAT:
            openFlags |= os.O_CREAT
        if flags & FXF_TRUNC == FXF_TRUNC:
            openFlags |= os.O_TRUNC
        if flags & FXF_EXCL == FXF_EXCL:
            openFlags |= os.O_EXCL
        if "permissions" in attrs:
            mode = attrs["permissions"]
            del attrs["permissions"]
        else:
            mode = 0777
        openFlags |= win32.O_BINARY
        fd = server.avatar._runAsUser(os.open, filename, openFlags, mode)
        if attrs:
            server.avatar._runAsUser(server._setAttrs, filename, attrs)
        self.fd = fd

    def close(self):
        return self.server.avatar._runAsUser(os.close, self.fd)

    def readChunk(self, offset, length):
        return self.server.avatar._runAsUser([ (os.lseek, (self.fd, offset, 0)),
                                            (os.read, (self.fd, length)) ])

    def writeChunk(self, offset, data):
        return self.server.avatar._runAsUser([ (os.lseek, (self.fd, offset, 0)),
                                            (os.write, (self.fd, data)) ])

    def getAttrs(self):
        s = self.server.avatar._runAsUser(os.fstat, self.fd)
        return self.server._getAttrs(s)

    def setAttrs(self, attrs):
        raise NotImplementedError


class WindowsSFTPDirectory:

    def __init__(self, server, directory):
        self.server = server
        self.files = server.avatar._runAsUser(os.listdir, directory)
        self.dir_ = directory

    def __iter__(self):
        return self

    def next(self):
        try:
            f = self.files.pop(0)
        except IndexError:
            raise StopIteration
        else:
            s = self.server.avatar._runAsUser(os.lstat, posixpath.join(self.dir_, f))
            longname = lsLine(f, s)
            attrs = self.server._getAttrs(s)
            return (f, longname, attrs)

    def close(self):
        self.files = []


components.registerAdapter(SFTPServerForWindowsConchUser, WindowsConchUser, filetransfer.ISFTPServer)
#components.registerAdapter(SSHSessionForWindowsConchUser, WindowsConchUser, session.ISession)

