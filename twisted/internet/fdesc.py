# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

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
from main import CONNECTION_LOST


def setNonBlocking(fd):
    """Make a fd non-blocking."""
    flags = fcntl.fcntl(fd, FCNTL.F_GETFL)
    flags = flags | os.O_NONBLOCK
    fcntl.fcntl(fd, FCNTL.F_SETFL, flags)


def readFromFD(fd, callback):
    """Read from fd, calling callback with resulting data.

    Returns same thing FileDescriptor.doRead would.
    """
    try:
        output = os.read(fd, 8192)
    except IOError, ioe:
        if ioe.args[0] == errno.EAGAIN:
            return
        else:
            return CONNECTION_LOST
    if not output:
        return CONNECTION_LOST
    callback(output)


__all__ = ["setNonBlocking", "readFromFD"]
