
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
Test cases for twisted.protocols.pureber module.
"""

from pyunit import unittest
from twisted.protocols import pureber
from twisted.python.mutablestring import MutableString
import types

def s(*l):
    """Join all members of list to a string. Integer members are chr()ed"""
    r=''
    for e in l:
        if isinstance(e, types.IntType):
            e=chr(e)
        r=r+str(e)
    return r

def l(s):
    """Split a string to ord's of chars."""
    return map(lambda x: ord(x), s)

class BERIntegerKnownValues(unittest.TestCase):
    knownValues=(
        (0, [0x02, 0x01, 0]),
        (1, [0x02, 0x01, 1]),
        (2, [0x02, 0x01, 2]),
        (125, [0x02, 0x01, 125]),
        (126, [0x02, 0x01, 126]),
        (127, [0x02, 0x01, 127]),
        (-1, [0x02, 0x01, 256-1]),
        (-2, [0x02, 0x01, 256-2]),
        (-3, [0x02, 0x01, 256-3]),
        (-126, [0x02, 0x01, 256-126]),
        (-127, [0x02, 0x01, 256-127]),
        (-128, [0x02, 0x01, 256-128]),
        (-129, [0x02, 0x02, 256-1, 256-129]),
        (128, [0x02, 0x02, 0, 128]),
        (256, [0x02, 0x02, 1, 0]),
        )

    def testToBERIntegerKnownValues(self):
        """str(BERInteger(n)) should give known result with known input"""
        for integer, encoded in self.knownValues:
            result = pureber.BERInteger(integer)
            result = str(result)
            result = map(ord, result)
            assert encoded==result

    def testFromBERIntegerKnownValues(self):
        """BERInteger(encoded="...") should give known result with known input"""
        for integer, encoded in self.knownValues:
            m=MutableString(apply(s,encoded))
            m.append('foo')
            result = pureber.BERInteger(encoded=m, berdecoder=pureber.BERDecoderContext())
            assert m=='foo'
            result = result.value
            assert integer==result

    def testPartialBERIntegerEncodings(self):
        """BERInteger(encoded="...") with too short input should throw BERExceptionInsufficientData"""
        m=str(pureber.BERInteger(42))
        assert len(m)==3
        self.assertRaises(pureber.BERExceptionInsufficientData, pureber.BERInteger, encoded=m[:2], berdecoder=pureber.BERDecoderContext())
        self.assertRaises(pureber.BERExceptionInsufficientData, pureber.BERInteger, encoded=m[:1], berdecoder=pureber.BERDecoderContext())
        self.assertRaises(pureber.BERExceptionInsufficientData, pureber.BERInteger, encoded=MutableString(""), berdecoder=pureber.BERDecoderContext())

class BERIntegerSanityCheck(unittest.TestCase):
    def testSanity(self):
        """BERInteger(encoded=BERInteger(n)).value==n for -1000..1000"""
        for n in range(-1000, 1001, 10):
            encoded = MutableString(pureber.BERInteger(n))
            encoded.append('foo')
            result = pureber.BERInteger(encoded=encoded,
                                        berdecoder=pureber.BERDecoderContext())
            result = result.value
            assert encoded=='foo'
            assert n==result




class BEROctetStringKnownValues(unittest.TestCase):
    knownValues=(
        ("", [0x04, 0]),
        ("foo", [0x04, 3]+l("foo")),
        (100*"x", [0x04, 100]+l(100*"x")),
        )

    def testToBEROctetStringKnownValues(self):
        """str(BEROctetString(n)) should give known result with known input"""
        for st, encoded in self.knownValues:
            result = pureber.BEROctetString(st)
            result = str(result)
            result = map(ord, result)
            assert encoded==result

    def testFromBEROctetStringKnownValues(self):
        """BEROctetString(encoded="...") should give known result with known input"""
        for st, encoded in self.knownValues:
            m=MutableString(apply(s,encoded))
            m.append('foo')
            result = pureber.BEROctetString(encoded=m, berdecoder=pureber.BERDecoderContext())
            assert m=='foo'
            result = str(result)
            result = map(ord, result)
            assert encoded==result

    def testPartialBEROctetStringEncodings(self):
        """BEROctetString(encoded="...") with too short input should throw BERExceptionInsufficientData"""
        m=str(pureber.BEROctetString("x"))
        assert len(m)==3
        self.assertRaises(pureber.BERExceptionInsufficientData, pureber.BEROctetString, encoded=m[:2], berdecoder=pureber.BERDecoderContext())
        self.assertRaises(pureber.BERExceptionInsufficientData, pureber.BEROctetString, encoded=m[:1], berdecoder=pureber.BERDecoderContext())
        self.assertRaises(pureber.BERExceptionInsufficientData, pureber.BEROctetString, encoded=MutableString(""), berdecoder=pureber.BERDecoderContext())

