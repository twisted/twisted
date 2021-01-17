# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
# -*- test-case-name: twisted.internet.test.test_async -*-
"""
This module contains asynchronous filesystem interfaces and reference implementations
"""

from zope.interface import Interface, implementer
from twisted.internet import reactor
from twisted.internet.threads import deferToThreadPool
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure
from twisted.logger import Logger
import os
import os.path
import platform

log = Logger()


class IAsyncFilesystem(Interface):

    """
    an asynchronous filesystem
    based closely on L{twisted.conch.interfaces.ISFTPServer}
    """

    def openFile(filename, flags, attrs):
        """
        Called when the clients asks to open a file.

        @param filename: a string representing the file to open.

        @param flags: an integer of the flags to open the file with, ORed
        together.  The flags and their values are passed directly to L{os.open}

        @param attrs: a list of attributes to open the file with.  It is a
        dictionary, consisting of 0 or more keys.  The possible keys are::

            size: the size of the file in bytes
            uid: the user ID of the file as an integer
            gid: the group ID of the file as an integer
            permissions: the permissions of the file with as an integer.
            the bit representation of this field is defined by POSIX.
            atime: the access time of the file as seconds since the epoch.
            mtime: the modification time of the file as seconds since the epoch.
            ext_*: extended attributes.  The server is not required to
            understand this, but it may.

        NOTE: there is no way to indicate text or binary files.

        This method returns an object that meets the IFile interface.
        Alternatively, it can return a L{Deferred} that will be called back
        with the object.
        """

    def removeFile(filename):
        """
        Remove the given file.

        This method returns when the remove succeeds, or a Deferred that is
        called back when it succeeds.

        @param filename: the name of the file as a string.
        """

    def renameFile(oldpath, newpath):
        """
        Rename the given file.

        This method returns when the rename succeeds, or a L{Deferred} that is
        called back when it succeeds. If the rename fails, C{renameFile} will
        raise an implementation-dependent exception.

        @param oldpath: the current location of the file.
        @param newpath: the new file name.
        """

    def makeDirectory(path, attrs):
        """
        Make a directory.

        This method returns when the directory is created, or a Deferred that
        is called back when it is created.

        @param path: the name of the directory to create as a string.
        @param attrs: a dictionary of attributes to create the directory with.
        Its meaning is the same as the attrs in the L{openFile} method.
        """

    def removeDirectory(path):
        """
        Remove a directory (non-recursively)

        It is an error to remove a directory that has files or directories in
        it.

        This method returns when the directory is removed, or a Deferred that
        is called back when it is removed.

        @param path: the directory to remove.
        """

    def openDirectory(path):
        """
        Open a directory for scanning.

        B{NOTE:} this function differs from L{twisted.conch.interfaces.ISFTPServer}

        This method returns an iterable object that has a close() method,
        or a Deferred that is called back with same.

        The close() method is called when the client is finished reading
        from the directory.  At this point, the iterable will no longer
        be used.

        The iterable should return tuples of the form (filename,
        attrs) or Deferreds that return the same.  The
        sequence must support __getitem__, but otherwise may be any
        'sequence-like' object.

        attrs is a dictionary in the format of the attrs argument to openFile.

        @param path: the directory to open.
        """

    def getAttrs(path, followLinks):
        """
        Return the attributes for the given path.

        This method returns a dictionary in the same format as the attrs
        argument to openFile or a Deferred that is called back with same.

        @param path: the path to return attributes for as a string.
        @param followLinks: a boolean.  If it is True, follow symbolic links
        and return attributes for the real path at the base.  If it is False,
        return attributes for the specified path.
        """

    def setAttrs(path, attrs):
        """
        Set the attributes for the path.

        This method returns when the attributes are set or a Deferred that is
        called back when they are.

        @param path: the path to set attributes for as a string.
        @param attrs: a dictionary in the same format as the attrs argument to
        L{openFile}.
        """

    def readLink(path):
        """
        Find the root of a set of symbolic links.

        This method returns the target of the link, or a Deferred that
        returns the same.

        @param path: the path of the symlink to read.
        """

    def makeLink(linkPath, targetPath):
        """
        Create a symbolic link.

        This method returns when the link is made, or a Deferred that
        returns the same.

        @param linkPath: the pathname of the symlink as a string.
        @param targetPath: the path of the target of the link as a string.
        """

    def realPath(path):
        """
        Convert any path to an absolute path.

        This method returns the absolute path as a string, or a Deferred
        that returns the same.

        @param path: the path to convert as a string.
        """

    def unregister():
        """
        release system resources
        """

    def statfs():
        """
        @return: a Deferred returning a dictionary with these keys, all optional
         - C{size} size of a block, in bytes (int)
         - C{blocks} size of filesystem in blocks  (int)
         - C{free} free blocks (int)
         - C{disk_id} 32-bit integer disk ID  (int)
         - C{disk_namemax} maximum path length (int)
         - C{disk_label} disk/volume label (str)
         - C{disk_fstype} filesystem type (str)
         - C{disk_birthtime} disk/volume creation time (int)

        @rtype: L{dict}
        """


