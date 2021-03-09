# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
# -*- test-case-name: twisted.internet.test.test_async -*-
"""
This module contains asynchronous filesystem interfaces and reference implementations
"""

from zope.interface import Interface, Attribute, implementer
from twisted.internet import reactor
from twisted.internet.interfaces import (
    IPushProducer,
    IProducer,
    IConsumer,
)
from twisted.python.threadpool import ThreadPool
from twisted.internet.threads import (
    deferToThreadPool,
    blockingCallFromThread,
)
from twisted.internet.defer import Deferred
from twisted.logger import Logger
from typing import Tuple, Iterable, Optional, Callable, cast, Any
import os
import os.path
import threading

log = Logger()


DEFAULT_BUFFER_MAX = 2 ** 12  # four megabytes
DEFAULT_CHUNK_SIZE = 4096


class IAsyncFilesystem(Interface):

    """
    an asynchronous filesystem
    based closely on L{twisted.conch.interfaces.ISFTPServer}
    """

    def openFile(
        filename: str, flags: int = 0, attrs: Optional[dict] = None
    ) -> "Deferred":
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

    def removeFile(filename: str) -> "Deferred":
        """
        Remove the given file.

        This method returns a Deferred that is
        called back when it succeeds.

        @param filename: the name of the file as a string.
        """

    def renameFile(oldpath: str, newpath: str) -> "Deferred":
        """
        Rename the given file.

        This method returns when the rename succeeds, or a L{Deferred} that is
        called back when it succeeds. If the rename fails, C{renameFile} will
        raise an implementation-dependent exception.

        @param oldpath: the current location of the file.
        @param newpath: the new file name.
        """

    def makeDirectory(path: str, attrs: Optional[dict] = None) -> "Deferred":
        """
        Make a directory.

        This method returns when the directory is created, or a Deferred that
        is called back when it is created.

        @param path: the name of the directory to create as a string.
        @param attrs: a dictionary of attributes to create the directory with.
        Its meaning is the same as the attrs in the L{openFile} method.
        """

    def removeDirectory(path: str) -> "Deferred":
        """
        Remove a directory (non-recursively)

        It is an error to remove a directory that has files or directories in
        it.

        This method returns when the directory is removed, or a Deferred that
        is called back when it is removed.

        @param path: the directory to remove.
        """

    def openDirectory(path: str) -> "Deferred":
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

    def getAttrs(path: str, followLinks: bool) -> "Deferred":
        """
        Return the attributes for the given path.

        This method returns a dictionary in the same format as the attrs
        argument to openFile or a Deferred that is called back with same.

        @param path: the path to return attributes for as a string.
        @param followLinks: a boolean.  If it is True, follow symbolic links
        and return attributes for the real path at the base.  If it is False,
        return attributes for the specified path.
        """

    def setAttrs(path: str, attrs: dict) -> "Deferred":
        """
        Set the attributes for the path.

        This method returns when the attributes are set or a Deferred that is
        called back when they are.

        @param path: the path to set attributes for as a string.
        @param attrs: a dictionary in the same format as the attrs argument to
        L{openFile}.
        """

    def readLink(path: str) -> "Deferred":
        """
        Find the root of a set of symbolic links.

        This method returns the target of the link, or a Deferred that
        returns the same.

        @param path: the path of the symlink to read.
        """

    def makeLink(linkPath: str, targetPath: str) -> "Deferred":
        """
        Create a symbolic link.

        This method returns when the link is made, or a Deferred that
        returns the same.

        @param linkPath: the pathname of the symlink as a string.
        @param targetPath: the path of the target of the link as a string.
        """

    def realPath(path: str) -> "Deferred":
        """
        Convert any path to an absolute path.

        This method returns the absolute path as a string, or a Deferred
        that returns the same.

        @param path: the path to convert as a string.
        """

    def unregister() -> None:
        """
        release system resources
        """

    def statfs() -> "Deferred":
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
    This represents an open file on the filesystem.  An object adhering to this
    interface should be returned from L{openFile}().
    """

    def close() -> "Deferred":
        """
        Close the file.

        This method returns nothing if the close succeeds immediately, or a
        Deferred that is called back when the close succeeds.
        """

    def readChunk(offset: int, length: int) -> "Deferred":
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

    def writeChunk(offset: int, data: bytes) -> "Deferred":
        """
        Write to the file.

        This method returns when the write completes, or a Deferred that is
        called when it completes.

        @param offset: an integer that is the index to start from in the file.
        @param data: a L{bytes} that is the data to write.

        @return: number of bytes written
        @rtype: L{int}
        """

    def getAttrs() -> "Deferred":
        """
        Return the attributes for the file.

        This method returns a dictionary in the same format as the attrs
        argument to L{openFile} or a L{Deferred} that is called back with same.
        """

    def setAttrs(attrs: dict) -> "Deferred":
        """
        Set the attributes for the file.

        This method returns when the attributes are set or a Deferred that is
        called back when they are.

        @param attrs: a dictionary in the same format as the attrs argument to
        L{openFile}.
        """

    def fileno() -> int:
        """
        @return: the underlying file descriptor
        @rtype: L{int)
        """

    def send(
        consumer: "IConsumer", start: int = 0, chunkSize: int = DEFAULT_CHUNK_SIZE
    ) -> "Deferred":
        """
        Produce the contents of the file to the given consumer.

        @type consumer: C{IConsumer}
        @param start: offset to begin reading from
        @param chunkSize: size, in bytes, of each read
        @return: A Deferred which fires when the file has been
        consumed completely.

        adapted from L{twisted.protocols.ftp.IReadFile}
        """

    producer = Attribute("a read-only IPushProducer object available during send()")

    def receive(append: bool = False) -> "IConsumer":
        """
        @param append: True if append to end of file
        @return: A C{IConsumer} which is used to write data

        adapted from L{twisted.protocols.ftp.IWriteFile}
        """


class AccessViolation(Exception):
    """thrown when a caller tries to break access restrictions"""


@implementer(IFile)
class _ThreadFile:
    """
    a file accessed asynchronously using threads. Should only be created
    by L{ThreadVfs.openFile}
    """

    def __init__(
        self, fso: "ThreadFs", filename: str, flags: int, attrs: Optional[dict]
    ) -> None:
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
        self._write_consumer: Optional["_ThreadFileConsumer"] = None
        self._producer = _ThreadFileProducer()
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

    def fileno(self) -> int:
        return self.fd

    def close(self) -> "Deferred":
        if self._write_consumer:
            self._write_consumer.close()
            d = self._write_consumer.write_deferred
            d.addCallback(lambda _: self.fso._deferToThread(os.close, self.fd))
            return d
        else:
            return self.fso._deferToThread(os.close, self.fd)

    def readChunk(self, offset: int, length: int) -> "Deferred":
        def int_read() -> bytes:
            os.lseek(self.fd, offset, 0)
            return os.read(self.fd, length)

        return self.fso._deferToThread(int_read)

    def writeChunk(self, offset: int, data: bytes) -> "Deferred":
        if self.fso.read_only:
            raise AccessViolation()

        def int_write() -> int:
            os.lseek(self.fd, offset, 0)
            return os.write(self.fd, data)

        return self.fso._deferToThread(int_write)

    def getAttrs(self) -> "Deferred":
        s = self.fso._deferToThread(os.stat, self.fd)
        s.addCallback(self.fso._getAttrs)
        return s

    def setAttrs(self, attrs: dict) -> "Deferred":
        if self.fso.read_only:
            raise AccessViolation()
        return self.fso._deferToThread(self.fso._setAttrs, self.fd, attrs)

    def flush(self) -> "Deferred":
        if self.fso.read_only:
            raise AccessViolation()
        return self.fso._deferToThread(os.fsync, self.fd)

    def send(
        self, consumer: "IConsumer", start: int = 0, chunkSize: int = DEFAULT_CHUNK_SIZE
    ) -> "Deferred":
        self._producer.stop_flag = False
        self._producer.event.set()

        def int_read_loop() -> None:
            os.lseek(self.fd, start, 0)
            while True:
                buf = os.read(self.fd, chunkSize)
                if buf:
                    blockingCallFromThread(reactor, consumer.write, buf)
                if len(buf) < chunkSize or self._producer.stop_flag:
                    break
                self._producer.event.wait()

        return self.fso._deferToThread(int_read_loop)

    @property
    def producer(self) -> "_ThreadFileProducer":
        return self._producer

    def receive(
        self, append: bool = False, buffer_max: int = DEFAULT_BUFFER_MAX
    ) -> "IConsumer":
        if self.fso.read_only:
            raise AccessViolation()
        self._write_consumer = _ThreadFileConsumer(self, append, buffer_max)
        return self._write_consumer


@implementer(IPushProducer)
class _ThreadFileProducer:
    def __init__(self) -> None:
        self.stop_flag = False
        self.event = threading.Event()

    def stopProducing(self) -> None:
        self.stop_flag = True

    def pauseProducing(self) -> None:
        self.event.clear()

    def resumeProducing(self) -> None:
        self.event.set()


@implementer(IConsumer)
class _ThreadFileConsumer:
    def __init__(
        self, thread_file: "_ThreadFile", append: bool, buffer_max: int
    ) -> None:
        self.producer: Optional["IProducer"] = None
        self.streaming = False
        self.lock = threading.Lock()
        self.event = threading.Event()
        self._paused = False
        self._buffer = bytearray()
        self.fso = thread_file.fso
        self.write_deferred = self.fso._deferToThread(
            self._consumer_write_thread, append
        )
        self.fd = thread_file.fileno()
        self.buffer_max = buffer_max
        self._closed = False

    def registerProducer(self, producer: "IProducer", streaming: bool) -> None:
        assert self.producer is None
        self.producer = producer
        self.streaming = streaming
        self._paused = False

    def unregisterProducer(self) -> None:
        assert self.producer
        if self.streaming and not self._paused:
            cast("IPushProducer", self.producer).pauseProducing()
            self._paused = True
        self.producer = None

    def write(self, data: bytes) -> None:
        with self.lock:
            self._buffer += data
            self.event.set()
        if (
            self.producer
            and self.streaming
            and (not self._paused)
            and len(self._buffer) > self.buffer_max
        ):
            cast("IPushProducer", self.producer).pauseProducing()
            self._paused = True

    def close(self) -> None:
        with self.lock:
            self._closed = True
            self.event.set()
        if self.producer and self.streaming and (not self._paused):
            cast("IPushProducer", self.producer).pauseProducing()
            self._paused = True

    def _consumer_write_thread(self, append: bool) -> None:
        os.lseek(self.fd, 0, os.SEEK_END if append else os.SEEK_SET)
        while True:
            with self.lock:
                buf = bytes(self._buffer)
                self._buffer = bytearray()
                if len(buf) == 0:
                    self.event.clear()
            if len(buf) == 0:
                if self._closed:
                    break
                if self.producer and (
                    (self.streaming and self._paused) or (not self.streaming)
                ):
                    self._paused = False
                    blockingCallFromThread(
                        reactor, cast("IPushProducer", self.producer).resumeProducing
                    )
                self.event.wait()
            else:
                os.write(self.fd, buf)


@implementer(IAsyncFilesystem)
class ThreadFs:
    """
    An async filesystem implemented using threads

    This implementation cribbed from
    L{twisted.conch.unix.SFTPServerForUnixConchUser}

    However unlike conch we don't have per-user processes so more of our own security.
    """

    def __init__(
        self,
        root: str,
        threadpool: Optional["ThreadPool"] = None,
        read_only: bool = False,
    ) -> None:
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
            self.threadpool = reactor.getThreadPool()  # type: ignore

    def unregister(self) -> None:
        pass

    def _setAttrs(self, path: str, attrs: dict) -> bool:
        if "uid" in attrs and "gid" in attrs:
            os.chown(path, attrs["uid"], attrs["gid"])
        if "permissions" in attrs:
            os.chmod(path, attrs["permissions"])
        if "atime" in attrs and "mtime" in attrs:
            os.utime(path, (attrs["atime"], attrs["mtime"]))
        return True

    def _getAttrs(self, s: os.stat_result) -> dict:
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

    def _absPath(self, path: str) -> str:
        p = os.path.normpath(os.path.join(self.root, path))
        if not p.startswith(self.root):
            raise AccessViolation()
        return p

    def _deferToThread(self, f: Callable, *args: Any, **kwargs: Any) -> "Deferred":
        return cast(
            "Deferred", deferToThreadPool(reactor, self.threadpool, f, *args, **kwargs)
        )

    def openFile(
        self, filename: str, flags: int = 0, attrs: Optional[dict] = None
    ) -> "Deferred":
        return self._deferToThread(
            _ThreadFile, self, self._absPath(filename), flags, attrs
        )

    def removeFile(self, filename: str) -> "Deferred":
        if self.read_only:
            raise AccessViolation()
        filename = self._absPath(filename)
        return self._deferToThread(os.remove, filename)

    def renameFile(self, oldpath: str, newpath: str) -> "Deferred":
        if self.read_only:
            raise AccessViolation()
        oldpath = self._absPath(oldpath)
        newpath = self._absPath(newpath)
        return self._deferToThread(os.rename, oldpath, newpath)

    def makeDirectory(self, path: str, attrs: Optional[dict] = None) -> "Deferred":
        def int_mkdir() -> None:
            if self.read_only:
                raise AccessViolation()
            path2 = self._absPath(path)
            os.mkdir(path2)
            if attrs:
                self._setAttrs(path2, attrs)

        return self._deferToThread(int_mkdir)

    def removeDirectory(self, path: str) -> "Deferred":
        if self.read_only:
            raise AccessViolation()
        path = self._absPath(path)
        return self._deferToThread(os.rmdir, path)

    def openDirectory(self, path: str) -> "Deferred":
        def int_opendir() -> Iterable[Tuple[str, dict]]:
            path2 = self._absPath(path)
            return ((i.name, self._getAttrs(i.stat())) for i in os.scandir(path2))

        return self._deferToThread(int_opendir)

    def getAttrs(self, path: str, followLinks: bool = True) -> "Deferred":
        path = self._absPath(path)
        if followLinks:
            s = self._deferToThread(os.stat, path)
        else:
            s = self._deferToThread(os.lstat, path)
        s.addCallback(self._getAttrs)
        return s

    def setAttrs(self, path: str, attrs: dict) -> "Deferred":
        if self.read_only:
            raise AccessViolation()
        path = self._absPath(path)
        return self._deferToThread(self._setAttrs, path, attrs)

    def readLink(self, path: str) -> "Deferred":
        path = self._absPath(path)
        return self._deferToThread(os.readlink, path)

    def makeLink(self, linkPath: str, targetPath: str) -> "Deferred":
        if self.read_only:
            raise AccessViolation()
        linkPath = self._absPath(linkPath)
        targetPath = self._absPath(targetPath)
        return self._deferToThread(os.symlink, targetPath, linkPath)

    def realPath(self, path: str) -> "Deferred":
        return self._deferToThread(os.path.realpath, self._absPath(path))

    def statfs(self) -> "Deferred":
        def cb_statfs() -> dict:
            try:
                v = os.statvfs(self.root)
                s = os.stat(self.root)
            except AttributeError:
                # some systems dont have at all
                return {}
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
                d["disk_fstype"] = s.st_fstype  # type: ignore
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
