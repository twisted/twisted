"""An extremely asynch approach to unzipping files.  This allows you
to unzip a little bit of a file at a time, which means it can
integrate nicely with a reactor.

"""

from __future__ import generators

import zipfile
import os.path
import binascii
import zlib

class ChunkingZipFile(zipfile.ZipFile):
    """A ZipFile object which, with readfile(), also gives you access
    to a filelike object for each entry.
    """
    def readfile(self, name):
        """Return file-like object for name."""
        if self.mode not in ("r", "a"):
            raise RuntimeError, 'read() requires mode "r" or "a"'
        if not self.fp:
            raise RuntimeError, \
                  "Attempt to read ZIP archive that was already closed"
        zinfo = self.getinfo(name)
        self.fp.seek(zinfo.file_offset, 0)
        if zinfo.compress_type == zipfile.ZIP_STORED:
            return ZipFileEntry(self.fp, zinfo.compress_size)
        elif zinfo.compress_type == zipfile.ZIP_DEFLATED:
            if not zlib:
                raise RuntimeError, \
                      "De-compression requires the (missing) zlib module"
            return DeflatedZipFileEntry(self.fp, zinfo.compress_size)
        else:
            raise zipfile.BadZipfile, \
                  "Unsupported compression method %d for file %s" % \
            (zinfo.compress_type, name)
    
    def read(self, name):
        """Return file bytes (as a string) for name."""
        f = self.readfile(name)
        zinfo = self.getinfo(name)
        bytes = f.read()
        crc = binascii.crc32(bytes)
        if crc != zinfo.CRC:
            raise BadZipfile, "Bad CRC-32 for file %s" % name
        return bytes        


class ZipFileEntry:
    """File-like object used to read an uncompressed entry in a ZipFile"""
    
    def __init__(self, fp, length):
        self.fp = fp
        self.readBytes = 0
        self.length = length
        self.finished = 0
        
    def tell(self):
        return self.readBytes
    
    def read(self, n=None):
        if n is None:
            n = self.length - self.readBytes
        if n == 0 or self.finished:
            return ''
        
        data = self.fp.read(min(n, self.length - self.readBytes))
        self.readBytes += len(data)
        if self.readBytes == self.length or len(data) <  n:
            self.finished = 1
        return data

    def close(self):
        self.finished = 1
        del self.fp


class DeflatedZipFileEntry:
    """File-like object used to read a deflated entry in a ZipFile"""
    
    def __init__(self, fp, length):
        self.fp = fp
        self.returnedBytes = 0
        self.readBytes = 0
        self.decomp = zlib.decompressobj(-15)
        self.buffer = ""
        self.length = length
        self.finished = 0
        
    def tell(self):
        return self.returnedBytes
    
    def read(self, n=None):
        if self.finished:
            return ""
        if n is None:
            result = [self.buffer,]
            result.append(self.decomp.decompress(self.fp.read(self.length - self.readBytes)))
            result.append(self.decomp.decompress("Z"))
            result.append(self.decomp.flush())
            self.buffer = ""
            self.finished = 1
            result = "".join(result)
            self.returnedBytes += len(result)
            return result
        else:
            while len(self.buffer) < n:
                data = self.fp.read(min(n, 1024, self.length - self.readBytes))
                self.readBytes += len(data)
                if not data:
                    result = self.buffer + self.decomp.decompress("Z") + self.decomp.flush()
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
    
    def close(self):
        self.finished = 1
        del self.fp


def unzip(filename, directory=".", overwrite=0):
    """Unzip the file
    @param filename: the name of the zip file
    @param directory: the directory into which the files will be
    extracted
    @param overwrite: if on, overwrite files when they exist.  You can
    still get an error if you try to create a directory over a file
    with the same name or vice-versa.
    """
    for i in unzipIter(filename, directory, overwrite):
        pass

DIR_BIT=16
def unzipIter(filename, directory='.', overwrite=0):
    """Return a generator for the zipfile.  This implementation will
    yield after every file.

    The value it yields is the number of files left to unzip.
    """
    zf=zipfile.ZipFile(filename, 'r')
    names=zf.namelist()
    if not os.path.exists(directory): os.makedirs(directory)
    remaining=countZipFileEntries(filename)
    for entry in names:
        remaining=remaining - 1
        isdir=zf.getinfo(entry).external_attr & DIR_BIT
        f=os.path.join(directory, entry)
        if isdir:
            # overwrite flag only applies to files
            if not os.path.exists(f): os.makedirs(f)
        else:
            # create the directory the file will be in first,
            # since we can't guarantee it exists
            fdir=os.path.split(f)[0]
            if not os.path.exists(fdir):
                os.makedirs(f)
            if overwrite or not os.path.exists(f):
                outfile=file(f, 'wb')
                outfile.write(zf.read(entry))
                outfile.close()
        yield remaining

def countZipFileChunks(filename, chunksize):
    """Predict the number of chunks that will be extracted from the
    entire zipfile, given chunksize blocks.
    """
    totalchunks=0
    zf=ChunkingZipFile(filename)
    for info in zf.infolist():
        totalchunks=totalchunks+countFileChunks(info, chunksize)
    return totalchunks

def countFileChunks(zipinfo, chunksize):
    size=zipinfo.file_size
    count=size/chunksize
    if size%chunksize > 0:
        count=count+1
    # each file counts as at least one chunk
    return count or 1
    
def countZipFileEntries(filename):
    zf=zipfile.ZipFile(filename)
    return len(zf.namelist())

def unzipIterChunky(filename, directory='.', overwrite=0,
                    chunksize=4096):
    """Return a generator for the zipfile.  This implementation will
    yield after every chunksize uncompressed bytes, or at the end of a
    file, whichever comes first.

    The value it yields is the number of chunks left to unzip.
    """
    czf=ChunkingZipFile(filename, 'r')
    if not os.path.exists(directory): os.makedirs(directory)
    remaining=countZipFileChunks(filename, chunksize)
    names=czf.namelist()
    infos=czf.infolist()
    
    for entry, info in zip(names, infos):
        isdir=info.external_attr & DIR_BIT
        f=os.path.join(directory, entry)
        if isdir:
            # overwrite flag only applies to files
            if not os.path.exists(f): os.makedirs(f)
            remaining=remaining-1
            assert remaining>=0
            yield remaining
        else:
            # create the directory the file will be in first,
            # since we can't guarantee it exists
            fdir=os.path.split(f)[0]
            if not os.path.exists(fdir):
                os.makedirs(f)
            if overwrite or not os.path.exists(f):
                outfile=file(f, 'wb')
                fp=czf.readfile(entry)
                if info.file_size==0:
                    remaining=remaining-1
                    assert remaining>=0
                    yield remaining
                fread=fp.read
                ftell=fp.tell
                owrite=outfile.write
                size=info.file_size
                while ftell() < size:
                    hunk=fread(chunksize)
                    owrite(hunk)
                    remaining=remaining-1
                    assert remaining>=0
                    yield remaining
                outfile.close()
            else:
                remaining=remaining-countFileChunks(info, chunksize)
                assert remaining>=0
                yield remaining
