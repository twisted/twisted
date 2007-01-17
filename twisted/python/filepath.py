# -*- test-case-name: twisted.test.test_paths -*-
# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Object-oriented filesystem path representation.
"""

import os
import errno
import random
import sha
from os import path as ospath
import base64
import glob

from os import sep as slash

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
    pass


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
    Abstract helper class also used by ZipPath; implements certain utility methods.
    """

    def getContent(self):
        return self.open().read()

    def children(self):
        """
        List the children of this path object.

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
            subnames = self._listdir(self.fsPathname)
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

        FIXME: a list of strs is now wrong. Deprecate?
        """
        # this might be an unnecessarily inefficient implementation but it will
        # work on win32 and for zipfiles; later I will deterimine if the
        # obvious fast implemenation does the right thing too
        f = self
        p = f.parent()
        segments = []
        while f != ancestor and p != f:
            segments[0:0] = [f.fsBasename]
            f = p
            p = p.parent()
        if f == ancestor and segments:
            return segments
        raise ValueError("%r not parent of %r" % (ancestor, self))

    # new in 2.6.0
    def __hash__(self):
        """
        Hash the same as another FilePath with the same path as mine.
        """
        return hash((self.__class__, self.fsPathname))


    # pending deprecation in 2.6.0
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



class _BaseFilePath(_PathHelper):
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

    @type fsPathname: C{str} or C{unicode}
    @ivar fsPathname: The filesystem native pathname for this file. It will be a
    unicode string on some OSes and a byte string on others. It should only be
    used for passing to python filesystem APIs.

    @type displayPathname: C{unicode}
    @ivar displayPathname: The pathname for this file, suitable for displaying
    to a user. It is always unicode (decoded with 'replace' conversion if
    necessary). However, due to the conversion, there may have been some data
    loss.

    @type fsBasename: C{str} or C{unicode}
    @ivar fsBasename: The basename (last component of the path), in the
    system preferred format. (see fsPathname)

    @type displayBasename: C{unicode}
    @ivar displayBasename: The basename (last component of the path), in
    unicode, formatted for display.

    @type alwaysCreate: C{bool}
    @ivar alwaysCreate: When opening this file, only succeed if the file does not
    already exist.
    """

    statinfo = None
    fsPathname = None

    def __init__(self, path, alwaysCreate=False):
        # Used to set the return type of various deprecated functionality
        self._inputWasUnicode = (str, unicode)[isinstance(path, unicode)]
        self.fsPathname = ospath.abspath(self._coerceToFsPath(path))
        self.alwaysCreate = alwaysCreate

    def __getstate__(self):
        d = self.__dict__.copy()
        if d.has_key('statinfo'):
            del d['statinfo']
        return d

    def _convertToInputType(self, arg):
        """Convert arg to the same type as the input."""
        if self._inputWasUnicode:
            if isinstance(arg, unicode):
                return arg
            else:
                try:
                    return arg.decode(sys.getfilesystemencoding())
                except UnicodeDecodeError:
                    # Upon error converting to unicode, return str.
                    return arg
        else:
            # path was str
            if isinstance(arg, unicode):
                # Upon error, replace with ? chars.
                return arg.encode(sys.getfilesystemencoding(), 'replace')
            else:
                return arg

    def _getPath(self):
        warnings.warn("Filepath.path is deprecated as of Twisted 2.6. "
                      "Please use .fsPathname or .displayPathname instead.",
                      category=DeprecationWarning, stacklevel=2)
        return self._convertToInputType(self.fsPathname)

    path = property(_getPath)

    def _getFSBasename(self):
        return ospath.basename(self.fsPathname)

    def _getDisplayBasename(self):
        return ospath.basename(self.displayPathname)

    fsBasename = property(_getFSBasename)
    displayBasename = property(_getDisplayBasename)

    def child(self, path):
        path = self._coerceToFsPath(path)

        if platform.isWindows() and path.count(":"):
            # No NTFS file streams allowed.
            raise InsecurePath("%r contains a colon." % (path,))
        norm = ospath.normpath(path)
        if slash in norm:
            raise InsecurePath("%r contains one or more directory separators" % (path,))
        newpath = ospath.abspath(ospath.join(self.fsPathname, norm))
        if not newpath.startswith(self.fsPathname):
            raise InsecurePath("%r is not a child of %s" % (newpath, self.fsPathname))
        return self.clonePath(newpath)

    def preauthChild(self, path):
        """
        Use me if `path' might have slashes in it, but you know they're safe.

        (NOT slashes at the beginning. It still needs to be a _child_).
        """
        path = self._coerceToFsPath(path)

        newpath = ospath.abspath(ospath.join(self.fsPathname, ospath.normpath(path)))
        if not newpath.startswith(self.fsPathname):
            raise InsecurePath("%s is not a child of %s" % (newpath, self.fsPathname))
        return self.clonePath(newpath)

    def childSearchPreauth(self, *paths):
        """Return my first existing child with a name in 'paths'.

        paths is expected to be a list of *pre-secured* path fragments; in most
        cases this will be specified by a system administrator and not an
        arbitrary user.

        If no appropriately-named children exist, this will return None.
        """
        p = self.fsPathname
        for child in paths:
            child = self._coerceToFsPath(child)
            jp = ospath.join(p, child)
            if ospath.exists(jp):
                return self.clonePath(jp)

    def siblingExtensionSearch(self, *exts):
        """Attempt to return a path with my name, given multiple possible
        extensions.

        Each extension in exts will be tested and the first path which exists
        will be returned.  If no path exists, None will be returned.  If '' is
        in exts, then if the file referred to by this path exists, 'self' will
        be returned.

        The extension '*' has a magic meaning, which means "any filename that
        begins with my name + '.' is acceptable".
        """
        for ext in exts:
            if not ext and self.exists():
                return self
            if ext == '*':
                basedot = self.fsBasename+'.'
                parent = self.parent()
                try:
                    fns = self._listdir(parent.fsPathname)
                except OSError:
                    fns = []
                for fn in fns:
                    if fn.startswith(basedot):
                        return self.clonePath(ospath.dirname(self.fsPathname)+slash+fn)
            else:
                sibpath = self.siblingExtension(ext)
                if sibpath.exists():
                    return sibpath

    def siblingExtension(self, ext):
        return self.clonePath(self.fsPathname+self._coerceToFsExt(ext))

    def open(self, mode='r'):
        if self.alwaysCreate:
            assert 'a' not in mode, "Appending not supported when alwaysCreate == True"
            return self.create()
        return open(self.fsPathname, mode+'b')

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
            self.statinfo = os.stat(self.fsPathname)
        except OSError:
            self.statinfo = 0
            if reraise:
                raise

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
        return islink(self.fsPathname)

    def isabs(self):
        warnings.warn("Filepath.isabs() is deprecated as of Twisted 2.6. "
                      "It has never returned anything but True, anyhow.",
                      category=DeprecationWarning, stacklevel=2)
        return True

    def listdir(self):
        warnings.warn("Filepath.listdir() is deprecated as of Twisted 2.6. "
                      "Please use .children() instead.",
                      category=DeprecationWarning, stacklevel=2)

        return [self._convertToInputType(x) for x in self._listdir(self.fsPathname)]

    def splitext(self):
        warnings.warn("Filepath.splitext() is deprecated as of Twisted 2.6. "
                      "Please use os.path.splitext if necessary.",
                      category=DeprecationWarning, stacklevel=2)

        return self._convertToInputType(ospath.splitext(self.fsPathname))

    def __repr__(self):
        return 'FilePath(%r)' % (self.fsPathname,)

    def touch(self):
        try:
            self.open('a').close()
        except IOError:
            pass
        os.utime(self.fsPathname, None)

    def remove(self):
        if self.isdir():
            for child in self.children():
                child.remove()
            os.rmdir(self.fsPathname)
        else:
            os.remove(self.fsPathname)
        self.restat(False)

    def makedirs(self):
        return os.makedirs(self.fsPathname)

    def globChildren(self, pattern):
        """
        Assuming I am representing a directory, return a list of
        FilePaths representing my children that match the given
        pattern.
        """
        pattern = self._coerceToFsPath(pattern)
        if self.fsPathname[-1] == slash:
            path = self.fsPathname + pattern
        else:
            slash.join([self.fsPathname, pattern])
        return map(self.clonePath, glob.glob(path))

    def basename(self):
        warnings.warn("Filepath.basename() is deprecated as of Twisted 2.6. "
                      "Please use .fsBasename or .displayBasename instead.",
                      category=DeprecationWarning, stacklevel=2)

        return self._convertToInputType(ospath.basename(self.fsPathname))

    def dirname(self):
        warnings.warn("Filepath.dirname() is deprecated as of Twisted 2.6. "
                      "Please use .parent() instead.",
                      category=DeprecationWarning, stacklevel=2)

        return self._convertToInputType(ospath.dirname(self.fsPathname))

    def parent(self):
        return self.clonePath(ospath.dirname(self.fsPathname))

    def setContent(self, content, ext='.new'):
        sib = self.siblingExtension(ext)
        sib.open('w').write(content)
         and ospath.exists(self.fsPathname):
            os.unlink(self.fsPathname)
        os.rename(sib.fsPathname, self.fsPathname)

    # new in 2.2.0

    def __cmp__(self, other):
        if not isinstance(other, FilePath):
            return NotImplemented
        return cmp(self.fsPathname, other.fsPathname)

    def createDirectory(self):
        os.mkdir(self.fsPathname)

    def requireCreate(self, val=1):
        self.alwaysCreate = val

    def create(self):
        """Exclusively create a file, only if this file previously did not exist.
        """
        fdint = os.open(self.fsPathname, (os.O_EXCL |
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
        sib = self.sibling(_secureEnoughString() + self.fsBasename)
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
                destChild = destination.child(child.fsBasename)
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
            os.rename(self.fsPathname, destination.fsPathname)
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


if ospath.supports_unicode_filenames and platform.isWindows():
    class FilePath(_BaseFilePath):
        def __init__(self, path, alwaysCreate=False):
            _BaseFilePath.__init__(path, alwaysCreate)
            # Now mangle the pathname to have the stupid \\?\ prefix that makes
            # windows allow you to access long paths and special files.
            if not self.fsPathname.startswith('\\\\?\\'):
                if self.fsPathname.startswith('\\\\'):
                    # UNC pathname: \\server\share -> \\?\UNC\server\share
                    self.fsPathname = '\\\\?\\UNC'+self.fsPathname[1:]
                self.fsPathname = '\\\\?\\'+self.fsPathname

        def _coerceToFsPath(self, path):
            if not path:
                # abspath/normpath are broken on input of u'' and returns a str.
                # Work around said brokenness.
                return ospath.normpath(ospath.getcwdu())
            elif not isinstance(path, unicode):
                return path.decode(sys.getfilesystemencoding())
            return path

        def _coerceToFsExt(self, ext):
            if not isinstance(path, unicode):
                return path.decode(sys.getfilesystemencoding())
            return path

        def _getDisplayPathname(self):
            """Property getter for displayPathname."""
            return self.fsPathname

        displayPathname = property(_getDisplayPathnamee)

        # listdir is broken without a \ on the end in Python 2.3/2.4, since they
        # append a '/*.*' instead of '\*.*'. Sigh.
        def _listdir(self, path):
            if not path.endswith('\\'):
                path = path + '\\'
            return os.listdir(path)

        # Also override setContent to use windows-specific REPLACE_EXISTING call.
        def setContent(self, content, ext='.new'):
            sib = self.siblingExtension(ext)
            sib.open('w').write(content)
            win32.rename(sib.fsPathname, self.fsPathname)

else:
    class FilePath(_BaseFilePath):
        def _coerceToFsPath(self, path):
            if isinstance(path, unicode):
                return path.encode(sys.getfilesystemencoding())
            return path

        _coerceToFsExt = _coerceToFsPath

        def _getDisplayPathname(self):
            """Property getter for displayPathname."""
            return self.fsPathname.decode(sys.getfilesystemencoding(), 'replace')

        displayPathname = property(_getDisplayPathname)



FilePath.clonePath = FilePath
