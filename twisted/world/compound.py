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

import sys

from twisted.world.storable import Storable, ref
from twisted.world.allocator import Allocation, FragmentFile
from twisted.world.structfile import StructuredFile
from twisted.world.typemap import TypeMapperMapper
## class MetaStorableList(MetaStorable):
##     """
##     """

# hack, hack
from twisted.python.compat import *

class StorableList(Allocation):
    __schema__ = {
        'typeMapper': TypeMapperMapper,
        'fragdata': None,
    }

    initialPad = 10

##     __metaclass__ = MetaStorableList

    def __init__(self, db, typeMapper):
        self.typeMapper = typeMapper
        Allocation.__init__(self, db,
                            typeMapper.getPhysicalSize() * self.initialPad)

    def updateFragData(self):
        #print self.allocBegin, self.allocLength, self.fragfile
        self.fragdata = StructuredFile(self.getDataFile(),
                                       offset=self.allocBegin,
                                       maxSize=self.allocLength,
                                       ignoreSchema=True,
                                       *self.typeMapper.getLowColumns("value"))

    def expand(self, howMuch=None):
        #print "expand"
        Allocation.expand(self, howMuch)
        self.updateFragData()

    def __awake__(self):
        self.updateFragData()

    def _checkindex(self, inum):
        if inum >= len(self):
            raise IndexError("(persistent) list index out of range")
        if inum < 0:
            return len(self) + inum
        else:
            return inum

    def __len__(self):
        return self.contentLength // self.fragdata.size

    def __iter__(self):
        cl = self.contentLength
        fd = self.fragdata
        db = self.getDatabase()
        rval = self.typeMapper.highDataFromRow
        for idx in xrange(len(self)):
            if self.contentLength != cl:
                raise RuntimeError("ListOf changed during Iteration")
            yield rval(idx, "value", db, fd)
    
    def __delitem__(self, inum):
        inum = self._checkindex(inum)
        self.fragdata.copyBlock(inum+1, inum, len(self) - inum - 1)
        self.contentLength -= self.fragdata.size

    def __hash__(self):
        return id(self)

    def __cmp__(self, other):
        res = 0
        if self is other:
            return res
        try:
            iother = iter(other)
            iself = iter(self)
        except TypeError:
            return object.__cmp__(self, other)
        try:
            while 1:
                snext, onext = iself.next(), iother.next()
                res = cmp(snext, onext)
                if res != 0:
                    return res
        except StopIteration:
            pass
        try:
            iself.next()
            res += 1
        except StopIteration:
            pass
        try:
            iother.next()
            res -= 1
        except StopIteration:
            pass
        return res

    def __lt__(self, other):
        return self.__cmp__(other) < 0

    def __le__(self, other):
        return self.__cmp__(other) <= 0

    def __eq__(self, other):
        return self.__cmp__(other) == 0

    def __ne__(self, other):
        return self.__cmp__(other) != 0

    def __gt__(self, other):
        return self.__cmp__(other) == 1

    def __ge__(self, other):
        return self.__cmp__(other) >= 1

    def pop(self, inum=None):
        if inum is None:
            inum = len(self) - 1
        val = self[inum]
        del self[inum]
        return val

    def __getitem__(self, inum):
        inum = self._checkindex(inum)
        val = self.typeMapper.highDataFromRow(inum, "value",
                                              self.getDatabase(),
                                              self.fragdata)
        return val

    def __getslice__(self, begin, end):
        # XXX: Doesn't __getslice__ do this implicitly???
        if begin < 0:
            begin += len(self)
        if end < 0:
            end += len(self)
        # I know that this is necessary
        end = min(len(self), end)
        return [self[index] for index in xrange(begin,end)]

    def __setitem__(self, inum, value):
        inum = self._checkindex(inum)
        self.typeMapper.lowDataToRow(inum, "value", self.getDatabase(),
                                     self.fragdata, value)

    def __delslice__(self, begin, end):
        self[begin:end] = []

    def __setslice__(self, begin, end, val):
        if end < 0:
            end += len(self)
        if begin < 0:
            begin += len(self)
        begin = max(begin,0)
        end = max(end,0,begin)
        end = min(len(self),end)
        if begin > len(self):
            for o in val:
                self.append(o)
            return
        valdiff = len(val) - (end - begin)
        # TODO: GC needs to decref everything in the replaced range
        if valdiff > 0:
            # the slice is larger than the range it replaces, so we may need to make room
            padSpace = self.allocLength - self.contentLength
            neededSpace = valdiff - (padSpace // self.fragdata.size)
            if neededSpace > 0:
                self.expand(neededSpace * self.fragdata.size)
            prevLen = len(self)
            prevCL = self.contentLength
            self.contentLength += valdiff * self.fragdata.size
            # if there's any data that needs to be copied
            if end < prevLen:
                self.fragdata.copyBlock(end, end + valdiff, prevLen - end)
        elif valdiff < 0:
            # the slice is smaller than the range it replaces
            prevLen = len(self)
            self.contentLength += valdiff * self.fragdata.size
            # then put the old data at the end of the slice
            self.fragdata.copyBlock(end, end + valdiff, prevLen - end)
        # then insert the new data into the space that was made
        for index in range(begin, end+valdiff):
            self[index] = val[index-begin]

    def append(self, o):
        if ((self.contentLength + 1) * self.fragdata.size) > self.allocLength:
            self.expand()
        self.contentLength += self.fragdata.size
        self[len(self) - 1] = o

    def extend(self, seq):
        for o in seq:
            self.append(o)

    def insert(self, idx, o):
        self[idx:idx] = [o]

    def sort(self):
        l = list(self)
        l.sort()
        self[:] = l

class _Nothing:
    """
    this can stop torg
    """

class StorableDictionaryStore(StorableList):
    __schema__ = StorableList.__schema__.copy()
    __schema__.update({
        "keyValueCount": int
        })
    
    def __init__(self, db, keyType, valueType):
        typeMapper = getMapper((bool, keyType, valueType))
        StorableList.__init__(self, db, typeMapper)
        self[:] = [typeMapper.null()] * self.initialPad

    def computePosition(self, inKeyHash, offset):
        return ((inKeyHash + offset) % StorableList.__len__(self))

    def _embiggen(self):
        # this requires allocating a new arena to copy stuff into, but hanging
        # on to the old arena so that we can read the data out of it.  It has
        # completely different semantics than StorableList.expand().
        raise NotImplementedError("StorableDictionary._embiggen")
 
    def getHash(self, inKey):
        return hash(inKey)

    def getDictItem(self, inKey, default=_Nothing):
        h = self.getHash(inKey)
        for i in xrange(len(self)):
            pos = self.computePosition(h,i)
            rowUsed, rowKey, rowValue = self[pos]
            if not rowUsed:
                if default is _Nothing:
                    raise KeyError("No such key in persistent dict %s" % inKey)
                else:
                    return default
            if rowKey == inKey:
                return rowValue

    def setDictItem(self, inKey, inValue):
        h = self.getHash(inKey)
        for i in xrange(len(self)):
            pos = self.computePosition(h,i)
            rowUsed, rowKey, rowValue = self[pos]
            if (not rowUsed) or (inKey == rowKey):
                StorableList.__setitem__(self, pos, (True, inKey, inValue))
                if inKey != rowKey:
                    self.keyValueCount += 1
                break
        else:
            # oh god let's hope that we never actually get _here_
            self._embiggen()
            self[inKey] = inValue

from twisted.python.components import Adapter

_otherNothing = _Nothing()

class StorableDictionaryFacade(Adapter):
    def __setitem__(self, key, value):
        self.original.setDictItem(key, value)

    def __getitem__(self, key, default=_Nothing):
        return self.original.getDictItem(key, default)

    get = __getitem__

    def __len__(self):
        return self.original.keyValueCount

    def has_key(self, key):
        return (self.original.getDictItem(key, _otherNothing)
                is not _otherNothing)

def StorableDictionary(db, keyType, valueType):
    stor = StorableDictionaryStore(db, keyType, valueType)
    return StorableDictionaryFacade(stor)

### These are all deprecated.

class StrList(StorableList):
    dataType = str

class IntList(StorableList):
    dataType = int

class FloatList(StorableList):
    dataType = float


from twisted.world.typemap import getMapper
from twisted.world.typemap import StorableListTypeMapper as ListOf
