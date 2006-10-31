# -*- test-case-name: twisted.test.test_paths -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.python.runtime import platform

import os
import errno
import random
import sha

from os.path import isabs, exists, normpath, abspath, splitext
from os.path import basename, dirname
from os.path import join as joinpath
from os import sep as slash
from os import listdir, utime, stat

from stat import ST_MODE, ST_MTIME, ST_ATIME, ST_CTIME, ST_SIZE
from stat import S_ISREG, S_ISDIR

from zope.interface import Interface, implements

try:
    from os.path import islink
except ImportError:
    def islink(path):
        return False

try:
    from os import urandom as randomBytes
except ImportError:
    def randomBytes(n):
        randomData = [random.randrange(256) for n in xrange(n)]
        return ''.join(map(chr, randomData))

try:
    from base64 import urlsafe_b64encode as armor
except ImportError:
    def armor(s):
        return s.encode('hex')

class IFilePath(Interface):
    """
    File path object.

    A file path represents a location for a file-like-object and can be
    organized into a hierarchy; a file path can can children which are
    themselves file paths.

    A file path has a name which unique identifies it in the context of its
    parent (if it has one); a file path can not have two children with the same
    name.  This name is referred to as the file path's "base name".

    A series of such names can be used to locate nested children of a file path;
    such a series is referred to as the child's "path", relative to the parent.
    In this case, each name in the path is referred to as a "path segment"; the
    child's base name is the segment in the path.

    When representing a file path as a string, a "path separator" is used to
    delimit the path segments within the string.  For a file system path, that
    would be C{os.sep}.

    Note that the values of child names may be restricted.  For example, a file
    system path will not allow the use of the path separator in a name, and
    certain names (eg. C{"."} and C{".."}) may be reserved or have special
    meanings.
    """
    sep = Attribute("The path separator to use in string representations")

    def child(name):
        """
        Obtain a direct child of this file path.  The child may or may not
        exist.

        @param name: the name of a child of this path. C{name} must be a direct
            child of this path and may not contain a path separator.
        @return: the child of this path with the given C{name}.
        @raise InsecurePath: if C{name} describes a file path that is not a
            direct child of this file path.
        """

    def childSearchPreauth(*paths):
        """
        Obtain an existing child of this file path, if any, whose path is in the
        given sequence of child paths.

        This method may assume that each path in C{paths} identifies a child of
        this file path; the caller is expected to ensure this if necessary.  It
        is therefore important not to call this method with paths derived from
        untrusted data.

        @param paths: a sequence of paths for children of this file path.
        @return: the first existing child of this file path with a name in
            C{paths}, or C{None} if no matching child is found.
        """

    def siblingExtensionSearch(*extensions):
        """
        Obtain an existing sibling of this file path (that is, a file path which
        shares the same parent), if any, whose name is the same as the name of
        this file path with one of the given suffixes added.

        The extension "" matches this file path.

        The special extension "*" matches any suffix which begins with ".".

        @param extensions: a sequence of extensions.
        @return: a file path which matches the first of the given C{extensions}
            which has a matching file path.
        """

    # FIXME: Implementation-specific exceptions are a drag.  Unfortunately,
    # FilePath already raises various OS-specific exceptions.

    def open(mode="r"):
        """
        Opens this file path with the given mode.
        @return: a file-like-object.
        @raise Exception: if this file path cannot be opened.
        """

    def restat(reraise=True):
        """
        Reloads cached metadata for the file at this file path.
        @param reraise: specifies whether exceptions should be propagated to the
            caller.
        @raise Exception: is C{reraise} is C{True} and an exception occurs while
            reloading metadata.
        """

    def getsize():
        """
        @return: the size of the file at this file path in bytes.
        @raise Exception: if the size cannot be obtained.
        """

    def getmtime():
        """
        @return: the last modification time of the file at this file path in
            bytes.
        @raise Exception: if the last modification time cannot be obtained.
        """

    def getctime():
        """
        @return: the creation time of the file at this file path in bytes.
        @raise Exception: if the creation time cannot be obtained.
        """

    def getatime():
        """
        @return: the last access time of the file at this file path in bytes.
        @raise Exception: if the last access time cannot be obtained.
        """

    def exists():
        """
        @return: C{True} if the file at this file path exists, C{False}
            otherwise.
        """

    def isdir():
        """
        @return: C{True} if the file at this file path is a directory, C{False}
            otherwise.
        """

    def isfile():
        """
        @return: C{True} if the file at this file path is a regular file,
            C{False} otherwise.
        """

    def islink():
        """
        @return: C{True} if the file at this file path is a symbolic link,
            C{False} otherwise.
        """

    def isabs():
        """
        @return: C{True} if this file path is absolute, C{False} otherwise.
        """

    def listdir():
        """
        @return: a list of the children of the directory at this file path.
        @raise Exception: if the file at this file path is not a directory.
        """

    def splitext():
        """
        @return: a tuple C{(root, ext)} where C{root + ext} is the base name of
            this file path and C{ext} is empty or begins with a period and
            contains at most one period.
        """

    def touch():
        """
        Updates the last modification time of the file at this file path to the
        current time, creating a regular file, if not file exists, at this file
        path.
        @raise Exception: if unable to create or modify the last modification
            time of the file.
        """

    def remove():
        """
        Removes the file at this file path.
        @raise Exception: if unable to remove the file.
        """

    def makedirs():
        """
        Creates a directory, if none exists, at this file path, creating any
        non-existing intermediate directories as necessary.
        @raise Exception: if unable to create the directory.
        """

    def globChildren(pattern):
        """
        @return: a list of the children of the directory at this file path.
        @raise Exception: if the file at this file path is not a directory.
        """

    def basename(self):
        """
        @return: the base name of this file path.
        """

    def dirname(self):
        """
        @return: if the file at this file path is a directory, the string
            representation of this file path; otherwise, the the string
            representation of the path to the directory containing the file at
            this file path.
        """

    def parent(self):
        """
        A file path for the directory containing the file at this file path.
        """

