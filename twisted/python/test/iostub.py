# -*- test-case-name: twisted.python.test.test_memfs.PatchingTest -*-

"""
This module is a stub for test_memfs.  It imports various things
filesystem-related names and uses them to ensure that L{POSIXFilesystem} can
catch different styles of import.
"""

import os

from os import rename
from os import fsync


def writeWithOpen(filename, data):
    """
    Write some data to the given filename with the built-in 'open'.
    """
    f = open(filename, "w")
    f.write(data)
    f.close()



def writeWithFile(filename, data):
    """
    Write some data to the given filename with the built-in 'file'.
    """
    f = file(filename, "w")
    f.write(data)
    f.close()


def rename_moduleImport(filename1, filename2):
    """
    Rename a file using 'os.rename'.
    """
    os.rename(filename1, filename2)


def rename_functionImport(filename1, filename2):
    """
    Rename a file using 'rename', imported from 'os'.
    """
    rename(filename1, filename2)


def fsync_moduleImport(filename, data):
    """
    Sync some data to a filename using 'os.fsync'.
    """
    f = open(filename, "w")
    f.write(data)
    f.flush()
    os.fsync(f.fileno())


def fsync_functionImport(filename, data):
    """
    Sync some data to a filename using 'os.fsync'.
    """
    f = open(filename, "w")
    f.write(data)
    f.flush()
    fsync(f.fileno())


def osname():
    """
    Return 'os.name', an attribute unrelated to filesystem operations, to
    verify that the module remains otherwise unmolested.
    """
    return os.name
