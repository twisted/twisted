# -*- test-case-name: twisted.test.test_fdesc -*-

# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Utility functions for dealing with POSIX file descriptors.
"""

import sys
import os
import errno
import fcntl
if (sys.hexversion >> 16) >= 0x202:
    FCNTL = fcntl
else:
    import FCNTL

# twisted imports
from twisted.internet.main import CONNECTION_LOST, CONNECTION_DONE


def setNonBlocking(fd):
    """
    Make a file descriptor non-blocking.
    """
    flags = fcntl.fcntl(fd, FCNTL.F_GETFL)
    flags = flags | os.O_NONBLOCK
    fcntl.fcntl(fd, FCNTL.F_SETFL, flags)


def setBlocking(fd):
    """
    Make a file descriptor blocking.
    """
    flags = fcntl.fcntl(fd, FCNTL.F_GETFL)
    flags = flags & ~os.O_NONBLOCK
    fcntl.fcntl(fd, FCNTL.F_SETFL, flags)


def readFromFD(fd, callback):
    """
    Read from file descriptor, calling callback with resulting data.

    Returns same thing FileDescriptor.doRead would.

    @type fd: C{int}
    @param fd: non-blocking file descriptor to be read from.
    @param callback: a callable which accepts a single argument. If
    data is read from the file descriptor it will be called with this
    data. Handling exceptions from calling the callback is up to the
    caller.

    Note that if the descriptor is still connected but no data is read,
    None will be returned but callback will not be called.

    @return: CONNECTION_LOST on error, CONNECTION_DONE when fd is
    closed, otherwise None.
    """
    try:
        output = os.read(fd, 8192)
    except (OSError, IOError), ioe:
        if ioe.args[0] in (errno.EAGAIN, errno.EINTR):
            return
        else:
            return CONNECTION_LOST
    if not output:
        return CONNECTION_DONE
    callback(output)

def writeToFD(fd, data):
    """
    Write data to file descriptor.

    Returns same thing FileDescriptor.writeSomeData would.

    @type fd: C{int}
    @param fd: non-blocking file descriptor to be written to.
    @type data: C{str} or C{buffer}
    @param data: bytes to write to fd.

    @return: number of bytes written, or CONNECTION_LOST.
    """
    try:
        return os.write(fd, data)
    except (OSError, IOError), io:
        if io.errno in (errno.EAGAIN, errno.EINTR):
            return 0
        return CONNECTION_LOST


__all__ = ["setNonBlocking", "setBlocking", "readFromFD", "writeToFD"]
