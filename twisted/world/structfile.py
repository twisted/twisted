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

from fileutils import openPlus

from struct import calcsize, pack, unpack
from struct import error as StructError

## import struct

## def pack(fmt, *args):
##     assert fmt[0] == '!', fmt
##     return struct.pack(fmt, *args)

## def unpack(fmt, *args):
##     assert fmt[0] == '!', fmt
##     return struct.unpack(fmt, *args)

## def calcsize(fmt):
##     assert fmt[0] == '!', fmt
##     return struct.calcsize(fmt)


class FixedSizeString(object):
    def __init__(self, size):
        self.size = size

str255 = FixedSizeString(255)

class StructuredFile:

    """I am a file of fixed-length records."""

    #     ! format
    #     i int
    #     q long
    #     d float
    #     b bool

    VERSION_IDENTIFIER = 'SF01'

    typeToFormatChar = {
        int: 'i',
        long: 'q',
        float: 'd',
        bool: 'b',
    }

    typeToSize = dict([(xtype, calcsize('!'+fmchar)) for xtype, fmchar in typeToFormatChar.items()])

    _options = (('maxLength',None),
                ('offset', 0),
                ('maxSize',None),
                ('ignoreSchema',False))
    
    def __init__(self, nameOrFile, *instructure, **opts):
        """
        return StructuredFile(self.fl, offset=self.offset+(begin * self.size),
                              maxLength=end-begin,
                              *self.instructure)
        """
        #print "StructuredFile", nameOrFile, instructure, opts

        # initialize default options
        for opt, default in self._options:
            setattr(self, opt, opts.get(opt, default))

        # open a file or inherit an already open file
        if isinstance(nameOrFile, str):
            self.fl = openPlus(nameOrFile)
        else:
            self.fl = nameOrFile

        # instructure is the schema of the structured file
        # it is an ordered list of (type, name) tuples
        self.instructure = instructure
        
        # info is the name->type mapping
        self.info = info = {}

        # storeorder is the field names in instructure order
        storeorder = []

        # currentOffset is the offset of where the field is located in the record
        currentOffset = 0

        # formatstring is the struct format string (always big endian)
        formatstring = "!"

        # tupleOffset is the index of the field in the record
        tupleOffset = 0

        for type, name in instructure:
            storeorder.append(name)
            if isinstance(type, FixedSizeString):
                fmttype = "%ds" % type.size
                size = calcsize('!'+fmttype)
            else:
                fmttype = self.typeToFormatChar[type]
                size = self.typeToSize[type]
            formatstring += fmttype
            info[name] = (
                '!'+fmttype, 
                currentOffset, 
                size,
                tupleOffset)
            currentOffset += size
            tupleOffset += 1

        self.storeorder = tuple(storeorder)
        self.formatstring = formatstring
        self.size = calcsize(formatstring)

        if self.maxSize:
            assert self.maxLength is None
            self.maxLength = self.maxSize // self.size

        assert self.maxLength is None or self.maxLength >= 0

        self.orig_offset = self.offset
        if not self.ignoreSchema:
            self._verifyOrWriteIdentificationBlock()


    def _verifyOrWriteIdentificationBlock(self):
        # \x00 delimited formatstring, fieldname1, fieldname2, ....
        identblock = '\x00'.join((self.formatstring,) + self.storeorder)
        # minimum size we need to store the identification block
        identminsize = len(self.VERSION_IDENTIFIER) + calcsize('!II') + len(identblock)
        
        rec_ofs, rmdr = divmod(identminsize, self.size)
        if rmdr > 0:
            rec_ofs += 1

        # build the identification block
        # type      field name                      size
        # ---------------------------------------------
        # str(4)    VERSION_IDENTIFIER              4 bytes
        # uint      RECORD_LENGTH                   4 bytes
        # uint      SKIP_RECORDS                    4 bytes
        # str(?)    FORMAT_STRING (\x00 padded)     (RECORD_LENGTH * SKIP_RECORDS) - 12 bytes
        #
        file_idstring = ''.join((
            self.VERSION_IDENTIFIER,
            pack('!II', self.size, rec_ofs),
            identblock,
            '\x00' * ((self.size * rec_ofs) - (
                len(self.VERSION_IDENTIFIER) + len(identblock) + calcsize('!II'))),
        ))
        self.fl.seek(0, 2)
        file_len = self.fl.tell() - self.offset
        if file_len >= len(file_idstring):
            self.fl.seek(self.offset)
            assert self.fl.tell() == self.offset
            read_idstr = self.fl.read(len(file_idstring))
            if file_idstring != read_idstr:
                #print ''
                #print file_len
                #print repr(file_idstring)
                #print repr(read_idstr)
                #self.fl.seek(0)
                #allfile = self.fl.read()
                #print len(allfile)
                #print repr(allfile)
                # XXX - Make this do something
                raise ValueError, "StructuredFile does not match schema"
        else:
            self.fl.seek(self.offset)
            self.fl.write(file_idstring)
        self.offset += rec_ofs * self.size
    
    def dumpHTML(self, f):
        f.write("<table border='1'><tr>")
        for typ, name in self.instructure:
            f.write('<th>'+name+'</th>')
        f.write('</tr>')
        for row in self:
            f.write('<tr>')
            for item in row:
                try:
                    item = hex(item)
                except:
                    item = str(item)
                f.write('<td>'+item+'</td>')
            f.write('</tr>')
        f.write("</table>")

    def close(self):
        self.fl.close()

    def checkLength(self, at):
        if self.maxLength is not None and at > self.maxLength:
            raise IndexError("Too long by %s" % (at - self.maxLength))

    def setAll(self, at, *all):
        self.checkLength(at)
        tried = (at * self.size) + self.offset
        self.fl.seek(tried)
        assert tried == self.fl.tell()
        try:
            self.fl.write(pack(self.formatstring, *all))
        except StructError, se:
            raise Exception("could not pack", all, "into", self.formatstring, self.info, se)

    def getAll(self, at):
        self.checkLength(at)
        self.fl.seek((at * self.size) + self.offset)
        read = self.fl.read(self.size)
        if len(read) != self.size:
            read += '\x00' * (self.size - len(read))
        return unpack(self.formatstring, read)

    def setAt(self, at, field, value):
        self.checkLength(at)
        type, offset, size, tupleOffset = self.info[field]
        tried = self.offset + (at * self.size) + offset
        self.fl.seek(tried)
        assert tried == self.fl.tell()
        data = pack(type, value)
        if self.maxLength is not None:
            writeLimit = (((self.maxLength) * self.size) + self.offset)
            writeEnd = tried + len(data)
            assert writeEnd <= writeLimit, "%s !< %s" % (writeEnd, writeLimit)
        self.fl.write(data)

    def getAt(self, at, field):
        self.checkLength(at)
        type, offset, size, tupleOffset = self.info[field]
        self.fl.seek(self.offset + (at * self.size) + offset)
        read = self.fl.read(size)
        if len(read) != size:
            read += ('\x00' * (size -len(read)))
        return unpack(type, read)[0]

    def getColumnIndex(self, field):
        type, offset, size, columnOffset = self.info[field]
        return columnOffset

    # kinda-sorta look like a list
    
    def __len__(self):
        self.fl.seek(0,2)
        tf = self.fl.tell() - self.offset
        possible = tf // self.size
        if self.maxLength is not None and possible > self.maxLength:
            return int(self.maxLength)
        else:
            return max(int(possible), 0)

    def __getitem__(self, at):
        if at >= self.__len__():
            raise IndexError(str(at))
        return self.getAll(at)

    def __setitem__(self, at, tup):
        self.setAll(at, *tup)

    def getiterslice(self, begin=0, end=None):
        if end is None:
            end = self.__len__()
        if begin > end:
            direction = -1
        else:
            direction = 1
        for i in xrange(begin, end, direction):
            yield self[i]
            #try:
            #    yield self[i]
            #except IndexError:
            #    raise StopIteration
    
    __iter__ = getiterslice
    
    def append(self, tup):
        self[len(self)] = tup

    def expand(self, itemcount):
        # TODO: bounds check
        self.fl.seek(0, 2)
        self.fl.write('\x00' * (self.size * itemcount))

    def setiterslice(self, begin, end, value, valueLen=None):
        if valueLen is None:
            valueLen = len(value)
        if valueLen != abs(end - begin):
            raise NotImplementedError("Slices that relocate other file portions are not allowed.")
        if begin > end:
            direction = -1
        else:
            direction = 1
        index = begin
        for v in value:
            self[index] = v
            index += direction

    __setslice__ = setiterslice
    
    def __getslice__(self, begin, end):
        #return StructuredFile(self.fl, offset=self.offset+(begin * self.size),
        #                      maxLength=end-begin, ignoreSchema=True,
        #                      *self.instructure)
        return StructuredFileSlice(self, begin, end)

    def copyBlock(self, beginFrom, beginTo, length):
        # corner cases where nothing happens
        if beginFrom == beginTo or length == 0:
            return

        endFrom = beginFrom + length
        endTo = beginTo + length
        # do the blocks overlap?
        if abs(beginTo - beginFrom) < length and beginTo > beginFrom:
            # write backwards if 'left overlap'
            self.setiterslice(endTo - 1, beginTo - 1, self.getiterslice(endFrom - 1, beginFrom - 1), length) 
        else:
            # write forwards for no overlap or 'right overlap'
            self.setiterslice(beginTo, endTo, self.getiterslice(beginFrom, endFrom), length)

    def flush(self):
        self.fl.flush()

class StructuredFileSlice(object):
    def __init__(self, parent, begin, end):
        self.parent = parent
        self.begin = begin
        self.end = end
        self.maxLength = end - begin

    def append(self, item):
        self[len(self)] = item

    def __getitem__(self, index):
        return self.parent[self.begin + index]

    def __setitem__(self, index, item):
        self.parent[self.begin + index] = item
        
    def __len__(self):
        return min(self.end - self.begin, len(self.parent) - self.begin)

    def __setslice__(self, begin, end, value):
        self.parent[self.begin + begin:self.begin + end] = value
    
    def __getslice__(self, begin, end):
        return self.parent[self.begin + begin:min(self.begin + end, self.end)]

    def __iter__(self):
        return self.parent.getiterslice(self.begin, self.end)
        
