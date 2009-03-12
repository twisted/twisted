# -*- test-case-name: twisted.python.test.test_memfs -*-

"""
An in-memory implementation of various filesystem APIs.

This can be used to force code that uses Python's built-in file I/O APIs to
write to an in-memory data structure.  For easier inspection and testing, this
structure preserves numerous details about the state of stream buffers,
filesystem buffers, and hypothetical disk contents.
"""

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

    @ivar filesystem: A reference to an instance of a class like
        L{POSIXFilesystem} which defines filesystem behavior which isn't
        localized to a single file.

    @ivar fd: An C{int} giving this file's descriptor number.

    @ivar fpos: An C{int} giving the current position of this file.

    @ivar appBuffer: An array giving the data which has been written to this
        file but not yet flushed to the underlying descriptor.

    @ivar dirty: A list of two-tuples giving offsets and lengths of slices of
        C{appBuffer} which are dirty and must be written to the underlying file
        descriptor when a flush occurs.

    @ivar filesystemState: A L{_POSIXFilesystemFileState} instance giving the
        low-level storage state for this file.
    """

    def __init__(self, filesystem, fd, filesystemState):
        self.filesystem = filesystem
        self.fd = fd
        self.fpos = 0
        self.appBuffer = array('c')
        self.dirty = []
        self.filesystemState = filesystemState


    def _isClosed(self):
        """
        Is this file descriptor closed?
        """
        return self.fd not in self.filesystem.byDescriptor

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
        return self.fd


    def close(self):
        """
        Flush the I{application-level} buffer and invalidate this file object
        for further operations.
        """
        if self.closed:
            return
        self.flush()
        del self.filesystem.byDescriptor[self.fd]


    def tell(self):
        """
        Return the current file position pointer for this file.
        """
        self._checkClosed()
        return self.fpos


    def seek(self, offset, whence=SEEK_SET):
        """
        Change the current file position pointer.
        """
        self.flush()
        if whence == SEEK_SET:
            self.fpos = offset
        elif whence == SEEK_CUR:
            self.fpos += offset
        elif whence == SEEK_END:
            self.fpos = self.filesystemState.size() + offset


    def write(self, bytes):
        """
        Add the given bytes to an I{application-level} buffer.
        """
        self._checkClosed()
        padding = self.fpos - len(self.appBuffer)
        if padding > 0:
            self.appBuffer.extend('\0' * padding)
        self.appBuffer[self.fpos:self.fpos + len(bytes)] = array('c', bytes)
        self.dirty.append((self.fpos, self.fpos + len(bytes)))
        self.fpos += len(bytes)


    def read(self, size=None):
        """
        Read some bytes from the file at the current position.
        """
        self._checkClosed()
        end = None
        if size is not None and size >= 0:
            end = self.fpos + size
        return self.filesystemState.fsBuffer.tostring()[self.fpos:end]


    def flush(self):
        """
        Flush any bytes in the I{application-level} buffer into the
        I{filesystem-level} buffer.
        """
        self._checkClosed()
        for (start, end) in self.dirty:
            self.filesystemState.pwrite(start, self.appBuffer[start:end])
        self.appBuffer = array('c')
        self.dirty = []


    def _fsync(self):
        """
        Flush the underlying filesystem state for this file to the object
        representing the underlying hardware device.
        """
        self.filesystemState.fsync()



class _POSIXFilesystemFileState(object):
    """
    Represent the state of one file.

    @ivar fsBuffer: An L{array} representing the contents of this file as known
        by the filesystem, potentially representing changes which only exist in
        memory so far.

    @ivar device: An L{array} representing the contents of this file as known
        by a hypothetical hardware storage device, i.e. a hard disk.
    """
    def __init__(self):
        self.fsBuffer = array('c')
        self.device = array('c')


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
        padding = pos - len(self.fsBuffer)
        if padding > 0:
            self.fsBuffer.extend('\0' * padding)
        self.fsBuffer[pos:pos + len(bytes)] = bytes



class POSIXFilesystem(object):
    """
    An in-memory implementation of a filesystem.

    @ivar byName: C{dict} mapping filenames to L{MemoryFile} instances.
    @ivar byDescriptor: C{dict} mapping integer file descriptors to open
        L{MemoryFile} instances.
    """
    def __init__(self):
        self.byName = {}
        self.byDescriptor = {}


    _fdCounter = 3
    def _descriptorCounter(self):
        self._fdCounter += 1
        return self._fdCounter


    def open(self, name, mode='r'):
        """
        Implement a copy of the Python builtn "open" to behave in a way which
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
        if '+' in mode:
            if name in self.byName:
                raise Exception(
                    "Opening an existing file for reading is unsupported")

        descriptor = self._descriptorCounter()
        if name not in self.byName:
            self.byName[name] = _POSIXFilesystemFileState()
        fsState = self.byName[name]
        fObj = MemoryFile(self, descriptor, fsState)
        self.byDescriptor[descriptor] = fObj
        return fObj


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




