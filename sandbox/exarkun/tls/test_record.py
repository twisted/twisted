
import random

from record import Record, Integer, Int255String

class SingleSignedByte(Record):
    __format__ = [('a', Integer(8, True))]
    EXPECTED_ENCODED_SIZE = 1

class SingleUnsignedByte(Record):
    __format__ = [('a', Integer(8, False))]
    EXPECTED_ENCODED_SIZE = 1

class SingleSignedShort(Record):
    __format__ = [('a', Integer(16, True))]
    EXPECTED_ENCODED_SIZE = 2

class SingleUnsignedShort(Record):
    __format__ = [('a', Integer(16, False))]
    EXPECTED_ENCODED_SIZE = 2

class SingleSignedLong(Record):
    __format__ = [('a', Integer(32, True))]
    EXPECTED_ENCODED_SIZE = 4

class SingleUnsignedLong(Record):
    __format__ = [('a', Integer(32, False))]
    EXPECTED_ENCODED_SIZE = 4

class MultiByte(Record):
    __format__ = [('a', Integer(8, True)),
                  ('b', Integer(8, False))]
    EXPECTED_ENCODED_SIZE = 2

class MultiType(Record):
    __format__ = [('a', Integer(16, True)),
                  ('b', Integer(8, True))]
    EXPECTED_ENCODED_SIZE = 3

class SubByteFields(Record):
    __format__ = [('a', Integer(2, False)),
                  ('b', Integer(3, False)),
                  ('c', Integer(3, False))]
    EXPECTED_ENCODED_SIZE = 1

class MiddleSubByteFields(Record):
    __format__ = [('a', Integer(32)),
                  ('b', Integer(4)),
                  ('c', Integer(4)),
                  ('d', Integer(24)),
                  ('e', Integer(8))]
    EXPECTED_ENCODED_SIZE = 9

records = [SingleSignedByte, SingleUnsignedByte, SingleSignedShort,
           SingleUnsignedShort, SingleSignedLong, SingleUnsignedLong,
           MultiByte, MultiType, SubByteFields, MiddleSubByteFields]

def randomValue(type):
    if type.signed:
        return random.randrange(-2 ** type.bits + 1, 2 ** type.bits)
    return random.randrange(2 ** type.bits)

from twisted.trial import unittest
class RecordPacking(unittest.TestCase):
    def testMethodsAdded(self):
        for rt in records:
            self.failUnless(hasattr(rt, 'encode'))
            self.failUnless(hasattr(rt, 'decode'))

    def testEncoding(self):
        for rt in records:
            fmt = rt.__format__
            inst = rt()
            for (k, t) in fmt:
                # Pick a random value that the attribute can take on
                setattr(inst, k, randomValue(t))
                print 'Randomly picked', vars(inst)[k], 'for', t
            s = inst.encode()
            msg = "%s encoded to %d bytes, not %d bytes" % (rt.__name__, len(s), rt.EXPECTED_ENCODED_SIZE)
            self.assertEquals(len(s), rt.EXPECTED_ENCODED_SIZE, msg)
            self.assertEquals(vars(rt.decode(s)), vars(inst))
