#!/usr/bin/env python

import os, os.path, types

from twisted.python.util import sibpath

from twisted.python import components
import zope.interface as zi

# the interface we'll be adapting instances to

class IFilePath(components.Interface):
    def getPath():
        """i return a string that represents a file path"""


# here are some adapters to IFilePath

class ModulePath(components.Adapter):
    zi.implements(IFilePath)
    def getPath(self):
        return os.path.abspath(self.original.__file__)

class ListPath(components.Adapter):
    zi.implements(IFilePath)
    def getPath(self):
        return os.path.join(*self.original)

class StringPath(components.Adapter):
    zi.implements(IFilePath)
    def getPath(self):
        return os.path.basename(self.original)


class KlassPath(components.Adapter):
    zi.implements(IFilePath)
    def getPath(self):
        return os.path.abspath(__import__(self.original.__module__).__file__)


# here is where we hook together all the pieces

for _adapter, _original, _interface in [ ( ModulePath, types.ModuleType, IFilePath ),
                                         ( ListPath,   types.ListType,   IFilePath ),
                                         ( StringPath, types.StringType, IFilePath ),
                                         ( KlassPath,  types.ClassType,  IFilePath ) ]:

    components.registerAdapter(_adapter, _original, _interface)


def main():
    aString = "/foo/bar/baz"
    aList = ['path', 'to', 'knowhere']
    aModule = __import__('twisted')
    aKlass = StringPath

    # if you've ever been in a situation where you were just *dying* to use isinstance()
    # you actually wanted interfaces and adapters


    # XXX: write this part out and make what's happening _very explicit_
    for original in [aString, aList, aModule, aKlass]:
        adapterToIFilePath = IFilePath(original)
        adapterToIFilePath.getPath() 

if __name__ == '__main__':
    main()