class InsecurePath(Exception):
    pass

def _secureEnoughString():
    """
    Create a pseudorandom, 16-character string for use in secure filenames.
    """
    return armor(sha.new(randomBytes(64)).digest())[:16]

class _PathHelper:
    """
    Abstract helper class also used by ZipPath; implements certain utility methods.
    """

    def getContent(self):
        return self.open().read()

    def children(self):
        return map(self.child, self.listdir())

    def walk(self):
        """
        Yield myself, then each of my children, and each of those children's
        children in turn.

        @return: a generator yielding FilePath-like objects.
        """
        yield self
        if self.isdir():
            for c in self.children():
                for subc in c.walk():
                    yield subc

    def sibling(self, path):
        return self.parent().child(path)

    def segmentsFrom(self, ancestor):
        """
        Return a list of segments between a child and its ancestor.

        For example, in the case of a path X representing /a/b/c/d and a path Y
        representing /a/b, C{Y.segmentsFrom(X)} will return C{['c',
        'd']}.

        @param ancestor: an instance of the same class as self, ostensibly an
        ancestor of self.

        @raise: ValueError if the 'ancestor' parameter is not actually an
        ancestor, i.e. a path for /x/y/z is passed as an ancestor for /a/b/c/d.

        @return: a list of strs
        """
        # this might be an unnecessarily inefficient implementation but it will
        # work on win32 and for zipfiles; later I will deterimine if the
        # obvious fast implemenation does the right thing too
        f = self
        p = f.parent()
        segments = []
        while f != ancestor and p != f:
            segments[0:0] = [f.basename()]
            f = p
            p = p.parent()
        if f == ancestor and segments:
            return segments
        raise ValueError("%r not parent of %r" % (ancestor, self))

