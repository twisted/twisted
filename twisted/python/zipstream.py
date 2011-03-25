# -*- test-case-name: twisted.python.test.test_zipstream -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An incremental approach to unzipping files.  This allows you to unzip a little
bit of a file at a time, which means you can report progress as a file unzips.
"""

import warnings
import zipfile
import os.path
import zlib
import struct

_fileHeaderSize = struct.calcsize(zipfile.structFileHeader)

class ChunkingZipFile(zipfile.ZipFile):
    """
    A ZipFile object which, with readfile(), also gives you access to a
    filelike object for each entry.
    """

    def readfile(self, name):
        """
        Return file-like object for name.
        """
        if self.mode not in ("r", "a"):
            raise RuntimeError('read() requires mode "r" or "a"')
        if not self.fp:
            raise RuntimeError(
                "Attempt to read ZIP archive that was already closed")
        zinfo = self.getinfo(name)

        self.fp.seek(zinfo.header_offset, 0)

        fheader = self.fp.read(_fileHeaderSize)
        if fheader[0:4] != zipfile.stringFileHeader:
            raise zipfile.BadZipfile("Bad magic number for file header")

        fheader = struct.unpack(zipfile.structFileHeader, fheader)
        fname = self.fp.read(fheader[zipfile._FH_FILENAME_LENGTH])

        if fheader[zipfile._FH_EXTRA_FIELD_LENGTH]:
            self.fp.read(fheader[zipfile._FH_EXTRA_FIELD_LENGTH])

        if fname != zinfo.orig_filename:
            raise zipfile.BadZipfile(
                'File name in directory "%s" and header "%s" differ.' % (
                    zinfo.orig_filename, fname))

        if zinfo.compress_type == zipfile.ZIP_STORED:
            return ZipFileEntry(self, zinfo.compress_size)
        elif zinfo.compress_type == zipfile.ZIP_DEFLATED:
            return DeflatedZipFileEntry(self, zinfo.compress_size)
        else:
            raise zipfile.BadZipfile(
                "Unsupported compression method %d for file %s" %
                    (zinfo.compress_type, name))



class _FileEntry(object):
    """
    Abstract superclass of both compressed and uncompressed variants of
    file-like objects within a zip archive.

    @ivar chunkingZipFile: a chunking zip file.
    @type chunkingZipFile: L{ChunkingZipFile}

    @ivar length: The number of bytes within the zip file that represent this
    file.  (This is the size on disk, not the number of decompressed bytes
    which will result from reading it.)

    @ivar fp: the underlying file object (that contains pkzip data).  Do not
    touch this, please.  It will quite likely move or go away.

    @ivar closed: File-like 'closed' attribute; True before this file has been
    closed, False after.
    @type closed: L{bool}

    @ivar finished: An older, broken synonym for 'closed'.  Do not touch this,
    please.
    @type finished: L{int}
    """
    def __init__(self, chunkingZipFile, length):
        """
        Create a L{_FileEntry} from a L{ChunkingZipFile}.
        """
        self.chunkingZipFile = chunkingZipFile
        self.fp = self.chunkingZipFile.fp
        self.length = length
        self.finished = 0
        self.closed = False


    def isatty(self):
        """
        Returns false because zip files should not be ttys
        """
        return False


    def close(self):
        """
        Close self (file-like object)
        """
        self.closed = True
        self.finished = 1
        del self.fp


    def readline(self):
        """
        Read a line.
        """
        bytes = ""
        for byte in iter(lambda : self.read(1), ""):
            bytes += byte
            if byte == "\n":
                break
        return bytes


    def next(self):
        """
        Implement next as file does (like readline, except raises StopIteration
        at EOF)
        """
        nextline = self.readline()
        if nextline:
            return nextline
        raise StopIteration()


    def readlines(self):
        """
        Returns a list of all the lines
        """
        return list(self)


    def xreadlines(self):
        """
        Returns an iterator (so self)
        """
        return self


    def __iter__(self):
        """
        Returns an iterator (so self)
        """
        return self



class ZipFileEntry(_FileEntry):
    """
    File-like object used to read an uncompressed entry in a ZipFile
    """

    def __init__(self, chunkingZipFile, length):
        _FileEntry.__init__(self, chunkingZipFile, length)
        self.readBytes = 0


    def tell(self):
        return self.readBytes


    def read(self, n=None):
        if n is None:
            n = self.length - self.readBytes
        if n == 0 or self.finished:
            return ''
        data = self.chunkingZipFile.fp.read(
            min(n, self.length - self.readBytes))
        self.readBytes += len(data)
        if self.readBytes == self.length or len(data) <  n:
            self.finished = 1
        return data



class DeflatedZipFileEntry(_FileEntry):
    """
    File-like object used to read a deflated entry in a ZipFile
    """

    def __init__(self, chunkingZipFile, length):
        _FileEntry.__init__(self, chunkingZipFile, length)
        self.returnedBytes = 0
        self.readBytes = 0
        self.decomp = zlib.decompressobj(-15)
        self.buffer = ""


    def tell(self):
        return self.returnedBytes


    def read(self, n=None):
        if self.finished:
            return ""
        if n is None:
            result = [self.buffer,]
            result.append(
                self.decomp.decompress(
                    self.chunkingZipFile.fp.read(
                        self.length - self.readBytes)))
            result.append(self.decomp.decompress("Z"))
            result.append(self.decomp.flush())
            self.buffer = ""
            self.finished = 1
            result = "".join(result)
            self.returnedBytes += len(result)
            return result
        else:
            while len(self.buffer) < n:
                data = self.chunkingZipFile.fp.read(
                    min(n, 1024, self.length - self.readBytes))
                self.readBytes += len(data)
                if not data:
                    result = (self.buffer
                              + self.decomp.decompress("Z")
                              + self.decomp.flush())
                    self.finished = 1
                    self.buffer = ""
                    self.returnedBytes += len(result)
                    return result
                else:
                    self.buffer += self.decomp.decompress(data)
            result = self.buffer[:n]
            self.buffer = self.buffer[n:]
            self.returnedBytes += len(result)
            return result



def unzip(filename, directory=".", overwrite=0):
    """
    Unzip the file

    @param filename: the name of the zip file
    @param directory: the directory into which the files will be
    extracted
    @param overwrite: if on, overwrite files when they exist.  You can
    still get an error if you try to create a directory over a file
    with the same name or vice-versa.
    """
    warnings.warn("zipstream.unzip is deprecated since Twisted 11.0.0 for " +
                  "security reasons.  Use Python's zipfile instead.",
                  category=DeprecationWarning, stacklevel=2)

    for i in unzipIter(filename, directory, overwrite, suppressWarning=True):
        pass

DIR_BIT = 16

def unzipIter(filename, directory='.', overwrite=0, suppressWarning=False):
    """
    Return a generator for the zipfile.  This implementation will yield
    after every file.

    The value it yields is the number of files left to unzip.
    """
    if not suppressWarning:
        warnings.warn("zipstream.unzipIter is deprecated since Twisted " +
                      "11.0.0 for security reasons.  Use Python's " +
                      "zipfile instead.",
                      category=DeprecationWarning, stacklevel=2)

    zf = zipfile.ZipFile(filename, 'r')
    names = zf.namelist()
    if not os.path.exists(directory):
        os.makedirs(directory)
    remaining = len(zf.namelist())
    for entry in names:
        remaining -= 1
        isdir = zf.getinfo(entry).external_attr & DIR_BIT
        f = os.path.join(directory, entry)
        if isdir:
            # overwrite flag only applies to files
            if not os.path.exists(f):
                os.makedirs(f)
        else:
            # create the directory the file will be in first,
            # since we can't guarantee it exists
            fdir = os.path.split(f)[0]
            if not os.path.exists(fdir):
                os.makedirs(fdir)
            if overwrite or not os.path.exists(f):
                outfile = file(f, 'wb')
                outfile.write(zf.read(entry))
                outfile.close()
        yield remaining


def countZipFileChunks(filename, chunksize):
    """
    Predict the number of chunks that will be extracted from the entire
    zipfile, given chunksize blocks.
    """
    totalchunks = 0
    zf = ChunkingZipFile(filename)
    for info in zf.infolist():
        totalchunks += countFileChunks(info, chunksize)
    return totalchunks


def countFileChunks(zipinfo, chunksize):
    """
    Count the number of chunks that will result from the given L{ZipInfo}.

    @param zipinfo: a L{zipfile.ZipInfo} instance describing an entry in a zip
    archive to be counted.

    @return: the number of chunks present in the zip file.  (Even an empty file
    counts as one chunk.)
    @rtype: L{int}
    """
    count, extra = divmod(zipinfo.file_size, chunksize)
    if extra > 0:
        count += 1
    return count or 1


def countZipFileEntries(filename):
    """
    Count the number of entries in a zip archive.  (Don't use this function.)

    @param filename: The filename of a zip archive.
    @type filename: L{str}
    """
    warnings.warn("countZipFileEntries is deprecated.",
                  DeprecationWarning, 2)
    zf = zipfile.ZipFile(filename)
    return len(zf.namelist())


def unzipIterChunky(filename, directory='.', overwrite=0,
                    chunksize=4096):
    """
    Return a generator for the zipfile.  This implementation will yield after
    every chunksize uncompressed bytes, or at the end of a file, whichever
    comes first.

    The value it yields is the number of chunks left to unzip.
    """
    czf = ChunkingZipFile(filename, 'r')
    if not os.path.exists(directory):
        os.makedirs(directory)
    remaining = countZipFileChunks(filename, chunksize)
    names = czf.namelist()
    infos = czf.infolist()

    for entry, info in zip(names, infos):
        isdir = info.external_attr & DIR_BIT
        f = os.path.join(directory, entry)
        if isdir:
            # overwrite flag only applies to files
            if not os.path.exists(f):
                os.makedirs(f)
            remaining -= 1
            yield remaining
        else:
            # create the directory the file will be in first,
            # since we can't guarantee it exists
            fdir = os.path.split(f)[0]
            if not os.path.exists(fdir):
                os.makedirs(fdir)
            if overwrite or not os.path.exists(f):
                outfile = file(f, 'wb')
                fp = czf.readfile(entry)
                if info.file_size == 0:
                    remaining -= 1
                    yield remaining
                while fp.tell() < info.file_size:
                    hunk = fp.read(chunksize)
                    outfile.write(hunk)
                    remaining -= 1
                    yield remaining
                outfile.close()
            else:
                remaining -= countFileChunks(info, chunksize)
                yield remaining
