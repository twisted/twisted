# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


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
