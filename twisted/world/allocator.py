# -*- test-case-name: twisted.test.test_world -*-
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
#

from __future__ import generators

# Twisted Imports

from twisted.python import finalize

# Sibling Imports

from twisted.world.storable import Storable
from twisted.world.fileutils import openPlus
from twisted.world.structfile import StructuredFile
from twisted.world.util import BoundProxy

DEFAULT_MAX_ALLOCS = 5000                 # random number - currently small so testing is easy


class FragmentFile(Storable):
    __schema__ = {
        'maxAllocs': int,
        'longestFragment': int,
        'fragmentCount': int,
        'allocCount': int,
        'fileSize': int,
        'datafile': None,
        'fragments': None,
        'allocs': None,
    }

    def __init__(self, db):
        self.maxAllocs = DEFAULT_MAX_ALLOCS
        self.longestFragment = 0
        self.fragmentCount = 0
        self.allocCount = 0
        self.fileSize = 0
        db.insert(self)
        self.__awake__()

    def __awake__(self):
        _op = lambda x: openPlus(self.getDatabase().dirname, "fragments", str(self._inmem_oid) + "." + x)
        self.datafile = _op("data")
        fragmentsFile = _op("fragments")
        allocationsFile = _op("allocations")
##         for f in self.datafile, fragmentsFile, allocationsFile:
##             self.keepAlive(f)
        self.fragments = StructuredFile(fragmentsFile,
                                        (int, "offset"),
                                        (int, "length"))
        self.allocs = StructuredFile(allocationsFile,
                                     (int, "oid"),
                                     (int, "offset"),
                                     (int, "length"),
                                     maxLength=self.maxAllocs,
                                     ignoreSchema=True,
                                     )
        finalize.register(self)


    def getDataFile(self):
        """Bind datafile to me and return it.

        This makes it so that I do not accidentally go away while others are
        still holding references to my datafile.
        """
        return BoundProxy(self.datafile, self)

    def __finalizers__(self):
        return [self.datafile.close,
                self.fragments.close,
                self.allocs.close]

    def packFragments(self, begin):
        """Pack my fragment-space starting with a recently-freed fragment.
        """
        self.fragmentCount -= 1
        self.fragments.copyBlock(begin+1, begin, self.fragmentCount-begin)

    def _findOIDIndex(self, oid):
        for n in xrange(self.allocCount):
            # find the oid
            if self.allocs.getAt(n, "oid") == oid:
                return n

    def reallocateSpace(self, oid, begin, oldSize, newSize, allocIndex):
        """Attempt to expand some already-allocated space forwards (move its
        end to a higher location in the file).  This means we have to either
        find a fragment that's bumping up against the beginning or end of the
        already-allocated space, or the already-allocated space is touching the
        end of the file.  If my attempt to request more space was successful, I
        will return the allocated size, otherwise, None.
        """
        assert newSize > oldSize, "expanding only goes OUT"
        # first, let's see if we're at the end of the file.
        oldAllocEnd = (begin + oldSize)
        # allocIndex = self._findOIDIndex(oid)
        assert self.allocs.getAt(allocIndex, "oid") == oid, "OID %s claims to own space at %s in %s but does not" % (oid, begin, self)
        if oldAllocEnd == self.fileSize:
            self.allocs.setAt(allocIndex, "length", newSize)
            self.fileSize += (newSize - oldSize)
            return newSize
        else:
            x = 0
            while x < self.fragmentCount:
                oft = self.fragments.getAt(x, "offset")
                if oft == oldAllocEnd:
                    possibleSize = self.fragments.getAt(x, "length") + oldSize
                    if possibleSize >= newSize:
                        # TODO: possibly don't remove the fragment, just adjust its size
                        self.allocs.setAt(allocIndex, 'length', possibleSize)
                        self.packFragments(x)
                        return possibleSize
                x += 1
        return None

    def findSpace(self, oid, sz):
        """Allocate the given number of bytes.  If I can do it, return an
        (offset,actual) pair that is an offset into me and the amount of actual
        space allocated.  This may be more than requested.  The given OID in
        the same database as me is assumed to own this data chunk and may be
        asked to relocate it with the 'relocate' method.

        If I can't, return None.
        """
        # first, see if we are allowed to accept another allocation
        if (self.fragmentCount + self.allocCount) >= self.maxAllocs:
            return None
        x = 0
        while x < self.fragmentCount:
            offset, length = self.fragments[x]
            if length >= sz:
                allocIndex = self.allocCount
                self.allocCount = self.allocCount + 1
                self.allocs[allocIndex] = oid, offset, length
                # TODO: we shouldn't ALWAYS kill the whole fragment.  depending
                # on some heuristics (the lack of which is why this TODO isn't
                # implemented) we should shorten the fragment towards the
                # beginning or end but not necessarily eliminate it.
                rtrn = offset, length, allocIndex
                self.packFragments(x)
                return rtrn
            x += 1
        # just chop some space at the end of the file
        offset = self.fileSize
        allocIndex = self.allocCount
        self.allocCount += 1
        self.allocs[allocIndex] = oid, offset, sz
        self.fileSize += sz
        return offset, sz, allocIndex

    def overlapSanityCheck(self):
        # l = [0] * self.fileSize
        l = [[] for x in xrange(self.fileSize)]
        for allocidx in xrange(self.allocCount):
            oid, bytebegin, sz = self.allocs[allocidx]
            byteend = bytebegin + sz
            for byteidx in range(bytebegin, byteend):
                l[byteidx].append(oid)
        for fragmentidx in xrange(self.fragmentCount):
            offset, sz = self.fragments[fragmentidx]
            oid = -1
            end = offset + sz
            for byteidx in range(offset,end):
                l[byteidx].append(-1)
        rv = 1
        for bi in range(len(l)):
            b = l[bi]
            if len(b) > 1:
                print bi, b
                rv = 0