class IFile(Interface):
    """
    This represents an open file on the server.  An object adhering to this
    interface should be returned from L{openFile}().
    """

    def close():
        """
        Close the file.

        This method returns nothing if the close succeeds immediately, or a
        Deferred that is called back when the close succeeds.
        """

    def readChunk(offset, length):
        """
        Read from the file.

        If EOF is reached before any data is read, raise EOFError.

        This method returns the data as L{bytes}, or a Deferred that is
        called back with same.

        @param offset: an integer that is the index to start from in the file.
        @param length: the maximum length of data to return.  The actual amount
        returned may less than this.  For normal disk files, however,
        this should read the requested number (up to the end of the file).
        """

    def writeChunk(offset, data):
        """
        Write to the file.

        This method returns when the write completes, or a Deferred that is
        called when it completes.

        @param offset: an integer that is the index to start from in the file.
        @param data: a L{bytes} that is the data to write.

        @return: number of bytes written
        @rtype: L{int}
        """

    def getAttrs():
        """
        Return the attributes for the file.

        This method returns a dictionary in the same format as the attrs
        argument to L{openFile} or a L{Deferred} that is called back with same.
        """

    def setAttrs(attrs):
        """
        Set the attributes for the file.

        This method returns when the attributes are set or a Deferred that is
        called back when they are.

        @param attrs: a dictionary in the same format as the attrs argument to
        L{openFile}.
        """

    def fileno():
        """
        @return: the underlying file descriptor
        @rtype: L{int)
        """


class AccessViolation(Exception):
    """thrown when a caller tries to break access restrictions"""


@implementer(IFile)
class _ThreadFile:
    """
    a file accessed asynchronously using threads. Should only be created
    by L{ThreadVfs.openFile}
    """

    def __init__(self, fso, filename, flags, attrs):
        """
        @param fso: the parent filesystem object
        @type fso: L{IFilesystem}
        @param filename: the path to open
        @type filename: L{str}
        @param flags: opening flags, passed to L{os.open}
        @type flags: L{int}
        @param attrs: a dictionary in the same format as the attrs argument to
        L{openFile}.
        @type attrs: L{dict}
        """
        self.fso = fso
        if attrs is None:
            attrs = {}
        if "permissions" in attrs and not self.fso.read_only:
            mode = attrs["permissions"]
            del attrs["permissions"]
        else:
            mode = 0o644
        if self.fso.read_only:
            flags = os.O_RDONLY
        elif flags == 0:
            flags = os.O_RDWR
        fd = os.open(filename, flags, mode)
        if attrs and not self.fso.read_only:
            self.fso._setAttrs(filename, attrs)
        self.fd = fd

    def fileno(self):
        return self.fd

    def close(self):
        return self.fso._deferToThread(os.close, self.fd)

    def readChunk(self, offset, length):
        def int_read():
            os.lseek(self.fd, offset, 0)
            return os.read(self.fd, length)

        return self.fso._deferToThread(int_read)

    def writeChunk(self, offset, data):
        if self.fso.read_only:
            raise AccessViolation()

        def int_write():
            os.lseek(self.fd, offset, 0)
            return os.write(self.fd, data)

        return self.fso._deferToThread(int_write)

    def getAttrs(self):
        s = self.fso._deferToThread(os.stat, self.fd)
        s.addCallback(self.fso._getAttrs)
        return s

    def setAttrs(self, attrs):
        if self.fso.read_only:
            raise AccessViolation()
        return self.fso._deferToThread(self.fso._setAttrs, self.fd, attrs)

    def flush(self):
        if self.fso.read_only:
            raise AccessViolation()
        return self.fso._deferToThread(os.fsync, self.fd)


