# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Utility functions for dealing with POSIX file descriptors.

API Stability: stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
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
from main import CONNECTION_LOST, CONNECTION_DONE


def setNonBlocking(fd):
    """Make a fd non-blocking."""
    flags = fcntl.fcntl(fd, FCNTL.F_GETFL)
    flags = flags | os.O_NONBLOCK
    fcntl.fcntl(fd, FCNTL.F_SETFL, flags)


def setBlocking(fd):
    """Make a fd blocking."""
    flags = fcntl.fcntl(fd, FCNTL.F_GETFL)
    flags = flags & ~os.O_NONBLOCK
    fcntl.fcntl(fd, FCNTL.F_SETFL, flags)


def readFromFD(fd, callback):
    """Read from fd, calling callback with resulting data.

    Returns same thing FileDescriptor.doRead would.
    """
    try:
        output = os.read(fd, 8192)
    except (OSError, IOError), ioe:
        if ioe.args[0] == errno.EAGAIN:
            return
        else:
            return CONNECTION_LOST
    if not output:
        return CONNECTION_DONE
    callback(output)


__all__ = ["setNonBlocking", "readFromFD"]
