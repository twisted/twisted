#!/usr/bin/env python

import os, os.path as osp, types
from os.path import join as opj

from twisted.python.util import sibpath

from twisted.python import components
import zope.interface as zi


# functions can be adapters too!

class IFilePath(components.Interface):
        """i return a string that the this object represents in terms of a file path"""

def modulePath(original):
    return osp.abspath(original.__file__)
zi.directlyProvides(modulePath, IFilePath)

def listPath(original):
    return opj(*original)
zi.directlyProvides(IFilePath)

def filePath(original):
    return original.name
zi.directlyProvides(IFilePath)

components.registerAdapter(
    modulePath,
    types.ModuleType,
    IFilePath
)

components.registerAdapter(
    listPath,
    types.ListType,
    IFilePath
)

components.registerAdapter(
    filePath,
    types.FileType,
    IFilePath
)


def main():
    import tempfile
    f = tempfile.TemporaryFile()
    aList = ['path', 'to', 'hell', 'paved', 'with', 'good', 'intentions']
    aModule = __import__('twisted')

    # if you've ever been in a situation where you were just *dying* to use isinstance()
    # you actually wanted interfaces and adapters

    for original in [f, aList, aModule]:
        print IFilePath(original)


if __name__ == '__main__':
    main()
