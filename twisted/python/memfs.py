# -*- test-case-name: twisted.python.test.test_memfs -*-

"""
An in-memory implementation of various filesystem APIs.

This can be used to force code that uses Python's built-in file I/O APIs to
write to an in-memory data structure.  For easier inspection and testing, this
structure preserves numerous details about the state of stream buffers,
filesystem buffers, and hypothetical disk contents.
"""

import os
import errno
from array import array

# Seek from beginning of file.
SEEK_SET = 0
# Seek from current position.
SEEK_CUR = 1
# Seek from end of file.
SEEK_END = 2


class MemoryFile(object):
    """
    An in-memory implementation of part of the Python file API.

    This is similar to L{StringIO}, in that it implements a file-like object.
    However, unlike L{StringIO}, it implements a file that participates in a
    filesystem; you can close this file, then re-open it via its
    L{POSIXFilesystem}.  In addition, L{MemoryFile} goes considerably further
    to implement stdio's buffering and POSIX's filesystem synchronization
    semantics, so you can tell what the same operations would have done on a
    filesystem.

    @ivar closed: A boolean indicating whether this file has been closed yet.

    @type closed: C{bool}

    @ivar _filesystem: A reference to an instance of a class like
        L{POSIXFilesystem} which defines filesystem behavior which isn't
        localized to a single file.

    @ivar _fd: An C{int} giving this file's descriptor number.

    @ivar _fpos: An C{int} giving the current position of this file.

    @ivar _streamBuffer: An array giving the data which has been written to this
        file but not yet flushed to the underlying descriptor.

    @ivar _dirty: A list of two-tuples giving offsets and lengths of slices of
        C{_streamBuffer} which are dirty and must be written to the underlying file
        descriptor when a flush occurs.

    @ivar _filesystemState: A L{_POSIXFilesystemFileState} instance giving the
        low-level storage state for this file.
    """

    def __init__(self, filesystem, fd, filesystemState):
        self._filesystem = filesystem
        self._fd = fd
        self._fpos = 0
        self._streamBuffer = array('c')
        self._dirty = []
        self._filesystemState = filesystemState


    def _isClosed(self):
        """
        Is this file descriptor closed?
        """
        return self._fd not in self._filesystem.byDescriptor

    closed = property(_isClosed, doc=_isClosed.__doc__)


    def _checkClosed(self):
        """
        Raise L{ValueError} if the file is closed.
        """
        if self.closed:
            raise ValueError("I/O operation on closed MemoryFile")


    def fileno(self):
        """
        Return the integer file descriptor for this file object.
        """
        self._checkClosed()
        return self._fd


    def close(self):
        """
        Flush the I{application-level} buffer and invalidate this file object
        for further operations.
        """
        if self.closed:
            return
        self.flush()
        del self._filesystem.byDescriptor[self._fd]


    def tell(self):
        """
        Return the current file position pointer for this file.
        """
        self._checkClosed()
        return self._fpos


    def seek(self, offset, whence=SEEK_SET):
        """
        Change the current file position pointer.
        """
        self.flush()
        if whence == SEEK_SET:
            self._fpos = offset
        elif whence == SEEK_CUR:
            self._fpos += offset
        elif whence == SEEK_END:
            self._fpos = self._filesystemState.size() + offset


    def write(self, bytes):
        """
        Add the given bytes to an I{application-level} buffer.
        """
        self._checkClosed()
        padding = self._fpos - len(self._streamBuffer)
        if padding > 0:
            self._streamBuffer.extend('\0' * padding)
        self._streamBuffer[self._fpos:self._fpos + len(bytes)] = array('c', bytes)
        self._dirty.append((self._fpos, self._fpos + len(bytes)))
        self._fpos += len(bytes)


    def read(self, size=None):
        """
        Read some bytes from the file at the current position.
        """
        self._checkClosed()
        end = None
        if size is not None and size >= 0:
            end = self._fpos + size
        data = self._filesystemState.fsBuffer.tostring()[self._fpos:end]
        self._fpos += len(data)
        return data


    def flush(self):
        """
        Flush any bytes in the I{application-level} buffer into the
        I{filesystem-level} buffer.
        """
        self._checkClosed()
        # If any exceptions are thrown below, we actually want to discard the
        # buffer; this is what the real flush() implementation effectively
        # does.
        streamBuffer = self._streamBuffer
        dirty = self._dirty
        self._streamBuffer = array('c')
        self._dirty = []
        for (start, end) in dirty:
            self._filesystemState.pwrite(start, streamBuffer[start:end])


    def _fsync(self):
        """
        Flush the underlying filesystem state for this file to the object
        representing the underlying hardware device.
        """
        self._filesystemState.fsync()



