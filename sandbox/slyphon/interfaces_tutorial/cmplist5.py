#!/usr/bin/env python2.3

import re, os, os.path as osp, time, types
from os.path import join as opj

from twisted.python import components
import zope.interface as zi


class IDisplay(zi.Interface):
    def simple():
        """display a simple version of data"""
   
    def verbose():
        """display a verbose view of data"""


class IListDirItem(zi.Interface):
   def __call__(pathAsString):
      """@param pathAsString: the path to a file"""
   path = zi.Attribute("the path given to this file")
   name = zi.Attribute("the name of the file")
   nlinks = zi.Attribute("the number of hardlinks to this file")
   size = zi.Attribute("size in bytes of a plain file")
   stat = zi.Attribute("the stat object returned by os.stat of path")
   uid = zi.Attribute("the user id of the owner")
   gid = zi.Attribute("the group id of the owner")


class ListDirItem(object):
    """a basic wrapper around the os.lstat object"""
    _stat = None

    def __init__(self, path):
        self.path = path
        self.name = osp.basename(self.path)
        self.nlinks = self.stat.st_nlink
        self.uid = self.stat.st_uid
        self.gid = self.stat.st_gid
        self.size = self.stat.st_size

    def _getstat(self):
        # hooray for lazy evaluation!
        if not self._stat:
            self._stat = os.lstat(self.path)
        return self._stat
    stat = property(_getstat)

components.registerAdapter(ListDirItem, types.StringType, IListDirItem)


class IFileLister(components.Interface):
    dirlist = zi.Attribute("a file list that can be easily converted into "
                           "linux-style ls -l command output")
    filenames = zi.Attribute("the filenames this lister "
                             "has listed (without full path info)")
    paths = zi.Attribute("the full path of the items this lister has listed")

class FileLister(object):
    """list all files in a directory"""
    zi.implements(IFileLister)
    _dirlist = None

    def __init__(self, original):
        self.original = self.path = original

    def _getDirList(self):
        print 'self.path: %s' % self.path
        if not self._dirlist:
            r = []
            for name in os.listdir(self.path):
                full = opj(self.path, name)
                if osp.isfile(full):
                    r.append(IListDirItem(full))
            self._dirlist = r
        return self._dirlist
    dirlist = property(_getDirList)
   
    filenames = property(lambda self: [i.name for i in self.dirlist])
    paths = property(lambda self: [i.path for i in self.dirlist])

components.registerAdapter(FileLister, types.StringType, IFileLister)


    
class DisplayFileList(object):
    zi.implements(IDisplay)

    def simple(self):
        print ' '.join(self.original.filenames)

    def verbose(self):

        def pmask(info):
            return ''.join([info.stat.st_mode & (256 >> n)
                            and 'rwx'[n % 3] or '-' for n in range(9)])

        def dtype(info):
            fmt = 'pld----'
            return [fmt[i] for i in range(7)
                    if (info.stat.st_mode >> 12) & (1 << i)][0]

        def strmtime(info):
            return time.strftime('%b %d %I:%M', time.gmtime(info.stat.st_mtime))

        for info in self.original.dirlist:
            print "%s%s   %s    %s    %s    %s   %s   %s" % (dtype(info),
                                                             pmask(info),
                                                             info.nlinks,
                                                             info.uid,
                                                             info.gid,
                                                             info.size,
                                                             strmtime(info),
                                                             info.name)

components.registerAdapter(DisplayFileList, IFileLister, IDisplay)



class IFileGrepper(zi.Interface):
   pattern = zi.Attribute('the patern to grep for')
   matchingLines = zi.Attribute("a list of (path, num, line) tuples "
                                "that matched the pattern in path")


class FileListerGrepper(object):
   """I grep a file with a regex pattern and display matching lines""" 
   zi.implements(IFileGrepper)

   _pattern, _regex, _matchList = None, None, None

   def __init__(self, original):
       self.original = original

   def _getPattern(self):
       return self._pattern

   def _setPattern(self, pattern):
       print "_setPattern called"
       self._pattern = pattern
       self._regex = re.compile(pattern)

   pattern = property(_getPattern, _setPattern)

   def _getMatchingLines(self):
       """return a list of all lines that match pattern in path"""
       l = []
       if not self._matchList:
           for path in self.original.paths:
               for num, line in enumerate(file(path, 'r')):
                   assert self._regex
                   if self._regex.search(line):
                       l.append((osp.basename(path), num, line))
           self._matchList = l
       return self._matchList
   matchingLines = property(_getMatchingLines)

components.registerAdapter(FileListerGrepper, FileLister, IFileGrepper)


class DisplayFileGrepper(object):
    zi.implements(IDisplay)

    def simple(self):
        for path, num, line in self.original.matchingLines:
            print line

    def verbose(self):
        for path, num, line in self.original.matchingLines:
            print "%s: %s:    %s" % (path, num, line)

components.registerAdapter(DisplayFileGrepper, FileListerGrepper, IDisplay)



def getGoodPath():
    from twisted.python.util import sibpath
    import twisted.python

    # gimme a path with a lot of good files to play with
    sp = sibpath(twisted.__file__, '../doc/howto')
    return osp.normpath(sp)


def main():
    goodpath = getGoodPath()
    print "we'll be playing around with goodpath: %s" % goodpath
    print "which is an object of type: %r" % type(goodpath)
    filelister = IFileLister(goodpath)

    print "\n\n"

    print "first, let's see IDisplay(filelist).simple()'s output"
    IDisplay(filelister).simple()
    
    print "\n\n"
   
    print "now let's see IDisplay(filelist).verbose()'s output"
    IDisplay(filelister).verbose()

    print "\n\n"

    print ("okay, now let's grep around for the pattern "
           "'\<[Tt]wisted\>' in filelist's list of names")
    p = r"[Tt]wisted"
    fg = IFileGrepper(filelister)

    print fg
    
    fg.pattern = p

    print IDisplay(fg).simple()

    print "\n\n"

    print "and now how about IDisplay(fg).verbose()"
    IDisplay(fg).verbose()


if __name__ == '__main__':
    main()


