# -*- test-case-name: twisted.test.test_filepile -*-
#
# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Consecutive filesystem mashing.  See FilePile.__doc__ for details.
"""

import os
import socket
from time import time as _uniquefloat

def unique():
    return str(long(_uniquefloat() * 1000))

try:
    from os import symlink
    from os import readlink
except:
    def symlink(value, filename):
        newlinkname = filename+"."+unique()+'.newlink'
        newvalname = os.path.join(newlinkname,"symlink")
        os.mkdir(newlinkname)
        f = open(newvalname,'wb')
        f.write(value)
        f.flush()
        f.close()
        try:
            os.rename(newlinkname, filename)
        except:
            os.remove(newvalname)
            os.rmdir(newlinkname)
            raise

    def readlink(filename):
        return open(os.path.join(filename,'symlink'),'rb').read()

from os import makedirs

prochost = socket.gethostname()
procpid = os.getpid()

def _bisect_cmp(a, x, cmpfunc=cmp, lo=0, hi=None):
    """A left-bisect on a vector using a user-provided comparison function.
    """
    if hi is None:
        hi = len(a)
    while lo < hi:
        mid = (lo+hi) // 2
        if cmpfunc(a[mid], x) == -1:
            lo = mid+1
        else:
            hi = mid
    return lo

def nextFileName(dirname, ext, directory=False):
    """Get a sequential file-name from a directory in a NFS and SMP-safe way.

    When you use this filename, do not run file() or symlink() on it; you
    must create a file elsewhere (you can use a mutated version of the returned
    filename to achieve SMP/NFS safety) and use os.rename over the returned
    filename.

    The returned filename includes the passed-in dirname; if you want an
    absolute path, pass an absolute dirname - don't manipulate the returned
    path.

    This will allocate a file-name using the following strategy:

        - look for a symlink named ext.sequence
        - if it's found
          - read the body of this symlink and jump to that sequence number
        - otherwise
          - start from 0
        - keep incrementing the sequence number until you arrive at a
        [sequence].ext which does not exist. (this is verified by creating a
        symlink, which is should always be an atomic test-and-set for non-local
        filesystems.)

    This algorithm is optimistic and may block for a while if there are a lot
    of concurrent processes working on the same directory.  Also, if you delete
    a symlink created in this way, sequence numbers may repeat.

    The optional 'directory' parameter will create a directory rather than a
    symlink, which is also safe.  As it is an empty directory, it will support
    os.rename'ing another directory over it.  At least on Linux.  At least on
    version 2.4.  10+.  Maybe.
    """
    if not os.path.isdir(dirname):
        makedirs(dirname)
    fn = os.path.join(dirname, ext+".sequence")
    try:
        num = int(readlink(fn))
    except (OSError, IOError):
        num = 0
    while True:
        extname = os.path.join(dirname, str(num)+ext)
        try:
            if directory:
                os.mkdir(extname)
            else:
                symlink(str(num), extname)
            break
        except OSError:
            pass
        num += 1
    try:
        os.remove(fn)
    except OSError:
        pass
    try:
        symlink(str(num), fn)
    except OSError:
        pass
    return extname


class _FilePileStackEntry:
    """I represent a cursor in an open directory; nothing to see here, move
    along, move along.
    """
    
    def __init__(self, dirname, loader=str, pilext='pile', itemext='item',
                 cmpfunc=cmp):
        
        """Create a pointer into a directory given with dirname.  Pass in
        options from a parent FilePile.  NOTE THAT CMPFUNC WILL BE IGNORED ON
        DIRECTORIES THAT HAVE HAD nextFileName USED WITH THE SAME EXTENSION
        GIVEN IN ITEMEXT.
        """
        self.dirname = dirname
        self.loader = loader
        self.pilext = pilext
        self.itemext = itemext
        self.cmpfunc = cmpfunc
        self.dirlist = None
        if os.path.exists(os.path.join(self.dirname, '.'+pilext+'.sequence')):
            self.cmpfunc = LenientIntCompare(pilext=pilext, itemext=itemext)
        else:
            self.cmpfunc = cmpfunc

    def makeChild(self, path):
        """Create a stack entry with similar options for a subpath of the
        directory I am listing.
        """
        return _FilePileStackEntry(os.path.join(self.dirname, path),
                                   self.loader, self.pilext, self.itemext,
                                   self.cmpfunc)

    def makeCopy(self):
        return _FilePileStackEntry(self.dirname,
                                   self.loader, self.pilext, self.itemext,
                                   self.cmpfunc)

    def listdir(self, forwards=True):
        """If I do not have a cached directory listing, load a directory
        listing and sort it according to self.cmpfunc.
        """
        if self.dirlist is None:
            self.dirlist = os.listdir(self.dirname)
            self.dirlist.sort(self.cmpfunc)
            if forwards:
                self.pos = -1
            else:
                self.pos = len(self.dirlist) -1
        return self.dirlist

    def bisectTo(self, name, adjust=0):
        """Jump my pointer position to point at a file who compares as closely
        as possible to name with self.cmpfunc.
        """
        self.pos = _bisect_cmp(self.listdir(), name, cmpfunc=self.cmpfunc) + adjust

    def next(self, forwards=True):
        """I AM NOT AN ITERATOR THIS IS JUST A GOOD METHOD NAME.  Get the next
        entry (isSubDirectory, itemOr_FilePileStackEntry).  If forwards is
        False, go backwards.
        """
        dirlist = self.listdir(forwards)
        while True:
            if forwards:
                if self.pos == len(dirlist) -1:
                    return
                self.pos += 1
            else:
                if self.pos < 0:
                    return
            name = dirlist[self.pos]
            if not forwards:
                self.pos -= 1
            ext = name.split('.')[-1]
            if ext == self.itemext:
                return False, self.loader(os.path.join(self.dirname, name))
            elif ext == self.pilext:
                return True, self.makeChild(name)

    def prev(self):
        """synonym for .next(False)
        """
        return self.next(False)

# XXX TODO: something like this - make os.mkdirs NFS safe.  probably just means
# we need to wrap each iteration in a try:except:

## def makedirs(self, fn):
##     sp = os.path.split(os.path.abspath(fn))
##     for seg in xrange(len(sp)):
##         cur = os.path.join(*sp[:seg+1])
##         while not os.path.isdir(cur):
##             try:
##                 os.symlink("mkdir", ".mkdir-lock-%s" % cur)
##             except:
##                 pass

class FilePileIterator:
    """I am a sorted list of files stored in a tree of directories.  I map
    filenames to Python objects using a 'loader' factory function.
    """

    def __init__(self, dirname, loader=str, pilext='pile', itemext='item', cmpfunc=cmp):
        self.dirname = dirname
        self.itemext = itemext
        self.pilext = pilext
        self.stack = [_FilePileStackEntry(dirname, loader, pilext, itemext, cmpfunc)]

    def rewind(self):
        """Jump back to the beginning of the top level directory, as if I had
        just been instantiated.
        """
        self.stack = [self.stack[0]]
        self.stack[0].pos = -1
        self.stack[0].dirlist = None

    def jumpTo(self, *path):
        """'Seek' my internal cursor forward to be as close as possible to an
        object at a given path.  This object does not need to exist, but if it
        does, it will be the next object returned by self.next().
        """
        piles = [("%s.%s" % (x, self.pilext)) for x in path[:-1]]
        item = '%s.%s' % (path[-1],self.itemext)
        self.stack = [self.stack[0]]
        for pilename in piles:
            newent = self.stack[-1].makeChild(pilename)
            self.stack[-1].bisectTo(pilename)
            if os.path.isdir(newent.dirname):
                self.stack.append(newent)
        else:
            self.stack[-1].bisectTo(item, adjust=-1)

    def next(self, forwards=True):
        """Get the next item at my current cursor location.  This will always
        ben an object created by self.loader.  If 'forwards' is false, go
        backwards.

        @raise: StopIteration when there are no items left.
        """
        while True:
            result = self.stack[-1].next(forwards)
            if result is None:
                if len(self.stack) == 1:
                    raise StopIteration()
                else:
                    self.stack.pop()
            else:
                isFilePile, item = result
                if isFilePile:
                    self.stack.append(item)
                else:
                    return item

    def prev(self):
        """Synonym for self.next(False).
        """
        return self.next(False)

    def __iter__(self):
        return self

class FilePile:
    """
    I manage trees of filenames and symlinks to help you write storage
    systems.
    """

    def __init__(self, dirname, loader=str, pilext='pile', itemext='item', cmpfunc=cmp):
        """Create a FilePile.

        @param loader: a factory function for whatever kind of objects you are
        storing here.  The signature of this function is loader(filename) ->
        object.

        @param cmpfunc: a comparison function which compares filenames.  This
        has a signature identical to cmp, and is passed to list.sort.

        @param pilext: The extension to use for subdirectories which represent
        collections, or 'subpiles'.

        @param itemext: The extension to use for files or symlinks in this
        directory whose names will be passed to the 'loader' function, and
        returned from my iteration methods.
        """
        self.dirname = dirname
        self.itemext = itemext
        self.pilext = pilext
        self.cmpfunc = cmpfunc
        self.loader = loader

    def pilePath(self, *path):
        "pilePath('1','2','3') => '<self.dirname>/1.pile/2.pile/3.pile'"
        return os.path.join(self.dirname,*[("%s.%s" % (x, self.pilext)) for x in path])

    def itemPath(self, *path):
        "itemPath('1','2','3') => '<self.dirname>/1.pile/2.pile/3.item'"
        return os.path.join(self.pilePath(*path[:-1]),'%s.%s' % (path[-1],self.itemext))

    def insertLink(self, name, *path):
        """Create an item with proper extensions at the given itemPath.

        @param name: the value of the symlink created.
        @param path: a tuple of names passed to self.itemPath(*path).
        """
        pp = self.pilePath(*path[:-1])
        if not os.path.isdir(pp):
            makedirs(pp)
        symlink(name, self.itemPath(*path))

    def numberedLink(self, *path):
        """Create an item with proper extensions at the given path.

        I use nextFileName; see its documentation for details.

        @param path: a tuple of names passed to self.pilePath(*path).
        """
        pp = self.pilePath(*path)
        return nextFileName(pp, '.'+self.itemext)

    def numberedDirectory(self, *path):
        pp = self.pilePath(*path)
        return nextFileName(pp, '.'+self.itemext, directory=True)

    def backwards(self):
        """Return an iterator that goes backwards over me.  This iterator will
        change my cursor, so watch out for concurrent uses!
        """
        return _b(iter(self))

    def __iter__(self):
        """Return me.  I will act as an iterator that goes forwards over my
        items.  Iterating this will change my cursor, so watch out for
        concurrent uses!
        """
        return FilePileIterator(self.dirname, self.loader,
                                self.pilext, self.itemext,
                                self.cmpfunc)

class _b:
    """Backwards iterator for FilePile."""
    def __init__(self, f):
        self.f = f

    def next(self):
        return self.f.prev()

    def __iter__(self):
        return self

from twisted.trial import unittest

def _lenieint(x):
    """Try to convert an object to an int, but if we can't, just give up and
    return the object itself.
    """
    try:
        return int(x)
    except:
        return x

class LenientIntCompare:
    """I am a comparator object which can be used for directories which has had
    objects created in it by nextFileName.
    """
    def __init__(self, itemext='item', poolext='pool', filt=_lenieint):
        self.itemext = itemext
        self.poolext = poolext
        self.filt = filt

    def __call__(self, fn1, fn2):
        fn1p, fn1e = os.path.splitext(fn1)
        fn2p, fn2e = os.path.splitext(fn2)
        
        # note - it might be a good idea to guarantee that pools sort before
        # items (or vice-versa) in order to make certain kinds of sorting
        # easier

        fn1i = fn1e[1:] in (self.itemext, self.poolext)
        fn2i = fn2e[1:] in (self.itemext, self.poolext)
        if fn1i and fn2i:
            return cmp(self.filt(fn1p),
                       self.filt(fn2p))
        elif fn1i:
            return -1
        elif fn2i:
            return 1
        else:
            return cmp(fn1,fn2)