class FilePath(_PathHelper):
    """I am a path on the filesystem that only permits 'downwards' access.

    Instantiate me with a pathname (for example,
    FilePath('/home/myuser/public_html')) and I will attempt to only provide
    access to files which reside inside that path.  I may be a path to a file,
    a directory, or a file which does not exist.

    The correct way to use me is to instantiate me, and then do ALL filesystem
    access through me.  In other words, do not import the 'os' module; if you
    need to open a file, call my 'open' method.  If you need to list a
    directory, call my 'path' method.

    Even if you pass me a relative path, I will convert that to an absolute
    path internally.

    @type alwaysCreate: C{bool}
    @ivar alwaysCreate: When opening this file, only succeed if the file does not
    already exist.
    """
    implements(IFilePath)

    statinfo = None
    path = None

    sep = slash

    def __init__(self, path, alwaysCreate=False):
        self.path = abspath(path)
        self.alwaysCreate = alwaysCreate

    def __getstate__(self):
        d = self.__dict__.copy()
        if d.has_key('statinfo'):
            del d['statinfo']
        return d

    def child(self, path):
        if platform.isWindows() and path.count(":"):
            # Catch paths like C:blah that don't have a slash
            raise InsecurePath("%r contains a colon." % (path,))
        norm = normpath(path)
        if self.sep in norm:
            raise InsecurePath("%r contains one or more path separators" % (path,))
        newpath = abspath(joinpath(self.path, norm))
        if not newpath.startswith(self.path):
            raise InsecurePath("%r is not a child of %s" % (newpath, self.path))
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
        if self.alwaysCreate:
            assert 'a' not in mode, "Appending not supported when alwaysCreate == True"
            return self.create()
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
        # We can't use cached stat results here, because that is the stat of
        # the destination - (see #1773) which in *every case* but this one is
        # the right thing to use.  We could call lstat here and use that, but
        # it seems unlikely we'd actually save any work that way.  -glyph
        return islink(self.path)

    def isabs(self):
        return isabs(self.path)

    def listdir(self):
        return listdir(self.path)

    def splitext(self):
        return splitext(self.path)

    def __repr__(self):
        return 'FilePath(%r)' % (self.path,)

    def touch(self):
        try:
            self.open('a').close()
        except IOError:
            pass
        utime(self.path, None)

    def remove(self):
        if self.isdir():
            for child in self.children():
                child.remove()
            os.rmdir(self.path)
        else:
            os.remove(self.path)
        self.restat(False)

    def makedirs(self):
        return os.makedirs(self.path)

    def globChildren(self, pattern):
        """
        Assuming I am representing a directory, return a list of
        FilePaths representing my children that match the given
        pattern.
        """
        import glob
        path = self.path[-1] == '/' and self.path + pattern or self.sep.join([self.path, pattern])
        return map(self.clonePath, glob.glob(path))

    def basename(self):
        return basename(self.path)

    def dirname(self):
        return dirname(self.path)

    def parent(self):
        return self.clonePath(self.dirname())

    def setContent(self, content, ext='.new'):
        sib = self.siblingExtension(ext)
        sib.open('w').write(content)
        if platform.isWindows() and exists(self.path):
            os.unlink(self.path)
        os.rename(sib.path, self.path)

    # new in 2.2.0

    def __cmp__(self, other):
        if not isinstance(other, FilePath):
            return NotImplemented
        return cmp(self.path, other.path)

    def createDirectory(self):
        os.mkdir(self.path)

    def requireCreate(self, val=1):
        self.alwaysCreate = val

    def create(self):
        """Exclusively create a file, only if this file previously did not exist.
        """
        fdint = os.open(self.path, (os.O_EXCL |
                                    os.O_CREAT |
                                    os.O_RDWR))

        # XXX TODO: 'name' attribute of returned files is not mutable or
        # settable via fdopen, so this file is slighly less functional than the
        # one returned from 'open' by default.  send a patch to Python...

        return os.fdopen(fdint, 'w+b')

    def temporarySibling(self):
        """
        Create a path naming a temporary sibling of this path in a secure fashion.
        """
        sib = self.sibling(_secureEnoughString() + self.basename())
        sib.requireCreate()
        return sib

    _chunkSize = 2 ** 2 ** 2 ** 2

    def copyTo(self, destination):
        # XXX TODO: *thorough* audit and documentation of the exact desired
        # semantics of this code.  Right now the behavior of existent
        # destination symlinks is convenient, and quite possibly correct, but
        # its security properties need to be explained.
        if self.isdir():
            if not destination.exists():
                destination.createDirectory()
            for child in self.children():
                destChild = destination.child(child.basename())
                child.copyTo(destChild)
        elif self.isfile():
            writefile = destination.open('w')
            readfile = self.open()
            while 1:
                # XXX TODO: optionally use os.open, os.read and O_DIRECT and
                # use os.fstatvfs to determine chunk sizes and make
                # *****sure**** copy is page-atomic; the following is good
                # enough for 99.9% of everybody and won't take a week to audit
                # though.
                chunk = readfile.read(self._chunkSize)
                writefile.write(chunk)
                if len(chunk) < self._chunkSize:
                    break
            writefile.close()
            readfile.close()
        else:
            # If you see the following message because you want to copy
            # symlinks, fifos, block devices, character devices, or unix
            # sockets, please feel free to add support to do sensible things in
            # reaction to those types!
            raise NotImplementedError(
                "Only copying of files and directories supported")

    def moveTo(self, destination):
        try:
            os.rename(self.path, destination.path)
            self.restat(False)
        except OSError, ose:
            if ose.errno == errno.EXDEV:
                # man 2 rename, ubuntu linux 5.10 "breezy":

                #   oldpath and newpath are not on the same mounted filesystem.
                #   (Linux permits a filesystem to be mounted at multiple
                #   points, but rename(2) does not work across different mount
                #   points, even if the same filesystem is mounted on both.)

                # that means it's time to copy trees of directories!
                secsib = destination.temporarySibling()
                self.copyTo(secsib) # slow
                secsib.moveTo(destination) # visible

                # done creating new stuff.  let's clean me up.
                mysecsib = self.temporarySibling()
                self.moveTo(mysecsib) # visible
                mysecsib.remove() # slow
            else:
                raise


FilePath.clonePath = FilePath
