#!/usr/bin/env python

import os, os.path as osp, types
from os.path import join as opj

from twisted.python.util import sibpath

from twisted.python import components
import zope.interface as zi


class IFilePath(components.Interface):
    def getPath():
        """i return a string that the this object represents in terms of a file path"""

class ModulePath(components.Adapter):
    zi.implements(IFilePath)
    def getPath(self):
        return osp.abspath(self.original.__file__)

class ListPath(components.Adapter):
    zi.implements(IFilePath)
    def getPath(self):
        return opj(*self.original)

class StringPath(components.Adapter):
    zi.implements(IFilePath)
    def getPath(self):
        return osp.basename(self.original)


class KlassPath(components.Adapter):
    zi.implements(IFilePath)
    def getPath(self):
        return osp.abspath(__import__(self.original.__module__).__file__)


components.registerAdapter(
    ModulePath,
    types.ModuleType,
    IFilePath
)

components.registerAdapter(
    ListPath,
    types.ListType,
    IFilePath
)

components.registerAdapter(
    StringPath,
    types.StringType,
    IFilePath
)

components.registerAdapter(
    KlassPath,
    types.ClassType,
    IFilePath
)


def main():
    aString = "/foo/bar/baz"
    aList = ['path', 'to', 'knowhere']
    aModule = __import__('twisted')
    aKlass = StringPath

    # if you've ever been in a situation where you were just *dying* to use isinstance()
    # you actually wanted interfaces and adapters

    for original in [aString, aList, aModule, aKlass]:
        print IFilePath(original).getPath()


if __name__ == '__main__':
    main()
