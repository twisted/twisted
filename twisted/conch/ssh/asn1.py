# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# 

"""
A basic ASN.1 parser to parse private SSH keys.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

from Crypto.Util import number

def parse(data):
    things = []
    while data:
        t = ord(data[0])
        assert (t & 0xc0) == 0, 'not a universal value: 0x%02x' % t
        #assert t & 0x20, 'not a constructed value: 0x%02x' % t
        l = ord(data[1])
        assert data != 0x80, "shouldn't be an indefinite length"
        if l & 0x80: # long form
            ll = l & 0x7f
            l = number.bytes_to_long(data[2:2+ll])
            s = 2 + ll
        else:
            s = 2
        body, data = data[s:s+l], data[s+l:]
        t = t&(~0x20)
        assert t in (SEQUENCE, INTEGER), 'bad type: 0x%02x' % t
        if t == SEQUENCE:
            things.append(parse(body))
        elif t == INTEGER:
            #assert (ord(body[0])&0x80) == 0, "shouldn't have negative number"
            things.append(number.bytes_to_long(body))
    if len(things) == 1:
        return things[0]
    return things

def pack(data):
    ret = ''
    for part in data:
        if type(part) in (type(()), type([])):
            partData = pack(part)
            partType = SEQUENCE|0x20
        elif type(part) in (type(1), type(1L)):
            partData = number.long_to_bytes(part)
            if ord(partData[0])&(0x80):
                partData = '\x00' + partData
            partType = INTEGER
        else:
            raise ValueError('unknown type %s' % (type(part),))

        ret += chr(partType)
        if len(partData) > 127:
            l = number.long_to_bytes(len(partData))
            ret += chr(len(l)|0x80) + l
        else:
            ret += chr(len(partData))
        ret += partData
    return ret

INTEGER = 0x02
SEQUENCE = 0x10

