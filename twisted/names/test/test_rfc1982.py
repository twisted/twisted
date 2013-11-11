# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.names.rfc1982}.
"""

from __future__ import division, absolute_import

import calendar
from datetime import datetime
from functools import partial

from twisted.names.rfc1982 import SNA
from twisted.trial import unittest



class SNATests(unittest.TestCase):
    """
    Tests for L{SNA}.
    """

    def test_serialBitsDefault(self):
        """
        L{SNA.serialBits} has default value 32.
        """
        self.assertEqual(SNA(1).serialBits, 32)


    def test_serialBitsOverride(self):
        """
        L{SNA.__init__} accepts a C{serialBits} argument whose value
        is assigned to L{SNA.serialBits}.
        """
        self.assertEqual(SNA(1, serialBits=8).serialBits, 8)


    def test_str(self):
        """
        L{SNA.__str__} returns a string representation of the current
        value.
        """
        self.assertEqual(str(SNA(123)), '123')


    def test_hash(self):
        """
        L{SNA.__hash__} allows L{SNA} instances to be hashed for use
        as dictionary keys.
        """
        self.assertEqual(hash(SNA(1)), hash(SNA(1)))
        self.assertNotEqual(hash(SNA(1)), hash(SNA(2)))


    def test_convertOtherSerialBitsMismatch(self):
        """
        L{SNA._convertOther} raises L{TypeError} if the other SNA instance has a
        different C{serialBits} value.
        """
        s1 = SNA(0, serialBits=8)
        s2 = SNA(0, serialBits=16)

        self.assertRaises(
            TypeError,
            s1._convertOther,
            s2
        )


    def test_eq(self):
        """
        L{SNA.__eq__} provides rich equality comparison.
        """
        self.assertEqual(SNA(1), SNA(1))


    def test_eqForeignType(self):
        """
        == comparison of L{SNA} with a non-L{SNA} instance raises L{TypeError}.
        """
        self.assertRaises(TypeError, lambda: SNA(1) == object())


    def test_ne(self):
        """
        L{SNA.__ne__} provides rich equality comparison.
        """
        self.assertFalse(SNA(1) != SNA(1))
        self.assertNotEqual(SNA(1), SNA(2))


    def test_neForeignType(self):
        """
        != comparison of L{SNA} with a non-L{SNA} instance raises L{TypeError}.
        """
        self.assertRaises(TypeError, lambda: SNA(1) != object())


    def test_le(self):
        """
        L{SNA.__le__} provides rich <= comparison.
        """
        self.assertTrue(SNA(1) <= SNA(1))
        self.assertTrue(SNA(1) <= SNA(2))


    def test_leForeignType(self):
        """
        <= comparison of L{SNA} with a non-L{SNA} instance returns False.
        """
        self.assertRaises(TypeError, lambda: SNA(1) <= object())


    def test_ge(self):
        """
        L{SNA.__ge__} provides rich >= comparison.
        """
        self.assertTrue(SNA(1) >= SNA(1))
        self.assertTrue(SNA(2) >= SNA(1))


    def test_geForeignType(self):
        """
        >= comparison of L{SNA} with a non-L{SNA} instance returns False.
        """
        self.assertRaises(TypeError, lambda: SNA(1) >= object())


    def test_lt(self):
        """
        L{SNA.__lt__} provides rich < comparison.
        """
        self.assertTrue(SNA(1) < SNA(2))


    def test_ltForeignType(self):
        """
        < comparison of L{SNA} with a non-L{SNA} instance returns False.
        """
        self.assertRaises(TypeError, lambda: SNA(1) < object())


    def test_gt(self):
        """
        L{SNA.__gt__} provides rich > comparison.
        """
        self.assertTrue(SNA(2) > SNA(1))


    def test_gtForeignType(self):
        """
        > comparison of L{SNA} with a non-L{SNA} instance returns False.
        """
        self.assertRaises(TypeError, lambda: SNA(2) > object())


    def test_add(self):
        """
        L{SNA.__add__} allows L{SNA} instances to be summed.
        """
        self.assertEqual(SNA(1) + SNA(1), SNA(2))


    def test_addForeignType(self):
        """
        Addition of L{SNA} with a non-L{SNA} instance raises L{TypeError}.
        """
        self.assertRaises(TypeError, lambda: SNA(1) + object())


    def test_addOutOfRangeHigh(self):
        """
        L{SNA} cannot be added with other SNA values larger than C{_maxAdd}.
        """
        maxAdd = SNA(1)._maxAdd
        self.assertRaises(
            ArithmeticError,
            lambda: SNA(1) + SNA(maxAdd + 1))


    def test_maxVal(self):
        """
        L{SNA.__add__} returns a wrapped value when s1 plus the s2
        would result in a value greater than the C{maxVal}.

        XXX: I've got a feeling we need more tests demonstrating how
        results vary with different s2 values.
        """
        s = SNA(1)
        maxVal = s._halfRing + s._halfRing - 1
        maxValPlus1 = maxVal + 1
        self.assertTrue(SNA(maxValPlus1) > SNA(maxVal))
        self.assertEqual(SNA(maxValPlus1), SNA(0))


    def test_fromRFC4034DateString(self):
        """
        L{SNA.fromRFC4034DateString} accepts a datetime string argument of the
        form 'YYYYMMDDhhmmss' and returns an L{SNA} instance whose value is the
        unix timestamp corresponding to that UTC date.
        """
        self.assertEqual(
            SNA(1325376000),
            SNA.fromRFC4034DateString('20120101000000')
        )


    def test_toRFC4034DateString(self):
        """
        L{DateSNA.toRFC4034DateString} interprets the current value as a unix
        timestamp and returns a date string representation of that date.
        """
        self.assertEqual(
            '20120101000000',
            SNA(1325376000).toRFC4034DateString()
        )


    def test_unixEpoch(self):
        """
        L{SNA.toRFC4034DateString} stores 32bit timestamps relative to the UNIX
        epoch.
        """
        self.assertEqual(
            SNA(0).toRFC4034DateString(),
            '19700101000000'
        )


    def test_Y2106Problem(self):
        """
        L{SNA} wraps unix timestamps in the year 2106.
        """
        self.assertEqual(
            SNA(-1).toRFC4034DateString(),
            '21060207062815'
        )


    def test_Y2038Problem(self):
        """
        L{SNA} raises ArithmeticError when used to add dates more than 68 years
        in the future.
        """
        maxAddTime = calendar.timegm(
            datetime(2038, 1, 19, 3, 14, 7).utctimetuple())

        self.assertEqual(
            maxAddTime,
            SNA(0)._maxAdd,
        )

        self.assertRaises(
            ArithmeticError,
            lambda: SNA(0) + SNA(maxAddTime + 1))



def assertUndefinedComparison(testCase, s1, s2):
    """
    A custom assertion for L{SNA} values that cannot be meaningfully
    compared.

    "Note that there are some pairs of values s1 and s2 for which s1 is
    not equal to s2, but for which s1 is neither greater than, nor less
    than, s2.  An attempt to use these ordering operators on such pairs
    of values produces an undefined result."

    @see: U{https://tools.ietf.org/html/rfc1982#section-3.2}

    @param testCase: The L{unittest.TestCase} on which to call
        assertion methods.
    @type testCase: L{unittest.TestCase}

    @param s1: The first value to compare.
    @type s1: L{SNA}

    @param s2: The second value to compare.
    @type s2: L{SNA}
    """
    testCase.assertFalse(s1 == s2)
    testCase.assertFalse(s1 <= s2)
    testCase.assertFalse(s1 < s2)
    testCase.assertFalse(s1 > s2)
    testCase.assertFalse(s1 >= s2)



sna2 = partial(SNA, serialBits=2)



class SNA2BitTests(unittest.TestCase):
    """
    Tests for correct answers to example calculations in RFC1982 5.1.

    The simplest meaningful serial number space has SERIAL_BITS == 2.  In
    this space, the integers that make up the serial number space are 0,
    1, 2, and 3.  That is, 3 == 2^SERIAL_BITS - 1.

    https://tools.ietf.org/html/rfc1982#section-5.1
    """
    def test_maxadd(self):
        """
        In this space, the largest integer that it is meaningful to add to a
        sequence number is 2^(SERIAL_BITS - 1) - 1, or 1.
        """
        self.assertEqual(SNA(0, serialBits=2)._maxAdd, 1)


    def test_add(self):
        """
        Then, as defined 0+1 == 1, 1+1 == 2, 2+1 == 3, and 3+1 == 0.
        """
        self.assertEqual(sna2(0) + sna2(1), sna2(1))
        self.assertEqual(sna2(1) + sna2(1), sna2(2))
        self.assertEqual(sna2(2) + sna2(1), sna2(3))
        self.assertEqual(sna2(3) + sna2(1), sna2(0))


    def test_gt(self):
        """
        Further, 1 > 0, 2 > 1, 3 > 2, and 0 > 3.
        """
        self.assertTrue(sna2(1) > sna2(0))
        self.assertTrue(sna2(2) > sna2(1))
        self.assertTrue(sna2(3) > sna2(2))
        self.assertTrue(sna2(0) > sna2(3))


    def test_undefined(self):
        """
        It is undefined whether
        2 > 0 or 0 > 2, and whether 1 > 3 or 3 > 1.
        """
        assertUndefinedComparison(self, sna2(2), sna2(0))
        assertUndefinedComparison(self, sna2(0), sna2(2))
        assertUndefinedComparison(self, sna2(1), sna2(3))
        assertUndefinedComparison(self, sna2(3), sna2(1))



sna8 = partial(SNA, serialBits=8)



class SNA8BitTests(unittest.TestCase):
    """
    Tests for correct answers to example calculations in RFC1982 5.2.

    Consider the case where SERIAL_BITS == 8.  In this space the integers
    that make up the serial number space are 0, 1, 2, ... 254, 255.
    255 == 2^SERIAL_BITS - 1.

    https://tools.ietf.org/html/rfc1982#section-5.2
    """

    def test_maxadd(self):
        """
        In this space, the largest integer that it is meaningful to add to a
        sequence number is 2^(SERIAL_BITS - 1) - 1, or 127.
        """
        self.assertEqual(SNA(0, serialBits=8)._maxAdd, 127)


    def test_add(self):
        """
        Addition is as expected in this space, for example: 255+1 == 0,
        100+100 == 200, and 200+100 == 44.
        """
        self.assertEqual(sna8(255) + sna8(1), sna8(0))
        self.assertEqual(sna8(100) + sna8(100), sna8(200))
        self.assertEqual(sna8(200) + sna8(100), sna8(44))


    def test_gt(self):
        """
        Comparison is more interesting, 1 > 0, 44 > 0, 100 > 0, 100 > 44,
        200 > 100, 255 > 200, 0 > 255, 100 > 255, 0 > 200, and 44 > 200.
        """
        self.assertTrue(sna8(1) > sna8(0))
        self.assertTrue(sna8(44) > sna8(0))
        self.assertTrue(sna8(100) > sna8(0))
        self.assertTrue(sna8(100) > sna8(44))
        self.assertTrue(sna8(200) > sna8(100))
        self.assertTrue(sna8(255) > sna8(200))
        self.assertTrue(sna8(100) > sna8(255))
        self.assertTrue(sna8(0) > sna8(200))
        self.assertTrue(sna8(44) > sna8(200))


    def test_surprisingAddition(self):
        """
        Note that 100+100 > 100, but that (100+100)+100 < 100.  Incrementing
        a serial number can cause it to become "smaller".  Of course,
        incrementing by a smaller number will allow many more increments to
        be made before this occurs.  However this is always something to be
        aware of, it can cause surprising errors, or be useful as it is the
        only defined way to actually cause a serial number to decrease.
        """
        self.assertTrue(sna8(100) + sna8(100) > sna8(100))
        self.assertTrue(sna8(100) + sna8(100) + sna8(100) < sna8(100))


    def test_undefined(self):
        """
        The pairs of values 0 and 128, 1 and 129, 2 and 130, etc, to 127 and
        255 are not equal, but in each pair, neither number is defined as
        being greater than, or less than, the other.
        """
        assertUndefinedComparison(self, sna8(0), sna8(128))
        assertUndefinedComparison(self, sna8(1), sna8(129))
        assertUndefinedComparison(self, sna8(2), sna8(130))
        assertUndefinedComparison(self, sna8(127), sna8(255))
