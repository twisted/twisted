# -*- test-case-name: twisted.test.test_paths.ZipFilePathTestCase -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This module contains implementations of IFilePath for zip files.

See the constructor for ZipArchive for use.
"""
from __future__ import print_function, division, absolute_import

__metaclass__ = type

import os
import time
import errno


# Python 2.6 includes support for incremental unzipping of zipfiles, and
# thus obviates the need for ChunkingZipFile.
import sys
if sys.version_info[:2] >= (2, 6):
    _USE_ZIPFILE = True
    from zipfile import ZipFile
else:
    _USE_ZIPFILE = False
    from twisted.python.zipstream import ChunkingZipFile

from twisted.python.filepath import IFilePath, FilePath, AbstractFilePath

from zope.interface import implementer

# Using FilePath here exclusively rather than os to make sure that we don't do
# anything OS-path-specific here.

ZIP_PATH_SEP = b'/'             # In zipfiles, "/" is universally used as the
                                # path separator, regardless of platform.

ENCODING = sys.getfilesystemencoding()


@implementer(IFilePath)
class ZipPath(AbstractFilePath):
    """
    I represent a file or directory contained within a zip file.
    """

    sep = ZIP_PATH_SEP

    def __init__(self, archive, pathInArchive):
        """
        Don't construct me directly.  Use ZipArchive.child().

        @param archive: a ZipArchive instance.

        @param pathInArchive: a ZIP_PATH_SEP-separated string.
        """
        self.archive = archive

        # Keep pathInArchive as bytes
        if isinstance(pathInArchive, bytes):
            self.pathInArchive = pathInArchive
        else:
            self.pathInArchive = pathInArchive.encode(ENCODING)

        # self.path pretends to be os-specific because that's the way the
        # 'zipimport' module does it.
        self.path = os.path.join(archive.zipfile.filename.encode(),
                                 *(self.pathInArchive.split(ZIP_PATH_SEP)))

    def __cmp__(self, other):
        if not isinstance(other, ZipPath):
            return NotImplemented
        return cmp((self.archive, self.pathInArchive),
                   (other.archive, other.pathInArchive))


    def __repr__(self):
        parts = [os.path.abspath(self.archive.path)]
        parts.extend(self.pathInArchive.split(ZIP_PATH_SEP))
        path = os.sep.encode().join(parts)
        return "ZipPath(%r)" % (path,)


    def parent(self):
        splitup = self.pathInArchive.split(ZIP_PATH_SEP)
        if len(splitup) == 1:
            return self.archive
        return ZipPath(self.archive, ZIP_PATH_SEP.join(splitup[:-1]))


    def child(self, path):
        """
        Return a new ZipPath representing a path in C{self.archive} which is
        a child of this path.

        @note: Requesting the C{".."} (or other special name) child will not
            cause L{InsecurePath} to be raised since these names do not have
            any special meaning inside a zip archive.  Be particularly
            careful with the C{path} attribute (if you absolutely must use
            it) as this means it may include special names with special
            meaning outside of the context of a zip archive.
        """
        try:
            encodedPath = path.encode(ENCODING)
        except AttributeError:
            encodedPath = path

        return ZipPath(self.archive,
                       ZIP_PATH_SEP.join([self.pathInArchive, encodedPath]))


    def sibling(self, path):
        return self.parent().child(path)

    # preauthChild = child

    def exists(self):
        return self.isdir() or self.isfile()

    def isdir(self):
        return self.pathInArchive in self.archive.childmap

    def isfile(self):
        return self.pathInArchive in self.archive.zipfile.NameToInfo

    def islink(self):
        return False

    def listdir(self):
        if self.exists():
            if self.isdir():
                # py3's dict().keys() is no longer a list
                return list(self.archive.childmap[self.pathInArchive])
            else:
                raise OSError(errno.ENOTDIR, "Leaf zip entry listed")
        else:
            raise OSError(errno.ENOENT, "Non-existent zip entry listed")


    def splitext(self):
        """
        Return a value similar to that returned by os.path.splitext.
        """
        # This happens to work out because of the fact that we use OS-specific
        # path separators in the constructor to construct our fake 'path'
        # attribute.
        return os.path.splitext(self.path)


    def basename(self):
        return self.pathInArchive.split(ZIP_PATH_SEP)[-1]


    def dirname(self):
        # XXX NOTE: This API isn't a very good idea on filepath, but it's even
        # less meaningful here.
        return self.parent().path


    def open(self, mode="r"):
        if _USE_ZIPFILE:
            return self.archive.zipfile.open(
                self.pathInArchive.decode(ENCODING), mode=mode)
        else:
            # XXX oh man, is this too much hax?
            self.archive.zipfile.mode = mode
            return self.archive.zipfile.readfile(
                self.pathInArchive.decode(ENCODING))

    def changed(self):
        pass

    def getsize(self):
        """
        Retrieve this file's size.

        @return: file size, in bytes
        """

        pathInArchive = self.pathInArchive.decode(ENCODING)
        return self.archive.zipfile.NameToInfo[pathInArchive].file_size

    def getAccessTime(self):
        """
        Retrieve this file's last access-time.  This is the same as the last access
        time for the archive.

        @return: a number of seconds since the epoch
        """
        return self.archive.getAccessTime()


    def getModificationTime(self):
        """
        Retrieve this file's last modification time.  This is the time of
        modification recorded in the zipfile.

        @return: a number of seconds since the epoch.
        """
        pathInArchive = self.pathInArchive.decode(ENCODING)
        return time.mktime(
            self.archive.zipfile.NameToInfo[pathInArchive].date_time
            + (0, 0, 0))


    def getStatusChangeTime(self):
        """
        Retrieve this file's last modification time.  This name is provided for
        compatibility, and returns the same value as getmtime.

        @return: a number of seconds since the epoch.
        """
        return self.getModificationTime()



class ZipArchive(ZipPath):
    """ I am a FilePath-like object which can wrap a zip archive as if it were
    a directory.
    """
    archive = property(lambda self: self)
    def __init__(self, archivePathname):
        """Create a ZipArchive, treating the archive at archivePathname as a
        zip file.

        @param archivePathname: a str, naming a path in the filesystem.
        """

        # convert to string because python3 ZipFile doesn't take bytes
        if isinstance(archivePathname, bytes):
            archivePathname = archivePathname.decode(ENCODING)

        if _USE_ZIPFILE:
            self.zipfile = ZipFile(archivePathname)
        else:
            self.zipfile = ChunkingZipFile(archivePathname)
        try:
            self.path = archivePathname.encode(ENCODING)
        except AttributeError:
            self.path = archivePathname

        self.pathInArchive = b''
        # zipfile is already wasting O(N) memory on cached ZipInfo instances,
        # so there's no sense in trying to do this lazily or intelligently
        self.childmap = {}      # map parent: list of children

        for name in self.zipfile.namelist():
            name = name.split(ZIP_PATH_SEP.decode())
            for x in range(len(name)):
                child = name[-x]
                parent = ZIP_PATH_SEP.decode().join(name[:-x])
                # convert back to bytes to reflect correct file path api
                parent = parent.encode(ENCODING)
                child = child.encode(ENCODING)
                if parent not in self.childmap:
                    self.childmap[parent] = {}
                self.childmap[parent][child] = 1
            parent = ''

    def child(self, path):
        """
        Create a ZipPath pointing at a path within the archive.

        @param path: a str with no path separators in it, either '/' or the
        system path separator, if it's different.
        """
        return ZipPath(self, path)

    def exists(self):
        """
        Returns true if the underlying archive exists.
        """
        return FilePath(self.zipfile.filename).exists()


    def getAccessTime(self):
        """
        Return the archive file's last access time.
        """
        return FilePath(self.zipfile.filename).getAccessTime()


    def getModificationTime(self):
        """
        Return the archive file's modification time.
        """
        return FilePath(self.zipfile.filename).getModificationTime()


    def getStatusChangeTime(self):
        """
        Return the archive file's status change time.
        """
        return FilePath(self.zipfile.filename).getStatusChangeTime()


    def __repr__(self):
        return 'ZipArchive(%r)' % (os.path.abspath(self.path),)


__all__ = ['ZipArchive', 'ZipPath']
