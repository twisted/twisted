#!/usr/bin/env python

import os, os.path, types

from twisted.python.util import sibpath

from twisted.python import components
import zope.interface as zi

# the interface we'll be adapting instances to

class IFilePath(components.Interface):
    def getPath():
        """i return a string that represents a file path"""


class Adapter(object):
    def __init__(self, original):
        self.original = original

# here are some adapters to IFilePath

class ModulePath(Adapter):
    zi.implements(IFilePath)
    def getPath(self):
        return os.path.abspath(self.original.__file__)

class ListPath(Adapter):
    zi.implements(IFilePath)
    def getPath(self):
        return os.path.join(*self.original)

class StringPath(Adapter):
    zi.implements(IFilePath)
    def getPath(self):
        return os.path.basename(self.original)

class KlassPath(Adapter):
    zi.implements(IFilePath)
    def getPath(self):
        return os.path.abspath(__import__(self.original.__module__).__file__)


# here is where we hook together all the pieces

for _adapter, _original, _interface in [ ( ModulePath, types.ModuleType, IFilePath ),
                                         ( ListPath,   types.ListType,   IFilePath ),
                                         ( StringPath, types.StringType, IFilePath ),
                                         ( KlassPath,  type,  IFilePath ) ]:

    components.registerAdapter(_adapter, _original, _interface)


def main():
    aString = "/foo/bar/baz"
    aList = ['path', 'to', 'knowhere']
    aModule = __import__('twisted')
    aKlass = Adapter

    # if you've ever been in a situation where you were just *dying* to use isinstance()
    # you actually wanted interfaces and adapters

    print IFilePath(aString).getPath()
    print IFilePath(aList).getPath()
    print IFilePath(aModule).getPath()
    print IFilePath(aKlass).getPath()

if __name__ == '__main__':
    main()

