# -*- test-case-name: twisted.test.test_paths -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Python 3 and Windows-specific wrappers for L{os.path}/L{os} that use Unicode only.
"""

import os
import os.path


def _ensureText(path):

    if isinstance(path, bytes):
        return path.decode("mbcs")
    return path


def _ensureOriginal(oldPath, newPath):
    if isinstance(oldPath, bytes) and isinstance(newPath, str):
        return newPath.encode('mbcs')
    return newPath


def isabs(path):
    return os.path.isabs(_ensureText(path))

def exists(path):
    return os.path.exists(_ensureText(path))

def normpath(path):
    res = os.path.normpath(_ensureText(path))
    return _ensureOriginal(path, res)

def abspath(path):
    res = os.path.abspath(_ensureText(path))
    return _ensureOriginal(path, res)

def splitext(path):
    res = os.path.splitext(_ensureText(path))
    return tuple([_ensureOriginal(path, newPath) for newPath in res])

def basename(path):
    res = os.path.basename(_ensureText(path))
    return _ensureOriginal(path, res)

def dirname(path):
    res = os.path.dirname(_ensureText(path))
    return _ensureOriginal(path, res)

def join(path, *paths):
    res = os.path.join(_ensureText(path),
                       *[_ensureText(path) for path in paths])
    return _ensureOriginal(path, res)

def listdir(path):
    res = os.listdir(path)
    return [_ensureOriginal(path, newPath) for newPath in res]

def utime(path, times):
    return os.utime(_ensureText(path), times)

def stat(path):
    return os.stat(_ensureText(path))

def realpath(path):
    res = os.path.realpath(_ensureText(path))
    return _ensureOriginal(path, res)

def symlink(source, link_name):
    return os.symlink(_ensureText(source), _ensureText(link_name))

def chmod(path, mode):
    return os.chmod(_ensureText(path), mode)

def rmdir(path):
    return os.rmdir(_ensureText(path))

def remove(path):
    return os.remove(_ensureText(path))

def rename(fromPath, toPath):
    return os.rename(_ensureText(fromPath), _ensureText(toPath))

def mkdir(path):
    return os.mkdir(_ensureText(path))

def makedirs(path):
    return os.makedirs(_ensureText(path))

def open(path, *args, **kwargs):
    return os.open(_ensureText(path), *args, **kwargs)

def fdopen(path, *args, **kwargs):
    return os.fdopen(_ensureText(path), *args, **kwargs)