class BEROctetStringSanityCheck(unittest.TestCase):
    def testSanity(self):
        """BEROctetString(encoded=BEROctetString(n*'x')).value==n*'x' for some values of n"""
        for n in 0,1,2,3,4,5,6,100,126,127,128,129,1000,2000:
            encoded = MutableString(pureber.BEROctetString(n*'x'))
            encoded.append('foo')
            result = pureber.BEROctetString(encoded=encoded, berdecoder=pureber.BERDecoderContext())
            result = result.value
            assert encoded=='foo'
            assert n*'x'==result












class BERNullKnownValues(unittest.TestCase):
    def testToBERNullKnownValues(self):
        """str(BERNull()) should give known result"""
        result = pureber.BERNull()
        result = str(result)
        result = map(ord, result)
        assert [0x05, 0x00]==result

    def testFromBERNullKnownValues(self):
        """BERNull(encoded="...") should give known result with known input"""
        encoded=[0x05, 0x00]
        m=MutableString(apply(s,encoded))
        m.append('foo')
        result = pureber.BERNull(encoded=m, berdecoder=pureber.BERDecoderContext())
        assert m=='foo'
        assert 0x05==result.tag

    def testPartialBERNullEncodings(self):
        """BERNull(encoded="...") with too short input should throw BERExceptionInsufficientData"""
        m=str(pureber.BERNull())
        assert len(m)==2
        self.assertRaises(pureber.BERExceptionInsufficientData, pureber.BERNull, encoded=m[:1], berdecoder=pureber.BERDecoderContext())
        self.assertRaises(pureber.BERExceptionInsufficientData, pureber.BERNull, encoded=MutableString(""), berdecoder=pureber.BERDecoderContext())





class BERBooleanKnownValues(unittest.TestCase):
    knownValues=(
        (0, [0x01, 0x01, 0], 0),
        (1, [0x01, 0x01, 0xFF], 0xFF),
        (2, [0x01, 0x01, 0xFF], 0xFF),
        (125, [0x01, 0x01, 0xFF], 0xFF),
        (126, [0x01, 0x01, 0xFF], 0xFF),
        (127, [0x01, 0x01, 0xFF], 0xFF),
        (-1, [0x01, 0x01, 0xFF], 0xFF),
        (-2, [0x01, 0x01, 0xFF], 0xFF),
        (-3, [0x01, 0x01, 0xFF], 0xFF),
        (-126, [0x01, 0x01, 0xFF], 0xFF),
        (-127, [0x01, 0x01, 0xFF], 0xFF),
        (-128, [0x01, 0x01, 0xFF], 0xFF),
        (-129, [0x01, 0x01, 0xFF], 0xFF),
        (-9999, [0x01, 0x01, 0xFF], 0xFF),
        (128, [0x01, 0x01, 0xFF], 0xFF),
        (255, [0x01, 0x01, 0xFF], 0xFF),
        (256, [0x01, 0x01, 0xFF], 0xFF),
        (9999, [0x01, 0x01, 0xFF], 0xFF),
        )

    def testToBERBooleanKnownValues(self):
        """str(BERBoolean(n)) should give known result with known input"""
        for integer, encoded, dummy in self.knownValues:
            result = pureber.BERBoolean(integer)
            result = str(result)
            result = map(ord, result)
            assert encoded==result

    def testFromBERBooleanKnownValues(self):
        """BERBoolean(encoded="...") should give known result with known input"""
        for integer, encoded, canon in self.knownValues:
            m=MutableString(apply(s,encoded))
            m.append('foo')
            result = pureber.BERBoolean(encoded=m, berdecoder=pureber.BERDecoderContext())
            assert m=='foo'
            result = result.value
            assert result==canon

    def testPartialBERBooleanEncodings(self):
        """BERBoolean(encoded="...") with too short input should throw BERExceptionInsufficientData"""
        m=str(pureber.BERBoolean(42))
        assert len(m)==3
        self.assertRaises(pureber.BERExceptionInsufficientData, pureber.BERBoolean, encoded=m[:2], berdecoder=pureber.BERDecoderContext())
        self.assertRaises(pureber.BERExceptionInsufficientData, pureber.BERBoolean, encoded=m[:1], berdecoder=pureber.BERDecoderContext())
        self.assertRaises(pureber.BERExceptionInsufficientData, pureber.BERBoolean, encoded=MutableString(""), berdecoder=pureber.BERDecoderContext())








