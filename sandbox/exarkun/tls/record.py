import struct

class RecordType(type):
    def __init__(klass, name, bases, attrs):
        if '__format__' in attrs:
            attrs['encode'] = klass.makeEncoder(attrs['__format__'])
            attrs['decode'] = klass.makeDecoder(attrs['__format__'])
        return type.__new__(klass, name, bases, attrs)

    def makeEncoder(klass, format):
        attrs, fmts = zip(*format)
        fmts = '>' + fmts
        def encode(self):
            return struct.pack(fmts, *[getattr(self, a) for a in attrs])
        return encode

    def makeDecoder(klass, format):
        attrs, fmts = zip(*format)
        fmts = '>' + fmts
        def decode(cls, s):
            values = struct.unpack(fmts, s)
            attrs = dict(zip(attrs, values))
            return types.InstanceType(cls, attrs)
        return classmethod(decode)