@implementer(IAsyncFilesystem)
class ThreadFs:
    """
    An async filesystem implemented using threads

    This implementation cribbed from
    L{twisted.conch.unix.SFTPServerForUnixConchUser}

    However unlike conch we don't have per-user processes so more of our own security.
    """

    def __init__(self, root, threadpool=None, read_only=False):
        """
        @param root: the base directory
        @type root: L{str}

        @param threadpool: the threadpool to use, default the reactor's threadpool
        @type threadpool: L{twisted.python.threadpool.ThreadPool}

        @param read_only: if C{True}, changes to filesystem forbidden
        @type read_only: C{bool}
        """
        self.root = root
        self.read_only = read_only
        if threadpool:
            self.threadpool = threadpool
        else:
            self.threadpool = reactor.getThreadPool()

    def unregister(self):
        pass

    def _setAttrs(self, path, attrs):
        if "uid" in attrs and "gid" in attrs:
            os.chown(path, attrs["uid"], attrs["gid"])
        if "permissions" in attrs:
            os.chmod(path, attrs["permissions"])
        if "atime" in attrs and "mtime" in attrs:
            os.utime(path, (attrs["atime"], attrs["mtime"]))
        return True

    def _getAttrs(self, s):
        d = {
            "size": s.st_size,
            "uid": s.st_uid,
            "gid": s.st_gid,
            "permissions": s.st_mode,
            "atime": int(s.st_atime),
            "mtime": int(s.st_mtime),
            "ext_ctime": int(s.st_ctime),
            "ext_nlinks": s.st_nlink,
        }
        try:
            d["ext_blksize"] = s.st_blksize
        except AttributeError:
            # not available on all platforms
            pass
        try:
            if s.st_birthtime:
                d["ext_birthtime"] = s.st_birthtime
        except AttributeError:
            # not available on all platforms
            pass
        return d

    def _absPath(self, path):
        p = os.path.normpath(os.path.join(self.root, path))
        if not p.startswith(self.root):
            raise AccessViolation()
        return p

    def _deferToThread(self, f, *args, **kwargs):
        return deferToThreadPool(reactor, self.threadpool, f, *args, **kwargs)

    def openFile(self, filename, flags=0, attrs=None):
        return self._deferToThread(
            _ThreadFile, self, self._absPath(filename), flags, attrs
        )

    def removeFile(self, filename):
        if self.read_only:
            raise AccessViolation()
        filename = self._absPath(filename)
        return self._deferToThread(os.remove, filename)

    def renameFile(self, oldpath, newpath):
        if self.read_only:
            raise AccessViolation()
        oldpath = self._absPath(oldpath)
        newpath = self._absPath(newpath)
        return self._deferToThread(os.rename, oldpath, newpath)

    def makeDirectory(self, path, attrs=None):
        def int_mkdir():
            if self.read_only:
                raise AccessViolation()
            path2 = self._absPath(path)
            os.mkdir(path2)
            if attrs:
                self._setAttrs(path2, attrs)

        return self._deferToThread(int_mkdir)

    def removeDirectory(self, path):
        if self.read_only:
            raise AccessViolation()
        path = self._absPath(path)
        return self._deferToThread(os.rmdir, path)

    def openDirectory(self, path):
        def int_opendir():
            path2 = self._absPath(path)
            return ((i.name, self._getAttrs(i.stat())) for i in os.scandir(path2))

        return self._deferToThread(int_opendir)

    def getAttrs(self, path, followLinks=True):
        path = self._absPath(path)
        if followLinks:
            s = self._deferToThread(os.stat, path)
        else:
            s = self._deferToThread(os.lstat, path)
        s.addCallback(self._getAttrs)
        return s

    def setAttrs(self, path, attrs):
        if self.read_only:
            raise AccessViolation()
        path = self._absPath(path)
        return self._deferToThread(self._setAttrs, path, attrs)

    def readLink(self, path):
        path = self._absPath(path)
        return self._deferToThread(os.readlink, path)

    def makeLink(self, linkPath, targetPath):
        if self.read_only:
            raise AccessViolation()
        linkPath = self._absPath(linkPath)
        targetPath = self._absPath(targetPath)
        return self._deferToThread(os.symlink, targetPath, linkPath)

    def realPath(self, path):
        return self._deferToThread(os.path.realpath, self._absPath(path))

    def statfs(self):
        def cb_statfs():
            try:
                v = os.statvfs(self.root)
                s = os.stat(self.root)
            except AttributeError:
                # some systems dont have at all
                return None
            d = dict(
                size=v.f_frsize,
                blocks=v.f_blocks,
                free=v.f_bavail,
                disk_namemax=v.f_namemax,
            )
            try:
                d["disk_id"] = v.f_fsid % 2 ** 32
            except AttributeError:
                pass  # only python 3.7+
            try:
                d["disk_fstype"] = s.st_fstype
            except AttributeError:
                pass  # only Solaris
            try:
                if s.st_birthtime:
                    d["disk_birthtime"] = s.st_birthtime
            except AttributeError:
                # classically, only BSDs (?and Darwin)
                # with statx, linux with glibc >= 2.28 also
                pass
            return d

        return self._deferToThread(cb_statfs)
