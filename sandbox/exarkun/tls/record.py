# -*- test-case-name: twisted.test.test_record -*-

import types, math, struct, itertools

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
    print "extract", [hex(ord(x)) for x in bytes], offset, size
    
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

def processDecode(attrs, toproc, bytes):
    offset = 0
    for (a, t) in toproc:
        attrs[a] = extract(bytes, offset, t.bits)
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

class RecordType(type):
    FORMAT_SPECIFIERS = {
        Integer(8, False): 'B',
        Integer(8, True): 'b',
        Integer(16, False): 'H',
        Integer(16, True): 'h',
        Integer(32, False): 'I',
        Integer(32, True): 'i',
        Int255String(): 'p',
        }

    def __new__(klass, name, bases, attrs):
        if '__format__' in attrs:
            attrs['encode'] = klass.makeEncoder(attrs['__format__'])
            attrs['decode'] = klass.makeDecoder(attrs['__format__'])
        return type.__new__(klass, name, bases, attrs)

    def makeEncoder(klass, format):
        def encode(self):
            result = []
            subbytes = []
            for (attr, type) in format:
                if type in klass.FORMAT_SPECIFIERS:
                    processEncode(result, subbytes)
                    subbytes = []

                    fmt = klass.FORMAT_SPECIFIERS[type]
                    result.append(struct.pack('>' + fmt, getattr(self, attr)))
                elif isinstance(type, Integer):
                    subbytes.append((getattr(self, attr), type))
                else:
                    raise NotImplementedError((type, attr))
            if subbytes:
                processEncode(result, subbytes)
            return ''.join(result)
        return encode
    makeEncoder = classmethod(makeEncoder)

    def makeDecoder(klass, format):
        def decode(cls, bytes):
            d = {}
            offset = 0
            subbytes = []
            for (attr, type) in format:
                if type in klass.FORMAT_SPECIFIERS:
                    if offset:
                        raise ValueError("Non-byte-aligned values in format")
                    fmt = klass.FORMAT_SPECIFIERS[type]
                    size = struct.calcsize('>' + fmt)
                    d[attr] = struct.unpack('>' + fmt, bytes[:size])[0]
                    bytes = bytes[size:]
                else:
                    if offset + type.bits < 8:
                        subbytes.append((attr, type))
                        offset += type.bits
                    elif (offset + type.bits) % 8 == 0:
                        subbytes.append((attr, type))
                        processDecode(d, subbytes, bytes)
                        bytes = bytes[(offset + type.bits) / 8:]
                        subbytes = []
                        offset = 0
            i = cls()
            i.__dict__.update(d)
            return i
        return classmethod(decode)
    makeDecoder = classmethod(makeDecoder)

class Record(object):
    __metaclass__ = RecordType
