# -*- test-case-name: twisted.test.test_record -*-

import struct

class Integer:
    def __init__(self, bits, signed=False):
        if signed:
            bits -= 1
        self.bits = bits
        self.signed = signed

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
                    offset = 0
                    accum = 0
                    subbytes.reverse()
                    for (v, t) in subbytes:
                        accum |= unsignedNegation(v) << offset
                        offset += t.bits
                    subbytes = []
                    for (n, fmt) in ((32, 'I'), (16, 'H'), (8, 'B')):
                        while offset >= n:
                            result.append(struct.pack('>' + fmt, accum & (2 ** n - 1)))
                            offset -= n
                            accum >>= n

                    if offset:
                        raise ValueError("Non-byte-aligned values in format")

                    fmt = klass.FORMAT_SPECIFIERS[type]
                    result.append(struct.pack('>' + fmt, getattr(self, attr)))
                elif isinstance(type, Integer):
                    subbytes.append((getattr(self, attr), type))
                else:
                    raise NotImplementedError((type, attr))
            return ''.join(result)
        return encode
    makeEncoder = classmethod(makeEncoder)

    def makeDecoder(klass, format):
        def decode(cls, bytes):
            d = {}
            for (attr, type) in format:
                if type in klass.FORMAT_SPECIFIERS:
                    fmt = klass.FORMAT_SPECIFIERS[type]
                    size = struct.calcsize('>' + fmt)
                    d[attr] = struct.unpack('>' + fmt, bytes[:size])[0]
                    bytes = bytes[size:]
                else:
                    if type.bits % 8 == 0:
                        # Yay, easy
                        accum = 0
                        for b in bytes[:type.bits % 8]:
                            accum <<= 8
                            accum |= ord(b)
                        d[attr] = accum
                        bytes = bytes[type.bits % 8:]
                    else:
                        raise NotImplementedError("Decoding sub-byte fields is hard")
            return types.InstanceType(cls, d)
        return classmethod(decode)
    makeDecoder = classmethod(makeDecoder)

class Record(object):
    __metaclass__ = RecordType
