#!/usr/bin/env python2.3

import re, os, os.path as osp, time
from os.path import join as opj

from twisted.python import components
import zope.interface as zi


#### our "data objects" ####
#
# these classes represent data and methods for acquiring the data we're interested in
# 


class FileGrepper(object):
   """I grep a file with a regex pattern and display matching lines""" 

   _matchlist = None

   def __init__(self, path, pattern):
       self.path = path
       self.pattern = pattern

   def _getMatchingLines(self):
       """return a list of all lines that match pattern in path"""
       r = re.compile(self.pattern)
       l = []
       if not self._matchlist:
           for num, line in enumerate(file(self.path, 'r')):
               if r.search(line):
                   l.append((num, line))
           self._matchlist = l
       return self._matchlist
   matchingLines = property(_getMatchingLines)


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
    

class FileLister(object):
    """list all files in a directory"""
    _dirlist = None
    def __init__(self, path):
        self.path = path

    def _getDirList(self):
        """returns a file list that can be easily converted into linux-style ls -l command output"""
        print 'self.path: %s' % self.path
        if not self._dirlist:
            r = []
            for name in os.listdir(self.path):
                full = opj(self.path, name)
                if osp.isfile(full):
                    r.append(ListDirItem(full))
            self._dirlist = r
        return self._dirlist
    dirlist = property(_getDirList)
   
    filenames = property(lambda self: [i.name for i in self.dirlist])
    paths = property(lambda self: [i.path for i in self.dirlist])
    


# Let's pretend everything up here is in one module...
                                                                                     
#######################################################################################
                                                                                     
# ...and everything down here is in another
 



#### our interfaces ####
#
# these are some simple interfaces that we'll make a little more complicated in
# components, phase 3
#

class IDisplay(zi.Interface):
    def simple():
        """display a simple version of data"""
   
    def verbose():
        """display a verbose view of data"""


class IPrint(IDisplay):
    """I print data to the console"""



#### our Adapters ####
#
# these adapt other objects to the required interfaces

class DisplayFileGrepper(components.Adapter):
    zi.implements(IDisplay)

    def simple(self):
        for num, line in self.original.matchingLines:
            print line

    def verbose(self):
        for num, line in self.original.matchingLines:
            print "%s:    %s" % (num, line)



class DisplayFileList(components.Adapter):
    zi.implements(IDisplay)

    def simple(self):
        print ' '.join(self.original.filenames)

    def verbose(self):

        # these next two are exarkun's bit of magic, so don't ask, I don't know

        def pmask(info):
            return ''.join([info.stat.st_mode & (256 >> n) and 'rwx'[n % 3] or '-' for n in range(9)])

        def dtype(info):
            fmt = 'pld----'
            return [fmt[i] for i in range(7) if (info.stat.st_mode >> 12) & (1 << i)][0]

        ### --end exarkun magic-- ###


        def strmtime(info):
            return time.strftime('%b %d %I:%M', time.gmtime(info.stat.st_mtime))

        for info in self.original.dirlist:
            print "%s%s   %s    %s    %s    %s   %s   %s" % (dtype(info), pmask(info), info.nlinks, info.uid, info.gid, info.size, strmtime(info), info.name)




#### adapter registration ####
#
# I always forget the order in which you call the registerAdapter function
#
# here are two very helpful suggestions from dash and moshez:
#
#  < moshez> slyphon: I always imagine it like a call
#  < moshez> Adapter(OriginalInterface) -> AdaptedInterface
#
#  < dash> slyphon: AOI AOI AOI
#

                          
components.registerAdapter(
    DisplayFileGrepper,     # our -A-dapter
    FileGrepper,            # our -O-riginal interface
    IDisplay                # our -I-nterface 
)


components.registerAdapter(
    DisplayFileList,
    FileLister,
    IDisplay
)



def getGoodPath():
    from twisted.python.util import sibpath
    import twisted.python

    # gimme a path with a lot of good files to play with
    return sibpath(twisted.__file__, '../doc/howto')


def main():
    goodpath = getGoodPath()
    filelister = FileLister(goodpath)


    print "first, let's see IDisplay(filelist).simple()'s output"
    idfl = IDisplay(filelister)
    idfl.simple()
    
    print "now let's see IDisplay(filelist).verbose()'s output"
    IDisplay(filelister).verbose()


    print "okay, now let's grep around for the pattern '\<[Tt]wisted\>' in filelist's list of names"
    pattern = r"\<[Tt]wisted\>"
    glist = [FileGrepper(path, pattern) for path in filelister.paths]

    
    print "and see IDisplay(grepper).simple()"
    for grepper in glist:
        IDisplay(grepper).simple()


    print "and now how about IDisplay(grepper).verbose()"
    for grepper in glist:
        IDisplay(grepper).simple()


if __name__ == '__main__':
    main()


