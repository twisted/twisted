#!/usr/bin/env python

import os, os.path as osp, types
from os.path import join as opj

from twisted.python import components
import zope.interface 


# functions can be adapters too!

class IFilePath(zope.interface.Interface):
   """i return a string that the this object represents in terms of a file path"""
   pass

def modulePath(original):
    return osp.abspath(original.__file__)
zope.interface.directlyProvides(modulePath, IFilePath)

def listPath(original):
    return opj(*original)
zope.interface.directlyProvides(listPath, IFilePath)

def filePath(original):
    return original.name
zope.interface.directlyProvides(filePath, IFilePath)


for _adapter, _original, _interface in [ (modulePath, types.ModuleType, IFilePath),
                                         (listPath, types.ListType, IFilePath),
                                         (filePath, types.FileType, IFilePath) ]:

    components.registerAdapter(_adapter, _original, _interface)


def main():
    import tempfile
    f = tempfile.TemporaryFile()
    aList = ['path', 'to', 'hell', 'paved', 'with', 'good', 'intentions']
    aModule = __import__('twisted')

    for original in [f, aList, aModule]:
        print IFilePath(original)


if __name__ == '__main__':
    main()
