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

from twisted.world.storable import Storable, ref
from twisted.world.allocator import Allocation, FragmentFile
from twisted.world.structfile import StructuredFile

## class MetaStorableList(MetaStorable):
##     """
##     """

class StorableList(Allocation):
    __schema__ = {
        'typeMapper': None,
        'fragdata': None,
    }

##     __metaclass__ = MetaStorableList

    dataType = Storable

    def __init__(self, db):
        Allocation.__init__(self, db,
                            getMapper(self.dataType).getPhysicalSize() * 10)

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
        #print "%r.__awake__() dataType=%r" % (self, self.dataType)
        self.typeMapper = getMapper(self.dataType)
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
        assert isinstance(val, self.getClass()), "%s not an instance of %s" % (val, self.getClass())
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
        assert isinstance(value, self.getClass()), "%s not an instance of %s" % (value, self.getClass())
        self.typeMapper.lowDataToRow(inum, "value", self.getDatabase(),
                                     self.fragdata, value)

    def getClass(self):
        if not hasattr(self, 'storedClassName'):
            return self.dataType
        else:
            return reflect.namedClass(self.storedClassName)

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

class StrList(StorableList):
    dataType = str

class IntList(StorableList):
    dataType = int

class FloatList(StorableList):
    dataType = float


def _codedlist(module, othername):
    """horrible hack"""
    return StorableList
    otherclass = module + '.' + othername
    classname = 'StorableList_' + otherclass.replace(".", "_")
    import listtypes
    if hasattr(listtypes, classname):
        # print 'found our ref'
        return getattr(listtypes, classname)
    execstring = """
class %(classname)s(StorableList):
    storedClassName = %(otherclass)r
""" % {
        'classname': classname,
        'otherclass': otherclass
        }
    print 'execing'
    print execstring
    exec execstring in listtypes.__dict__, listtypes.__dict__
    return getattr(listtypes, classname)
    

def ListOf(n):
    if n is int:
        return IntList
    if n is str:
        return StrList
    if n is float:
        return FloatList
    if isinstance(n, ref):
        return _codedlist(n.module, n.name)
    if issubclass(n, Storable):
        othername = n.__name__
        module = n.__module__
        return _codedlist(module, othername)
    raise KeyError("can't have lists of %s" % n)

from twisted.world.typemap import getMapper
