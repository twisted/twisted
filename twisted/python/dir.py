# -*- test-case-name: twisted.test.test_dir -*-
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

"""Fine-grained file listing

This module provides functions for incrementally retrieving the contents of a
directory, as well as for examining some information related to each content.
"""

from twisted.python._c_dir import *

def isDirectory((name, type)):
    """Determine whether a given (filename, filetype) refer to a directory.
    """
    return type == DIR

def isCharDevice((name, type)):
    """Determine whether a given (filename, filetype) refer to a character device.
    """
    return type == CHR

def isBlockDevice((name, type)):
    """Determine whether a given (filename, filetype) refer to a block device.
    """
    return type == BLK

def isFifo((name, type)):
    """Determine whether a given (filename, filetype) refer to a fifo.
    """
    return type == FIFO

def isRegularFile((name, type)):
    """Determine whether a given (filename, filetype) refer to a regular file.
    """
    return type == REG

def isSymbolicLink((name, type)):
    """Determine whether a given (filename, filetype) refer to a symlink.
    """
    return type == LNK

def isSocket((name, type)):
    """Determine whether a given (filename, filetype) refer to a socket.
    """
    return type == SOCK

def isWhiteout((name, type)):
    """Determine whether a given (filename, filetype) refer to a whiteout.
    """
    return type == WHT