class _POSIXFilesystemFileState(object):
    """
    Represent the state of one file.

    @ivar fsBuffer: An L{array} representing the contents of this file as known
        by the filesystem, potentially representing changes which only exist in
        memory so far.

    @ivar device: An L{array} representing the contents of this file as known
        by a hypothetical hardware storage device, i.e. a hard disk.

    @ivar fs: The L{POSIXFilesystem} that this L{_POSIXFilesystemFileState} is
        a part of.
    """
    def __init__(self, fs):
        self.fsBuffer = array('c')
        self.device = array('c')
        self.fs = fs


    def size(self):
        """
        Return the size of this file.
        """
        # Not directly tested, but MemoryFile seek tests require this to work
        # right.
        return len(self.fsBuffer)


    def fsync(self):
        """
        Flush all data in C{fsBuffer} to C{device}.
        """
        # Unfortunately, I don't have any idea how to verify this fake
        # implementation of fsync(2).  In fact, this probably isn't even a very
        # realistic fsync(2) implementation, since it actually synchronizes the
        # filesystem cache with the underlying device, which real fsync(2)
        # implementations aren't well-known for doing. -exarkun
        self.device = self.fsBuffer[:]


    def pwrite(self, pos, bytes):
        """
        Write some data to this file.  This data goes to C{fsBuffer} until it
        C{fsync} is called.
        """
        # Not directly unit tested, but the MemoryFile tests definitely depend on
        # this working correctly.  It might be nice to add direct unit tests
        # for this code, anyway.
        if self.fs.full:
            raise IOError(errno.ENOSPC, os.strerror(errno.ENOSPC))
        padding = pos - len(self.fsBuffer)
        if padding > 0:
            self.fsBuffer.extend('\0' * padding)
        self.fsBuffer[pos:pos + len(bytes)] = bytes


    def truncate(self, pos):
        """
        Truncate the buffer to the given length.
        """
        del self.fsBuffer[pos:]



class POSIXFilesystem(object):
    """
    An in-memory implementation of a filesystem.

    @ivar byName: C{dict} mapping filenames to L{MemoryFile} instances.

    @ivar byDescriptor: C{dict} mapping integer file descriptors to open
        L{MemoryFile} instances.

    @ivar full: A boolean indicating whether to reject writing data to the
        filesystem with an ENOSPC error.  Normally C{False}.  Set to C{True} if
        you want this filesystem to behave as though it's full.
    """

    def __init__(self):
        self.full = False
        self.byName = {}
        self.byDescriptor = {}


    _fdCounter = 3
    def _descriptorCounter(self):
        self._fdCounter += 1
        return self._fdCounter


    def open(self, name, mode='r'):
        """
        Implement a copy of the Python builtin "open" to behave in a way which
        allows inspection of the resulting state without touching the actual
        filesystem.

        @return: an in-memory file connected to this filesystem.

        @rtype: L{MemoryFile}
        """
        if mode[-1:] == 'b':
            style = 'binary'
            mode = mode[:-1]
        else:
            style = 'text'
            if mode[-1:] == 't':
                mode = mode[:-1]
        if mode not in ('r', 'w', 'r+', 'w+', 'a', 'a+'):
            raise Exception("Illegal mode %r" % (mode,))
        if 'r' in mode:
            if name not in self.byName:
                raise Exception("No such file %r" % (name,))

        descriptor = self._descriptorCounter()
        if name not in self.byName:
            self.byName[name] = _POSIXFilesystemFileState(self)
        fsState = self.byName[name]
        if 'w' in mode:
            fsState.truncate(0)
        fObj = MemoryFile(self, descriptor, fsState)
        self.byDescriptor[descriptor] = fObj
        if 'a' in mode:
            fObj.seek(0, SEEK_END)
        return fObj


    def willLoseData(self):
        """
        Will the application using this filesystem lose any data that it has
        written to it at this point in execution, in the event of power-loss,
        device removal, or network disconnection?  Possible causes include
        writing data to a file and not flush()ing it, and flush()ing a file
        without sync()ing it.

        @return: L{True} if the application might lose data, L{False} if all
        the buffers have been properly synchronized.

        @rtype: L{bool}
        """
        for memFile in self.byDescriptor.itervalues():
            if memFile._streamBuffer:
                return True
        for fsState in self.byName.itervalues():
            if fsState.fsBuffer != fsState.device:
                return True
        return False


    def fsync(self, fd):
        """
        Flush any data known by the filesystem (but ignoring data known only by
        application buffers) to the object representing the underlying
        hardware.
        """
        if fd not in self.byDescriptor:
            raise OSError(errno.EBADF, None)
        self.byDescriptor[fd]._fsync()


    def rename(self, oldname, newname):
        """
        Change the name of a file.
        """
        self.byName[newname] = self.byName.pop(oldname)