##         if not rv:
##             import pdb
##             pdb.set_trace()
        return rv


    def free(self, oid, offset, sz, dx):
        aoid, aoffset, asz = self.allocs[dx]
        assert ((asz == sz) and (offset == aoffset) and aoid == oid), (
            "allocated size reported by object "
            "and by fragment file are not the same")
        self.allocs[dx] = 0, 0, 0
        if dx == (self.allocCount - 1):
            self.allocCount -= 1
        self.fragments[self.fragmentCount] = aoffset, asz
        self.fragmentCount += 1
        return

def _fliter(db):
    fls = db.queryClassSelect(FragmentFile)
    for fl in fls:
        yield fl
    yield FragmentFile(db)

class Allocation(Storable):
    """I am an object that allocates some space.
    """
    __schema__ = {
        'fragfile': FragmentFile,
        'allocBegin': int, # beginning (offset in bytes) of allocated space
        'allocLength': int, # length (in bytes) of allocated space
        'allocIndex': int, # index (in records) of alloc record in fragfile
        'contentLength': int, # length of content (in bytes) within allocation
    }

    def __init__(self, db, initialPad=10):
        self.fragfile = None
        self.allocBegin = 0
        self.allocLength = 0
        self.contentLength = 0
        self.allocIndex = 0
        db.insert(self)
        self.findFragFile(initialPad)
        self.__awake__()

    def findFragFile(self, howBig):
        """I may or may not have a fragment file.  Allocate some space in one
        for me.
        """
        if howBig == 0:
            if self.fragfile is not None:
                self.free()
                self.fragfile = None
            else:
                self.allocLength = 0
                self.allocBegin = 0
                self.allocIndex = 0
                self.contentLength = 0
            return
        db = self.getDatabase()
        fragFiles = _fliter(db)
        # TODO: scale better...
        for fl in fragFiles:
            sp = fl.findSpace(self._inmem_oid, howBig)
            if sp is not None:
                offset, actual, index = sp
                self.allocBegin = offset
                self.allocLength = actual
                self.allocIndex = index
                self.fragfile = fl
                break

    def getDataFile(self):
        if self.fragfile is None:
            import cStringIO
            return cStringIO.StringIO('')
        else:
            return self.fragfile.getDataFile()
##         return WindowCheckingFile(self.fragfile.getDataFile(),
##                                   self.allocBegin, self.allocBegin + self.allocLength)

    def expand(self, howMuch=None):
        """I have some space in a fragment file, but I need more.
        """
        if howMuch is None:
            howMuch = self.allocLength
        if howMuch == 0:
            howMuch = 10 # small initial pad
        oldAllocBegin = self.allocBegin
        oldAllocLength = self.allocLength
        oldAllocIndex = self.allocIndex
        oldFragFile = self.fragfile
        dat = None
        if self.fragfile is not None:
            dat = self.fragfile.reallocateSpace(self._inmem_oid,
                                                oldAllocBegin, oldAllocLength,
                                                self.allocLength + howMuch,
                                                self.allocIndex)
            if dat is not None:
                # best case: we don't have to copy anything
                self.allocLength = dat
                return
            dat = self.fragfile.findSpace(self._inmem_oid,
                                           self.allocLength + howMuch)
            if dat is not None:
                # slightly worse case: we have to move the data within a file
                offset, length, index = dat
                olddf = self.getDataFile()
                self.allocBegin = offset
                self.allocLength = length
                self.allocIndex = index
                newdf = self.getDataFile()
                # assert olddf is newdf
        if oldFragFile is None or dat is None:
            # worst case: we have to copy all the data between files
            olddf = self.getDataFile()
            self.findFragFile(self.allocLength + howMuch)
            newdf = self.getDataFile()
        # copy data now - better strategy later
        # TODO: this is not very scalable
        olddf.seek(oldAllocBegin)
        allocdata = olddf.read(self.contentLength)
        newdf.seek(self.allocBegin)
        newdf.write(allocdata)
        if oldFragFile is not None:
            oldFragFile.free(self._inmem_oid, oldAllocBegin,
                             oldAllocLength, oldAllocIndex)

    def free(self):
        self.fragfile.free(self._inmem_oid, self.allocBegin,
                           self.allocLength, self.allocIndex)
        self.allocBegin = 0
        self.allocLength = 0
        self.allocIndex = 0


class StringStore(Allocation):
    def __init__(self, db, st):
        Allocation.__init__(self,db,len(st))
        df = self.getDataFile()
        # THIS TEMPORARY VARIABLE IS NECESSARY.
        # If you don't create it, then nothing will actually refer to
        # self.fragfile in the meanwhile, it will be sent back to the database,
        # its finalizers will be called, and the file will be closed.  This
        # will have the effect of automatically calling seek(0) on it.
        df.seek(self.allocBegin)
        self.contentLength = len(st)
        df.write(st)

    def getData(self):
        df = self.getDataFile()
        df.seek(self.allocBegin)
        data = df.read(self.contentLength)
        return data


