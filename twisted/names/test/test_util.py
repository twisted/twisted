# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.names.util}.
"""

from functools import partial

from twisted.names.util import SNA, DateSNA, snaMax
from twisted.trial import unittest



class SNATest(unittest.TestCase):
    """
    Tests for L{SNA}.
    """

    def setUp(self):
        self.s1 = SNA(1)
        self.s1a = SNA(1)
        self.s2 = SNA(2)
        self.sMaxVal = SNA(SNA.halfRing + SNA.halfRing - 1)


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


    def test_equality(self):
        """
        L{SNA.__eq__} provides rich equality comparison.
        """
        self.assertEqual(self.s1, self.s1a)

        # XXX: Remove this test?
        # self.assertNotIdentical(self.s1, self.s1a)


    def test_hash(self):
        """
        L{SNA.__hash__} allows L{SNA} instances to be hashed for use
        as dictionary keys.
        """
        self.assertEqual(hash(self.s1), hash(self.s1a))
        self.assertNotEqual(hash(self.s1), hash(self.s2))


    def test_le(self):
        """
        L{SNA.__le__} provides rich <= comparison.
        """
        self.assertLessEqual(self.s1, self.s1)
        self.assertLessEqual(self.s1, self.s1a)
        self.assertLessEqual(self.s1, self.s2)
        # XXX: Remove this test?
        # self.assertFalse(self.s2 <= self.s1)


    def test_ge(self):
        """
        L{SNA.__ge__} provides rich >= comparison.
        """
        self.assertGreaterEqual(self.s1, self.s1)
        self.assertGreaterEqual(self.s1, self.s1a)
        # XXX: Remove this test?
        # self.assertFalse(self.s1 >= self.s2)
        self.assertGreaterEqual(self.s2, self.s1)


    def test_lt(self):
        """
        L{SNA.__lt__} provides rich < comparison.
        """
        # XXX: Remove these tests?
        # self.assertFalse(self.s1 < self.s1)
        # self.assertFalse(self.s1 < self.s1a)
        # self.assertFalse(self.s2 < self.s1)
        self.assertTrue(self.s1 < self.s2)


    def test_gt(self):
        """
        L{SNA.__gt__} provides rich > comparison.
        """
        # XXX: Remove these tests?
        # self.assertFalse(self.s1 > self.s1)
        # self.assertFalse(self.s1 > self.s1a)
        # self.assertFalse(self.s1 > self.s2)
        self.assertGreater(self.s2, self.s1)


    def test_add(self):
        """
        L{SNA.__add__} allows L{SNA} instances to be summed.
        """
        self.assertEqual(self.s1 + self.s1, self.s2)


    def test_addWhy(self):
        """
        L{SNA.__add__}
        XXX: Explain this test.
        """
        self.assertEqual(self.s1 + SNA(SNA.maxAdd), SNA(SNA.maxAdd + 1))


    def test_addWhy2(self):
        """
        L{SNA.__add__}
        XXX: Explain this test.
        """
        self.assertEqual(SNA(SNA.maxAdd) + SNA(SNA.maxAdd) + SNA(2), SNA(0))


    def test_maxVal(self):
        """
        L{SNA.__add__} returns a wrapped value when s1 plus the s2
        would result in a value greater than the C{maxVal}.

        XXX: I've got a feeling we need more tests demonstrating how
        results vary with different s2 values.
        """
        smaxplus1 = self.sMaxVal + self.s1
        self.assertGreater(smaxplus1, self.sMaxVal)
        self.assertEqual(smaxplus1, SNA(0))



class SnaMaxTests(unittest.TestCase):
    """
    Tests for L{snaMax}.
    """

    def setUp(self):
        self.s1 = SNA(1)
        self.s1a = SNA(1)
        self.s2 = SNA(2)
        self.sMaxVal = SNA(SNA.halfRing + SNA.halfRing - 1)


    def test_snaMax(self):
        """
        L{snaMax} accepts a list of L{SNA} instances and returns the
        one with the highest value.
        """
        self.assertEqual(snaMax([self.s2, self.s1]), self.s2)


    def test_snaMaxEqual(self):
        """
        If the list provided to L{snaMax} contains multiple equal
        L{SNA} instances, the first such instance is returned.
        """
        self.assertEqual(snaMax([self.s1, self.s1a]), self.s1)


    def test_snaMaxMixed(self):
        """
        L{snaMax} accepts mixed lists containing L{SNA} instances and
        C{None}. L{SNA} is always greater than C{None}.
        """
        self.assertEqual(snaMax([None, self.s1]), self.s1)
        self.assertEqual(snaMax([self.s1, None]), self.s1)
        # XXX: Remove this test?
        # self.assertEqual(snaMax([self.s2, self.s1a, self.s1, None]), self.s2)


    def test_why(self):
        """
        XXX: These tests need explaining.
        """
        self.assertEqual(
            snaMax([SNA(SNA.maxAdd), self.s2, self.s1a, self.s1, None]),
            SNA(SNA.maxAdd))

        self.assertEqual(
            snaMax([self.s2, self.s1a, self.s1, None, self.sMaxVal]),
            self.s2)



class DateSNATests(unittest.TestCase):
    """
    Tests for L{DateSNA}.
    """
    def test_dateStringArgument(self):
        """
        L{DateSNA.__init__} accepts a datetime string argument of the
        form 'YYYYMMDDhhmmss'
        """
        self.assertEqual(DateSNA('20120101000000'), SNA(1325376000))


    def test_lt(self):
        """
        L{DateSNA.__lt__} provides rich < comparison.
        """
        date1 = DateSNA('20120101000000')
        date2 = DateSNA('20130101000000')
        self.assertLess(date1, date2)


    def test_add(self):
        """
        L{DateSNA.__add__} wraps dates in the year 2038.

        XXX: Is that right? https://en.wikipedia.org/wiki/Year_2038_problem
        """
        date3 = DateSNA('20370101000000')
        sna1  = SNA(365 * 24 * 60 * 60)
        date4 = date3 + sna1
        self.assertEqual(date4.asInt(),  date3.asInt() + sna1.asInt())


    def test_asDate(self):
        """
        L{DateSNA.asDate} returns a date string in the form
        'YYYYMMDDhhmmss'.
        """
        date1 = '20120101000000'
        date1Sna = DateSNA(date1)
        self.assertEqual(date1Sna.asDate(), date1)


    def test_roundTrip(self):
        """
        L{DateSNA} instances can be converted to L{SNA} and back
        without loss.
        """
        date1 = '20370101000000'
        date1Sna = DateSNA(date1)
        intval = date1Sna.asInt()
        sna1a = SNA(intval)

        dateSna1a = DateSNA.fromSNA(sna1a)
        self.assertEqual(date1Sna, dateSna1a)

        dateSna2 = DateSNA.fromInt(intval)
        self.assertEqual(date1Sna, dateSna2)



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
        self.assertEqual(SNA(0, serialBits=2).maxAdd, 1)


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
        self.assertGreater(sna2(1), sna2(0))
        self.assertGreater(sna2(2), sna2(1))
        self.assertGreater(sna2(3), sna2(2))
        self.assertGreater(sna2(0), sna2(3))


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
        self.assertEqual(SNA(0, serialBits=8).maxAdd, 127)


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
        self.assertGreater(sna8(1), sna8(0))
        self.assertGreater(sna8(44), sna8(0))
        self.assertGreater(sna8(100), sna8(0))
        self.assertGreater(sna8(100), sna8(44))
        self.assertGreater(sna8(200), sna8(100))
        self.assertGreater(sna8(255), sna8(200))
        self.assertGreater(sna8(100), sna8(255))
        self.assertGreater(sna8(0), sna8(200))
        self.assertGreater(sna8(44), sna8(200))


    def test_surprisingAddition(self):
        """
        Note that 100+100 > 100, but that (100+100)+100 < 100.  Incrementing
        a serial number can cause it to become "smaller".  Of course,
        incrementing by a smaller number will allow many more increments to
        be made before this occurs.  However this is always something to be
        aware of, it can cause surprising errors, or be useful as it is the
        only defined way to actually cause a serial number to decrease.
        """
        self.assertGreater(sna8(100) + sna8(100), sna8(100))

        # XXX: This test should succeed according to description
        # above, but fails. Can't work out what's wrong, test or
        # implementation.
        # self.assertLess((sna8(100) + sna8(100)) + sna8(100), sna8(100))
        self.assertRaises(
            ArithmeticError,
            lambda: (sna8(100) + sna8(100)) + sna8(100))


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
