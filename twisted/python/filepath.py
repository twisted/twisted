# -*- test-case-name: twisted.test.test_paths -*-
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
#

import os
from os.path import isdir, isabs, isfile, exists, normpath, abspath, splitext
from os.path import basename, dirname, getsize, getmtime
from os.path import split as splitpath
from os.path import join as joinpath
from os import sep as slash
from os import listdir, utime, stat
from os import remove
from new import instance

from stat import ST_MODE, ST_MTIME, ST_ATIME, ST_CTIME, ST_SIZE

from stat import S_ISREG, S_ISDIR, S_ISLNK

try:
    from os.path import islink
except ImportError:
    def islink(path):
        return False

class InsecurePath(Exception):
    pass

class FilePath:
    
    """I am a path on the filesystem that only permits 'downwards' access.

    Instantiate me with a pathname (for example,
    FilePath('/home/myuser/public_html')) and I will attempt to only provide
    access to files which reside insidpe that path.  I may be a path to a file,
    a directory, or a file which does not exist.

    The correct way to use me is to instantiate me, and then do ALL filesystem
    access through me.  In other words, do not import the 'os' module; if you
    need to open a file, call my 'open' method.  If you need to list a
    directory, call my 'path' method.

    Even if you pass me a relative path, I will convert that to an absolute
    path internally.
    """

    # __slots__ = 'path abs'.split()

    statinfo = None

    def __init__(self, path):
        self.path = abspath(path)

    def __getstate__(self):
        d = self.__dict__.copy()
        if d.has_key('statinfo'):
            del d['statinfo']
        return d

    def child(self, path):
        norm = normpath(path)
        if slash in norm:
            raise InsecurePath()
        newpath = abspath(joinpath(self.path, norm))
        if not newpath.startswith(self.path):
            raise InsecurePath()
        return self.clonePath(newpath)

    def preauthChild(self, path):
        """
        Use me if `path' might have slashes in it, but you know they're safe.

        (NOT slashes at the beginning. It still needs to be a _child_).
        """
        newpath = abspath(joinpath(self.path, normpath(path)))
        if not newpath.startswith(self.path):
            raise InsecurePath("%s is not a child of %s" % (newpath, self.path))
        return self.clonePath(newpath)
        

    def childSearchPreauth(self, *paths):
        """Return my first existing child with a name in 'paths'.

        paths is expected to be a list of *pre-secured* path fragments; in most
        cases this will be specified by a system administrator and not an
        arbitrary user.

        If no appropriately-named children exist, this will return None.
        """
        p = self.path
        for child in paths:
            jp = joinpath(p, child)
            if exists(jp):
                return self.clonePath(jp)

    def siblingExtensionSearch(self, *exts):
        """Attempt to return a path with my name, given multiple possible
        extensions.

        Each extension in exts will be tested and the first path which exists
        will be returned.  If no path exists, None will be returned.  If '' is
        in exts, then if the file referred to by this path exists, 'self' will
        be returned.

        The extension '*' has a magic meaning, which means "any path that
        begins with self.path+'.' is acceptable".
        """
        p = self.path
        for ext in exts:
            if not ext and self.exists():
                return self
            if ext == '*':
                basedot = basename(p)+'.'
                for fn in listdir(dirname(p)):
                    if fn.startswith(basedot):
                        return self.clonePath(joinpath(dirname(p), fn))
            p2 = p + ext
            if exists(p2):
                return self.clonePath(p2)

    def siblingExtension(self, ext):
        return self.clonePath(self.path+ext)

    def open(self, mode='r'):
        return open(self.path, mode+'b')

    # stat methods below

    def restat(self, reraise=True):
        try:
            self.statinfo = stat(self.path)
        except OSError:
            self.statinfo = 0
            if reraise:
                raise
    
    def getsize(self):
        st = self.statinfo
        if not st:
            self.restat()
            st = self.statinfo
        return st[ST_SIZE]

    def getmtime(self):
        st = self.statinfo
        if not st:
            self.restat()
            st = self.statinfo
        return st[ST_MTIME]

    def getctime(self):
        st = self.statinfo
        if not st:
            self.restat()
            st = self.statinfo
        return st[ST_CTIME]

    def getatime(self):
        st = self.statinfo
        if not st:
            self.restat()
            st = self.statinfo
        return st[ST_ATIME]

    def exists(self):
        if self.statinfo:
            return True
        elif self.statinfo is None:
            self.restat(False)
            return self.exists()
        else:
            return False

    def isdir(self):
        st = self.statinfo
        if not st:
            self.restat(False)
            st = self.statinfo
            if not st:
                return False
        return S_ISDIR(st[ST_MODE])

    def isfile(self):
        st = self.statinfo
        if not st:
            self.restat(False)
            st = self.statinfo
            if not st:
                return False
        return S_ISREG(st[ST_MODE])

    def islink(self):
        st = self.statinfo
        if not st:
            self.restat(False)
            st = self.statinfo
            if not st:
                return False
        return S_ISLNK(st[ST_MODE])

    def isabs(self):
        return isabs(self.path)

    def listdir(self):
        return listdir(self.path)

    def splitext(self):
        return splitext(self.path)

    def __repr__(self):
        return 'FilePath(%r)' % self.path

    def touch(self):
        try:
            self.open('a').close()
        except IOError:
            pass
        utime(self.path,None)

    def remove(self):
        remove(self.path)

    def makedirs(self):
        return os.makedirs(self.path)

    def globChildren(self, pattern):
        """
        Assuming I am representing a directory, return a list of
        FilePaths representing my children that match the given
        pattern.
        """
        import glob
        path = self.path[-1] == '/' and self.path + pattern or slash.join([self.path, pattern])
        return map(self.clonePath, glob.glob(path))

    def basename(self):
        return basename(self.path)

    def setContent(self, content, ext='.new'):
        sib = self.siblingExtension(ext)
        sib.open('w').write(content)
        os.rename(sib.path, self.path)

    def getContent(self):
        return self.open().read()


FilePath.clonePath = FilePath
