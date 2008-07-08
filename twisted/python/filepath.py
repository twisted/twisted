# -*- test-case-name: twisted.test.test_paths -*-
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Object-oriented filesystem path representation.
"""

import os
import errno
import random
import sha
import base64

from os.path import isabs, exists, normpath, abspath, splitext
from os.path import basename, dirname
from os.path import join as joinpath
from os import sep as slash
from os import listdir, utime, stat

from stat import S_ISREG, S_ISDIR

# Please keep this as light as possible on other Twisted imports; many, many
# things import this module, and it would be good if it could easily be
# modified for inclusion in the standard library.  --glyph

from twisted.python.runtime import platform

from twisted.python.win32 import ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND
from twisted.python.win32 import ERROR_INVALID_NAME, ERROR_DIRECTORY
from twisted.python.win32 import WindowsError

def _stub_islink(path):
    """
    Always return 'false' if the operating system does not support symlinks.

    @param path: a path string.
    @type path: L{str}
    @return: false
    """
    return False


def _stub_urandom(n):
    """
    Provide random data in versions of Python prior to 2.4.  This is an
    effectively compatible replacement for 'os.urandom'.

    @type n: L{int}
    @param n: the number of bytes of data to return
    @return: C{n} bytes of random data.
    @rtype: str
    """
    randomData = [random.randrange(256) for n in xrange(n)]
    return ''.join(map(chr, randomData))


def _stub_armor(s):
    """
    ASCII-armor for random data.  This uses a hex encoding, although we will
    prefer url-safe base64 encoding for features in this module if it is
    available.
    """
    return s.encode('hex')

islink = getattr(os.path, 'islink', _stub_islink)
randomBytes = getattr(os, 'urandom', _stub_urandom)
armor = getattr(base64, 'urlsafe_b64encode', _stub_armor)

class InsecurePath(Exception):
    """
    Error that is raised when the path provided to FilePath is invalid.
    """



class LinkError(Exception):
    """
    An error with symlinks - either that there are cyclical symlinks or that
    symlink are not supported on this platform.
    """



class UnlistableError(OSError):
    """
    An exception which is used to distinguish between errors which mean 'this
    is not a directory you can list' and other, more catastrophic errors.

    This error will try to look as much like the original error as possible,
    while still being catchable as an independent type.

    @ivar originalException: the actual original exception instance, either an
    L{OSError} or a L{WindowsError}.
    """
    def __init__(self, originalException):
        """
        Create an UnlistableError exception.

        @param originalException: an instance of OSError.
        """
        self.__dict__.update(originalException.__dict__)
        self.originalException = originalException



class _WindowsUnlistableError(UnlistableError, WindowsError):
    """
    This exception is raised on Windows, for compatibility with previous
    releases of FilePath where unportable programs may have done "except
    WindowsError:" around a call to children().

    It is private because all application code may portably catch
    L{UnlistableError} instead.
    """



def _secureEnoughString():
    """
    Create a pseudorandom, 16-character string for use in secure filenames.
    """
    return armor(sha.new(randomBytes(64)).digest())[:16]



class _PathHelper:
    """
    Abstract helper class also used by ZipPath; implements certain utility
    methods.
    """

    def getContent(self):
        return self.open().read()

    def children(self):
        """
        List the chilren of this path object.

        @raise OSError: If an error occurs while listing the directory.  If the
        error is 'serious', meaning that the operation failed due to an access
        violation, exhaustion of some kind of resource (file descriptors or
        memory), OSError or a platform-specific variant will be raised.

        @raise UnlistableError: If the inability to list the directory is due
        to this path not existing or not being a directory, the more specific
        OSError subclass L{UnlistableError} is raised instead.

        @return: an iterable of all currently-existing children of this object
        accessible with L{_PathHelper.child}.
        """
        try:
            subnames = self.listdir()
        except WindowsError, winErrObj:
            # WindowsError is an OSError subclass, so if not for this clause
            # the OSError clause below would be handling these.  Windows error
            # codes aren't the same as POSIX error codes, so we need to handle
            # them differently.

            # Under Python 2.5 on Windows, WindowsError has a winerror
            # attribute and an errno attribute.  The winerror attribute is
            # bound to the Windows error code while the errno attribute is
            # bound to a translation of that code to a perhaps equivalent POSIX
            # error number.

            # Under Python 2.4 on Windows, WindowsError only has an errno
            # attribute.  It is bound to the Windows error code.

            # For simplicity of code and to keep the number of paths through
            # this suite minimal, we grab the Windows error code under either
            # version.

            # Furthermore, attempting to use os.listdir on a non-existent path
            # in Python 2.4 will result in a Windows error code of
            # ERROR_PATH_NOT_FOUND.  However, in Python 2.5,
            # ERROR_FILE_NOT_FOUND results instead. -exarkun
            winerror = getattr(winErrObj, 'winerror', winErrObj.errno)
            if winerror not in (ERROR_PATH_NOT_FOUND,
                                ERROR_FILE_NOT_FOUND,
                                ERROR_INVALID_NAME,
                                ERROR_DIRECTORY):
                raise
            raise _WindowsUnlistableError(winErrObj)
        except OSError, ose:
            if ose.errno not in (errno.ENOENT, errno.ENOTDIR):
                # Other possible errors here, according to linux manpages:
                # EACCES, EMIFLE, ENFILE, ENOMEM.  None of these seem like the
                # sort of thing which should be handled normally. -glyph
                raise
            raise UnlistableError(ose)
        return map(self.child, subnames)

    def walk(self, descend=None):
        """
        Yield myself, then each of my children, and each of those children's
        children in turn.  The optional argument C{descend} is a predicate that
        takes a FilePath, and determines whether or not that FilePath is
        traversed/descended into.  It will be called with each path for which
        C{isdir} returns C{True}.  If C{descend} is not specified, all
        directories will be traversed (including symbolic links which refer to
        directories).

        @param descend: A one-argument callable that will return True for
            FilePaths that should be traversed, False otherwise.

        @return: a generator yielding FilePath-like objects.
        """
        yield self
        if self.isdir() and (descend is None or descend(self)):
            for c in self.children():
                for subc in c.walk(descend):
                    if os.path.realpath(self.path).startswith(
                        os.path.realpath(subc.path)):
                        raise LinkError("Cycle in file graph.")
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


    # new in 8.0
    def __hash__(self):
        """
        Hash the same as another FilePath with the same path as mine.
        """
        return hash((self.__class__, self.path))


    # pending deprecation in 8.0
    def getmtime(self):
        """
        Deprecated.  Use getModificationTime instead.
        """
        return int(self.getModificationTime())


    def getatime(self):
        """
        Deprecated.  Use getAccessTime instead.
        """
        return int(self.getAccessTime())


    def getctime(self):
        """
        Deprecated.  Use getStatusChangeTime instead.
        """
        return int(self.getStatusChangeTime())



class FilePath(_PathHelper):
    """
    I am a path on the filesystem that only permits 'downwards' access.

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

    Note: although time-related methods do return floating-point results, they
    may still be only second resolution depending on the platform and the last
    value passed to L{os.stat_float_times}.  If you want greater-than-second
    precision, call C{os.stat_float_times(True)}, or use Python 2.5.
    Greater-than-second precision is only available in Windows on Python2.5 and
    later.

    @type alwaysCreate: C{bool}
    @ivar alwaysCreate: When opening this file, only succeed if the file does not
    already exist.
    """

    statinfo = None
    path = None

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
        if slash in norm:
            raise InsecurePath("%r contains one or more directory separators" % (path,))
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


    def realpath(self):
        """
        Returns the absolute target as a FilePath if self is a link, self
        otherwise.  The absolute link is the ultimate file or directory the
        link refers to (for instance, if the link refers to another link, and
        another...).  If the filesystem does not support symlinks, or
        if the link is cyclical, raises a LinkError.

        Behaves like L{os.path.realpath} in that it does not resolve link
        names in the middle (ex. /x/y/z, y is a link to w - realpath on z
        will return /x/y/z, not /x/w/z).

        @return: FilePath of the target path
        @raises LinkError: if links are not supported or links are cyclical.
        """
        if self.islink():
            result = os.path.realpath(self.path)
            if result == self.path:
                raise LinkError("Cyclical link - will loop forever")
            return self.clonePath(result)
        return self


    def siblingExtension(self, ext):
        return self.clonePath(self.path+ext)


    def linkTo(self, linkFilePath):
        """
        Creates a symlink to self to at the path in the L{FilePath}
        C{linkFilePath}.  Only works on posix systems due to its dependence on
        C{os.symlink}.  Propagates C{OSError}s up from C{os.symlink} if
        C{linkFilePath.parent()} does not exist, or C{linkFilePath} already
        exists.

        @param linkFilePath: a FilePath representing the link to be created
        @type linkFilePath: L{FilePath}
        """
        os.symlink(self.path, linkFilePath.path)


    def open(self, mode='r'):
        if self.alwaysCreate:
            assert 'a' not in mode, "Appending not supported when alwaysCreate == True"
            return self.create()
        return open(self.path, mode+'b')

    # stat methods below

    def restat(self, reraise=True):
        """
        Re-calculate cached effects of 'stat'.  To refresh information on this path
        after you know the filesystem may have changed, call this method.

        @param reraise: a boolean.  If true, re-raise exceptions from
        L{os.stat}; otherwise, mark this path as not existing, and remove any
        cached stat information.
        """
        try:
            self.statinfo = stat(self.path)
        except OSError:
            self.statinfo = 0
            if reraise:
                raise


    def chmod(self, mode):
        """
        Changes the permissions on self, if possible.  Propagates errors from
        C{os.chmod} up.

        @param mode: integer representing the new permissions desired (same as
            the command line chmod)
        @type mode: C{int}
        """
        os.chmod(self.path, mode)


    def getsize(self):
        st = self.statinfo
        if not st:
            self.restat()
            st = self.statinfo
        return st.st_size


    def getModificationTime(self):
        """
        Retrieve the time of last access from this file.

        @return: a number of seconds from the epoch.
        @rtype: float
        """
        st = self.statinfo
        if not st:
            self.restat()
            st = self.statinfo
        return float(st.st_mtime)


    def getStatusChangeTime(self):
        """
        Retrieve the time of the last status change for this file.

        @return: a number of seconds from the epoch.
        @rtype: float
        """
        st = self.statinfo
        if not st:
            self.restat()
            st = self.statinfo
        return float(st.st_ctime)


    def getAccessTime(self):
        """
        Retrieve the time that this file was last accessed.

        @return: a number of seconds from the epoch.
        @rtype: float
        """
        st = self.statinfo
        if not st:
            self.restat()
            st = self.statinfo
        return float(st.st_atime)


    def exists(self):
        """
        Check if the C{path} exists.

        @return: C{True} if the stats of C{path} can be retrieved successfully,
            C{False} in the other cases.
        @rtype: C{bool}
        """
        if self.statinfo:
            return True
        else:
            self.restat(False)
            if self.statinfo:
                return True
            else:
                return False


    def isdir(self):
        st = self.statinfo
        if not st:
            self.restat(False)
            st = self.statinfo
            if not st:
                return False
        return S_ISDIR(st.st_mode)

    def isfile(self):
        st = self.statinfo
        if not st:
            self.restat(False)
            st = self.statinfo
            if not st:
                return False
        return S_ISREG(st.st_mode)

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
        """
        Removes the file or directory that is represented by self.  If
        C{self.path} is a directory, recursively remove all its children
        before removing the directory.  If it's a file or link, just delete
        it.
        """
        if self.isdir() and not self.islink():
            for child in self.children():
                child.remove()
            os.rmdir(self.path)
        else:
            os.remove(self.path)
        self.restat(False)


    def makedirs(self):
        """
        Create all directories not yet existing in C{path} segments, using
        C{os.makedirs}.
        """
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

    def dirname(self):
        return dirname(self.path)

    def parent(self):
        return self.clonePath(self.dirname())

    def setContent(self, content, ext='.new'):
        sib = self.siblingExtension(ext)
        f = sib.open('w')
        f.write(content)
        f.close()
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


    def copyTo(self, destination, followLinks=True):
        """
        Copies self to destination.

        If self is a directory, this method copies its children (but not
        itself) recursively to destination - if destination does not exist as a
        directory, this method creates it.  If destination is a file, an
        IOError will be raised.

        If self is a file, this method copies it to destination.  If
        destination is a file, this method overwrites it.  If destination is a
        directory, an IOError will be raised.

        If self is a link (and followLinks is False), self will be copied
        over as a new symlink with the same target as returned by os.readlink.
        That means that if it is absolute, both the old and new symlink will
        link to the same thing.  If it's relative, then perhaps not (and
        it's also possible that this relative link will be broken).

        File/directory permissions and ownership will NOT be copied over.

        If followLinks is True, symlinks are followed so that they're treated
        as their targets.  In other words, if self is a link, the link's target
        will be copied.  If destination is a link, self will be copied to the
        destination's target (the actual destination will be destination's
        target).  Symlinks under self (if self is a directory) will be
        followed and its target's children be copied recursively.

        If followLinks is False, symlinks will be copied over as symlinks.

        @param destination: the destination (a FilePath) to which self
            should be copied
        @param followLinks: whether symlinks in self should be treated as links
            or as their targets
        """
        if self.islink() and not followLinks:
            os.symlink(os.readlink(self.path), destination.path)
            return
        # XXX TODO: *thorough* audit and documentation of the exact desired
        # semantics of this code.  Right now the behavior of existent
        # destination symlinks is convenient, and quite possibly correct, but
        # its security properties need to be explained.
        if self.isdir():
            if not destination.exists():
                destination.createDirectory()
            for child in self.children():
                destChild = destination.child(child.basename())
                child.copyTo(destChild, followLinks)
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


    def moveTo(self, destination, followLinks=True):
        """
        Move self to destination - basically renaming self to whatever
        destination is named.  If destination is an already-existing directory,
        moves all children to destination if destination is empty.  If
        destination is a non-empty directory, or destination is a file, an
        OSError will be raised.

        If moving between filesystems, self needs to be copied, and everything
        that applies to copyTo applies to moveTo.

        @param destination: the destination (a FilePath) to which self
            should be copied
        @param followLinks: whether symlinks in self should be treated as links
            or as their targets (only applicable when moving between
            filesystems)
        """
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
                self.copyTo(secsib, followLinks) # slow
                secsib.moveTo(destination, followLinks) # visible

                # done creating new stuff.  let's clean me up.
                mysecsib = self.temporarySibling()
                self.moveTo(mysecsib, followLinks) # visible
                mysecsib.remove() # slow
            else:
                raise


FilePath.clonePath = FilePath
