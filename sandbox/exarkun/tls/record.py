# -*- test-case-name: twisted.test.test_record -*-
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

"""
Framework for decoding complex byte streams.

@author: U{Jp Calderone<mailto:exarkun@twistedmatrix.com}
"""

import types, math, struct

class Integer:
    def __init__(self, bits, signed=False):
        if signed:
            bits -= 1
        self.bits = bits
        self.signed = signed

    def __hash__(self):
        return hash((self.bits, self.signed))

    def __eq__(self, other):
        if isinstance(other, Integer):
            return self.bits == other.bits and self.signed == other.signed
        return False

    def __repr__(self):
        return '<%ssigned %d bit integer>' % (self.signed and 'un' or '', self.signed + self.bits)

    def verify(self, value):
        if not self.signed and value < 0:
            return False
        return 2 ** self.bits > abs(value)

    def sign(self, value):
        return value >= 0 or self.signed

    def range(self, value):
        return 2 ** self.bits > value

class Int255String:
    pass

def unsignedNegation(n, w):
    return struct.unpack('>I', struct.pack('>i', n))[0] & (2 ** w - 1)

def genmask(start, length):
    """Make a byte mask from 'start' and including 'length' bits.
       'start' counts from the MSB as 0. Hence:
       genmask(2,3) returns 00111000, or 0x38
    """
    return ((2**(8-start))-1) & ~(2 **(8-start-length)-1)

def extract(bytes, offset, size):
    i = offset / 8
    ch = ord(bytes[i])
    offset = offset % 8
    result = 0
    if offset+size > 8: # ono we span multiple bytes
        if offset: # double oh no, we start in the middle of a byte
            result = long(ch & genmask(offset, 8-offset))
            size -= 8-offset
        else:
            result = ch
            size -= 8

        while size >= 8:
            # eat a byte at a time
            i += 1
            ch = ord(bytes[i])
            result = (result << 8) + ch
            size -= 8
        offset = 0

    if size:
        mask = genmask(offset, size)
        result = (result << size) + ((mask & ch) >> 8-offset-size)
    return result

def processDecode(toproc, bytes):
    offset = 0
    for (a, t) in toproc:
        a(extract(bytes, offset, t.bits))
        offset += t.bits

def processEncode(result, toproc):
    offset = 0
    accum = 0
    toproc.reverse()
    for (v, t) in toproc:
        accum |= unsignedNegation(v, t.bits) << offset
        offset += t.bits

    for (n, fmt) in ((32, 'I'), (16, 'H'), (8, 'B')):
        while offset >= n:
            result.append(struct.pack('>' + fmt, accum & (2 ** n - 1)))
            offset -= n
            accum >>= n

    if offset:
        raise ValueError("Non-byte-aligned values in format")

def setattr(self, name):
    return lambda value: __builtins__['setattr'](self, name, value)
def callattr(self, name):
    return lambda value: getattr(self, name)(value)

class Record:
    FORMAT_SPECIFIERS = {
        Integer(8, False): 'B',
        Integer(8, True): 'b',
        Integer(16, False): 'H',
        Integer(16, True): 'h',
        Integer(32, False): 'I',
        Integer(32, True): 'i',
        Int255String(): 'p',
        }

    __format__ = ()

    def __encode__(self):
        return self.__format__

    def __decode__(self):
        return self.__format__

    def encode(self):
        result = []
        subbytes = []
        for (attr, t) in self.__encode__():
            if t in self.FORMAT_SPECIFIERS:
                processEncode(result, subbytes)
                subbytes = []

                fmt = self.FORMAT_SPECIFIERS[t]
                result.append(struct.pack('>' + fmt, getattr(self, attr)))
            elif isinstance(t, (types.ClassType, types.TypeType)) and issubclass(t, Record):
                processEncode(result, subbytes)
                subbytes = []

                result.append(getattr(self, attr).encode())
            elif isinstance(t, Integer):
                subbytes.append((getattr(self, attr), t))
            else:
                raise NotImplementedError((t, attr))
        if subbytes:
            processEncode(result, subbytes)
        return ''.join(result)


    def decode(cls, bytes):
        i = cls()
        offset = 0
        subbytes = []
        for (attrspec, t) in i.__decode__():
            if isinstance(attrspec, str):
                attrspec = setattr(i, attrspec)
            if t in cls.FORMAT_SPECIFIERS:
                if offset:
                    raise ValueError("Non-byte-aligned values in format")
                fmt = cls.FORMAT_SPECIFIERS[t]
                size = struct.calcsize('>' + fmt)
                attrspec(struct.unpack('>' + fmt, bytes[:size])[0])
                bytes = bytes[size:]
            elif isinstance(t, (types.ClassType, types.TypeType)) and issubclass(t, Record):
                o, bytes = t.decode(bytes)
                attrspec(o)
            else:
                if offset + t.bits < 8:
                    subbytes.append((attrspec, t))
                    offset += t.bits
                elif (offset + t.bits) % 8 == 0:
                    subbytes.append((attrspec, t))
                    processDecode(subbytes, bytes)
                    bytes = bytes[(offset + t.bits) / 8:]
                    subbytes = []
                    offset = 0
        return i, bytes
    decode = classmethod(decode)
