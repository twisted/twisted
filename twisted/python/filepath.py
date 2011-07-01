# -*- test-case-name: twisted.test.test_paths -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Object-oriented filesystem path representation.
"""

import os
import errno
import random
import base64

from os.path import isabs, exists, normpath, abspath, splitext
from os.path import basename, dirname
from os.path import join as joinpath
from os import sep as slash
from os import listdir, utime, stat

from stat import S_ISREG, S_ISDIR, S_IMODE, S_ISBLK, S_ISSOCK
from stat import S_IRUSR, S_IWUSR, S_IXUSR
from stat import S_IRGRP, S_IWGRP, S_IXGRP
from stat import S_IROTH, S_IWOTH, S_IXOTH


# Please keep this as light as possible on other Twisted imports; many, many
# things import this module, and it would be good if it could easily be
# modified for inclusion in the standard library.  --glyph

from twisted.python.runtime import platform
from twisted.python.hashlib import sha1

from twisted.python.win32 import ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND
from twisted.python.win32 import ERROR_INVALID_NAME, ERROR_DIRECTORY, O_BINARY
from twisted.python.win32 import WindowsError

from twisted.python.util import FancyEqMixin

_CREATE_FLAGS = (os.O_EXCL |
                 os.O_CREAT |
                 os.O_RDWR |
                 O_BINARY)


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
    return armor(sha1(randomBytes(64)).digest())[:16]



class _PathHelper:
    """
    Abstract helper class also used by ZipPath; implements certain utility
    methods.
    """

    def getContent(self):
        fp = self.open()
        try:
            return fp.read()
        finally:
            fp.close()


    def parents(self):
        """
        @return: an iterator of all the ancestors of this path, from the most
        recent (its immediate parent) to the root of its filesystem.
        """
        path = self
        parent = path.parent()
        # root.parent() == root, so this means "are we the root"
        while path != parent:
            yield parent
            path = parent
            parent = parent.parent()


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
        if self.isdir():
            for c in self.children():
                # we should first see if it's what we want, then we
                # can walk through the directory
                if (descend is None or descend(c)):
                    for subc in c.walk(descend):
                        if os.path.realpath(self.path).startswith(
                            os.path.realpath(subc.path)):
                            raise LinkError("Cycle in file graph.")
                        yield subc
                else:
                    yield c


    def sibling(self, path):
        """
        Return a L{FilePath} with the same directory as this instance but with a
        basename of C{path}.

        @param path: The basename of the L{FilePath} to return.
        @type path: C{str}

        @rtype: L{FilePath}
        """
        return self.parent().child(path)


    def descendant(self, segments):
        """
        Retrieve a child or child's child of this path.

        @param segments: A sequence of path segments as C{str} instances.

        @return: A L{FilePath} constructed by looking up the C{segments[0]}
            child of this path, the C{segments[1]} child of that path, and so
            on.

        @since: 10.2
        """
        path = self
        for name in segments:
            path = path.child(name)
        return path


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



class RWX(FancyEqMixin, object):
    """
    A class representing read/write/execute permissions for a single user
    category (i.e. user/owner, group, or other/world).  Instantiate with
    three boolean values: readable? writable? executable?.

    @type read: C{bool}
    @ivar read: Whether permission to read is given

    @type write: C{bool}
    @ivar write: Whether permission to write is given

    @type execute: C{bool}
    @ivar execute: Whether permission to execute is given

    @since: 11.1
    """
    compareAttributes = ('read', 'write', 'execute')
    def __init__(self, readable, writable, executable):
        self.read = readable
        self.write = writable
        self.execute = executable


    def __repr__(self):
        return "RWX(read=%s, write=%s, execute=%s)" % (
            self.read, self.write, self.execute)


    def shorthand(self):
        """
        Returns a short string representing the permission bits.  Looks like
        part of what is printed by command line utilities such as 'ls -l'
        (e.g. 'rwx')
        """
        returnval = ['r', 'w', 'x']
        i = 0
        for val in (self.read, self.write, self.execute):
            if not val:
                returnval[i] = '-'
            i += 1
        return ''.join(returnval)



class Permissions(FancyEqMixin, object):
    """
    A class representing read/write/execute permissions.  Instantiate with any
    portion of the file's mode that includes the permission bits.

    @type user: L{RWX}
    @ivar user: User/Owner permissions

    @type group: L{RWX}
    @ivar group: Group permissions

    @type other: L{RWX}
    @ivar other: Other/World permissions

    @since: 11.1
    """

    compareAttributes = ('user', 'group', 'other')

    def __init__(self, statModeInt):
        self.user, self.group, self.other = (
            [RWX(*[statModeInt & bit > 0 for bit in bitGroup]) for bitGroup in
             [[S_IRUSR, S_IWUSR, S_IXUSR],
              [S_IRGRP, S_IWGRP, S_IXGRP],
              [S_IROTH, S_IWOTH, S_IXOTH]]]
        )


    def __repr__(self):
        return "[%s | %s | %s]" % (
            str(self.user), str(self.group), str(self.other))


    def shorthand(self):
        """
        Returns a short string representing the permission bits.  Looks like
        what is printed by command line utilities such as 'ls -l'
        (e.g. 'rwx-wx--x')
        """
        return "".join(
            [x.shorthand() for x in (self.user, self.group, self.other)])



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
    @ivar alwaysCreate: When opening this file, only succeed if the file does
        not already exist.

    @type path: C{str}
    @ivar path: The path from which 'downward' traversal is permitted.

    @ivar statinfo: The currently cached status information about the file on
        the filesystem that this L{FilePath} points to.  This attribute is
        C{None} if the file is in an indeterminate state (either this
        L{FilePath} has not yet had cause to call C{stat()} yet or
        L{FilePath.changed} indicated that new information is required), 0 if
        C{stat()} was called and returned an error (i.e. the path did not exist
        when C{stat()} was called), or a C{stat_result} object that describes
        the last known status of the underlying file (or directory, as the case
        may be).  Trust me when I tell you that you do not want to use this
        attribute.  Instead, use the methods on L{FilePath} which give you
        information about it, like C{getsize()}, C{isdir()},
        C{getModificationTime()}, and so on.
    @type statinfo: C{int} or L{types.NoneType} or L{os.stat_result}
    """

    statinfo = None
    path = None

    def __init__(self, path, alwaysCreate=False):
        """
        Convert a path string to an absolute path if necessary and initialize
        the L{FilePath} with the result.
        """
        self.path = abspath(path)
        self.alwaysCreate = alwaysCreate

    def __getstate__(self):
        """
        Support serialization by discarding cached L{os.stat} results and
        returning everything else.
        """
        d = self.__dict__.copy()
        if d.has_key('statinfo'):
            del d['statinfo']
        return d


    def child(self, path):
        """
        Create and return a new L{FilePath} representing a path contained by
        C{self}.

        @param path: The base name of the new L{FilePath}.  If this contains
            directory separators or parent references it will be rejected.
        @type path: C{str}

        @raise InsecurePath: If the result of combining this path with C{path}
            would result in a path which is not a direct child of this path.
        """
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
        """
        Open this file using C{mode} or for writing if C{alwaysCreate} is
        C{True}.

        In all cases the file is opened in binary mode, so it is not necessary
        to include C{b} in C{mode}.

        @param mode: The mode to open the file in.  Default is C{r}.
        @type mode: C{str}
        @raises AssertionError: If C{a} is included in the mode and
            C{alwaysCreate} is C{True}.
        @rtype: C{file}
        @return: An open C{file} object.
        """
        if self.alwaysCreate:
            assert 'a' not in mode, ("Appending not supported when "
                                     "alwaysCreate == True")
            return self.create()
        # This hack is necessary because of a bug in Python 2.7 on Windows:
        # http://bugs.python.org/issue7686
        mode = mode.replace('b', '')
        return open(self.path, mode + 'b')

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


    def changed(self):
        """
        Clear any cached information about the state of this path on disk.

        @since: 10.1.0
        """
        self.statinfo = None


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


    def getInodeNumber(self):
        """
        Retrieve the file serial number, also called inode number, which 
        distinguishes this file from all other files on the same device.

        @raise: NotImplementedError if the platform is Windows, since the
                inode number would be a dummy value for all files in Windows
        @return: a number representing the file serial number
        @rtype: C{long}
        @since: 11.0
        """
        if platform.isWindows():
            raise NotImplementedError

        st = self.statinfo
        if not st:
            self.restat()
            st = self.statinfo
        return long(st.st_ino)


    def getDevice(self):
        """
        Retrieves the device containing the file.  The inode number and device
        number together uniquely identify the file, but the device number is
        not necessarily consistent across reboots or system crashes.

        @raise: NotImplementedError if the platform is Windows, since the
                device number would be 0 for all partitions on a Windows
                platform
        @return: a number representing the device
        @rtype: C{long}
        @since: 11.0
        """
        if platform.isWindows():
            raise NotImplementedError

        st = self.statinfo
        if not st:
            self.restat()
            st = self.statinfo
        return long(st.st_dev)


    def getNumberOfHardLinks(self):
        """
        Retrieves the number of hard links to the file.  This count keeps
        track of how many directories have entries for this file.  If the
        count is ever decremented to zero then the file itself is discarded
        as soon as no process still holds it open.  Symbolic links are not
        counted in the total.

        @raise: NotImplementedError if the platform is Windows, since Windows
                doesn't maintain a link count for directories, and os.stat
                does not set st_nlink on Windows anyway.
        @return: the number of hard links to the file
        @rtype: C{int}
        @since: 11.0
        """
        if platform.isWindows():
            raise NotImplementedError

        st = self.statinfo
        if not st:
            self.restat()
            st = self.statinfo
        return int(st.st_nlink)


    def getUserID(self):
        """
        Returns the user ID of the file's owner.

        @raise: NotImplementedError if the platform is Windows, since the UID
                is always 0 on Windows
        @return: the user ID of the file's owner
        @rtype: C{int}
        @since: 11.0
        """
        if platform.isWindows():
            raise NotImplementedError

        st = self.statinfo
        if not st:
            self.restat()
            st = self.statinfo
        return int(st.st_uid)


    def getGroupID(self):
        """
        Returns the group ID of the file.

        @raise: NotImplementedError if the platform is Windows, since the GID
                is always 0 on windows
        @return: the group ID of the file
        @rtype: C{int}
        @since: 11.0
        """
        if platform.isWindows():
            raise NotImplementedError

        st = self.statinfo
        if not st:
            self.restat()
            st = self.statinfo
        return int(st.st_gid)


    def getPermissions(self):
        """
        Returns the permissions of the file.  Should also work on Windows,
        however, those permissions may not what is expected in Windows.

        @return: the permissions for the file
        @rtype: L{Permissions}
        @since: 11.1
        """
        st = self.statinfo
        if not st:
            self.restat()
            st = self.statinfo
        return Permissions(S_IMODE(st.st_mode))


    def exists(self):
        """
        Check if this L{FilePath} exists.

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
        """
        @return: C{True} if this L{FilePath} refers to a directory, C{False}
            otherwise.
        """
        st = self.statinfo
        if not st:
            self.restat(False)
            st = self.statinfo
            if not st:
                return False
        return S_ISDIR(st.st_mode)


    def isfile(self):
        """
        @return: C{True} if this L{FilePath} points to a regular file (not a
            directory, socket, named pipe, etc), C{False} otherwise.
        """
        st = self.statinfo
        if not st:
            self.restat(False)
            st = self.statinfo
            if not st:
                return False
        return S_ISREG(st.st_mode)


    def isBlockDevice(self):
        """
        Returns whether the underlying path is a block device.

        @return: C{True} if it is a block device, C{False} otherwise 
        @rtype: C{bool}
        @since: 11.1
        """
        st = self.statinfo
        if not st:
            self.restat(False)
            st = self.statinfo
            if not st:
                return False
        return S_ISBLK(st.st_mode)


    def isSocket(self):
        """
        Returns whether the underlying path is a socket.

        @return: C{True} if it is a socket, C{False} otherwise 
        @rtype: C{bool}
        @since: 11.1
        """
        st = self.statinfo
        if not st:
            self.restat(False)
            st = self.statinfo
            if not st:
                return False
        return S_ISSOCK(st.st_mode)


    def islink(self):
        """
        @return: C{True} if this L{FilePath} points to a symbolic link.
        """
        # We can't use cached stat results here, because that is the stat of
        # the destination - (see #1773) which in *every case* but this one is
        # the right thing to use.  We could call lstat here and use that, but
        # it seems unlikely we'd actually save any work that way.  -glyph
        return islink(self.path)


    def isabs(self):
        """
        @return: C{True}, always.
        """
        return isabs(self.path)


    def listdir(self):
        """
        List the base names of the direct children of this L{FilePath}.

        @return: a C{list} of C{str} giving the names of the contents of the
            directory this L{FilePath} refers to.  These names are relative to
            this L{FilePath}.

        @raise: Anything the platform C{os.listdir} implementation might raise
            (typically OSError).
        """
        return listdir(self.path)


    def splitext(self):
        """
        @return: tuple where the first item is the filename and second item is
            the file extension. See Python docs for C{os.path.splitext}
        """
        return splitext(self.path)


    def __repr__(self):
        return 'FilePath(%r)' % (self.path,)


    def touch(self):
        """
        Update the access and modified times of the L{FilePath}'s file.
        """
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
        self.changed()


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
        """
        @return: The final component of the L{FilePath}'s path (Everything after
            the final path separator).
        @rtype: C{str}
        """
        return basename(self.path)


    def dirname(self):
        """
        @return: All of the components of the L{FilePath}'s path except the last
            one (everything up to the final path separator).
        @rtype: C{str}
        """
        return dirname(self.path)


    def parent(self):
        """
        @return: A L{FilePath} representing the path which directly contains
            this L{FilePath}.
        """
        return self.clonePath(self.dirname())


    def setContent(self, content, ext='.new'):
        """
        Replace the file at this path with a new file that contains the given
        bytes, trying to avoid data-loss in the meanwhile.

        On UNIX-like platforms, this method does its best to ensure that by the
        time this method returns, either the old contents I{or} the new contents
        of the file will be present at this path for subsequent readers
        regardless of premature device removal, program crash, or power loss,
        making the following assumptions:

            - your filesystem is journaled (i.e. your filesystem will not
              I{itself} lose data due to power loss)

            - your filesystem's C{rename()} is atomic

            - your filesystem will not discard new data while preserving new
              metadata (see U{http://mjg59.livejournal.com/108257.html} for more
              detail)

        On most versions of Windows there is no atomic C{rename()} (see
        U{http://bit.ly/win32-overwrite} for more information), so this method
        is slightly less helpful.  There is a small window where the file at
        this path may be deleted before the new file is moved to replace it:
        however, the new file will be fully written and flushed beforehand so in
        the unlikely event that there is a crash at that point, it should be
        possible for the user to manually recover the new version of their data.
        In the future, Twisted will support atomic file moves on those versions
        of Windows which I{do} support them: see U{Twisted ticket
        3004<http://twistedmatrix.com/trac/ticket/3004>}.

        This method should be safe for use by multiple concurrent processes, but
        note that it is not easy to predict which process's contents will
        ultimately end up on disk if they invoke this method at close to the
        same time.

        @param content: The desired contents of the file at this path.

        @type content: L{str}

        @param ext: An extension to append to the temporary filename used to
            store the bytes while they are being written.  This can be used to
            make sure that temporary files can be identified by their suffix,
            for cleanup in case of crashes.

        @type ext: C{str}
        """
        sib = self.temporarySibling(ext)
        f = sib.open('w')
        try:
            f.write(content)
        finally:
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
        """
        Create the directory the L{FilePath} refers to.

        @see: L{makedirs}

        @raise OSError: If the directory cannot be created.
        """
        os.mkdir(self.path)


    def requireCreate(self, val=1):
        self.alwaysCreate = val


    def create(self):
        """
        Exclusively create a file, only if this file previously did not exist.
        """
        fdint = os.open(self.path, _CREATE_FLAGS)

        # XXX TODO: 'name' attribute of returned files is not mutable or
        # settable via fdopen, so this file is slighly less functional than the
        # one returned from 'open' by default.  send a patch to Python...

        return os.fdopen(fdint, 'w+b')


    def temporarySibling(self, extension=""):
        """
        Construct a path referring to a sibling of this path.

        The resulting path will be unpredictable, so that other subprocesses
        should neither accidentally attempt to refer to the same path before it
        is created, nor they should other processes be able to guess its name in
        advance.

        @param extension: A suffix to append to the created filename.  (Note
            that if you want an extension with a '.' you must include the '.'
            yourself.)

        @type extension: C{str}

        @return: a path object with the given extension suffix, C{alwaysCreate}
            set to True.

        @rtype: L{FilePath}
        """
        sib = self.sibling(_secureEnoughString() + self.basename() + extension)
        sib.requireCreate()
        return sib


    _chunkSize = 2 ** 2 ** 2 ** 2

    def copyTo(self, destination, followLinks=True):
        """
        Copies self to destination.

        If self doesn't exist, an OSError is raised.

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
            try:
                readfile = self.open()
                try:
                    while 1:
                        # XXX TODO: optionally use os.open, os.read and O_DIRECT
                        # and use os.fstatvfs to determine chunk sizes and make
                        # *****sure**** copy is page-atomic; the following is
                        # good enough for 99.9% of everybody and won't take a
                        # week to audit though.
                        chunk = readfile.read(self._chunkSize)
                        writefile.write(chunk)
                        if len(chunk) < self._chunkSize:
                            break
                finally:
                    readfile.close()
            finally:
                writefile.close()
        elif not self.exists():
            raise OSError(errno.ENOENT, "No such file or directory")
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
        else:
            self.changed()
            destination.changed()


FilePath.clonePath = FilePath