class BEREnumeratedKnownValues(unittest.TestCase):
    knownValues=(
        (0, [0x0a, 0x01, 0]),
        (1, [0x0a, 0x01, 1]),
        (2, [0x0a, 0x01, 2]),
        (125, [0x0a, 0x01, 125]),
        (126, [0x0a, 0x01, 126]),
        (127, [0x0a, 0x01, 127]),
        (-1, [0x0a, 0x01, 256-1]),
        (-2, [0x0a, 0x01, 256-2]),
        (-3, [0x0a, 0x01, 256-3]),
        (-126, [0x0a, 0x01, 256-126]),
        (-127, [0x0a, 0x01, 256-127]),
        (-128, [0x0a, 0x01, 256-128]),
        (-129, [0x0a, 0x02, 256-1, 256-129]),
        (128, [0x0a, 0x02, 0, 128]),
        (256, [0x0a, 0x02, 1, 0]),
        )

    def testToBEREnumeratedKnownValues(self):
        """str(BEREnumerated(n)) should give known result with known input"""
        for integer, encoded in self.knownValues:
            result = pureber.BEREnumerated(integer)
            result = str(result)
            result = map(ord, result)
            assert encoded==result

    def testFromBEREnumeratedKnownValues(self):
        """BEREnumerated(encoded="...") should give known result with known input"""
        for integer, encoded in self.knownValues:
            m=MutableString(apply(s,encoded))
            m.append('foo')
            result = pureber.BEREnumerated(encoded=m, berdecoder=pureber.BERDecoderContext())
            assert m=='foo'
            result = result.value
            assert integer==result

    def testPartialBEREnumeratedEncodings(self):
        """BEREnumerated(encoded="...") with too short input should throw BERExceptionInsufficientData"""
        m=str(pureber.BEREnumerated(42))
        assert len(m)==3
        self.assertRaises(pureber.BERExceptionInsufficientData, pureber.BEREnumerated, encoded=m[:2], berdecoder=pureber.BERDecoderContext())
        self.assertRaises(pureber.BERExceptionInsufficientData, pureber.BEREnumerated, encoded=m[:1], berdecoder=pureber.BERDecoderContext())
        self.assertRaises(pureber.BERExceptionInsufficientData, pureber.BEREnumerated, encoded=MutableString(""), berdecoder=pureber.BERDecoderContext())

class BEREnumeratedSanityCheck(unittest.TestCase):
    def testSanity(self):
        """BEREnumerated(encoded=BEREnumerated(n)).value==n for -1000..1000"""
        for n in range(-1000, 1001, 10):
            encoded = MutableString(pureber.BEREnumerated(n))
            encoded.append('foo')
            result = pureber.BEREnumerated(encoded=encoded,
                                        berdecoder=pureber.BERDecoderContext())
            result = result.value
            assert encoded=='foo'
            assert n==result


# TODO BERSequence
# TODO BERSequenceOf
# TODO BERSet

testCases = [
    BERIntegerKnownValues, BERIntegerSanityCheck,
    BEROctetStringKnownValues, BEROctetStringSanityCheck,
    BERNullKnownValues, BERBooleanKnownValues,
    BEREnumeratedKnownValues, BEREnumeratedSanityCheck,
    ]
