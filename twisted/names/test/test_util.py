# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.names.util}.
"""

from twisted.names.util import SNA, DateSNA
from twisted.names.util import max as sna_max
from twisted.trial import unittest

class SNATest(unittest.TestCase):

    def setUp(self):
        self.s1 = SNA(1)
        self.s1a = SNA(1)
        self.s2 = SNA(2)
        self.sMaxVal = SNA(SNA.HLFRNG+SNA.HLFRNG-1)


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
        Test SNA equality
        """
        self.assertEqual(self.s1, self.s1a)
        self.assertNotIdentical(self.s1, self.s1a)
        self.assertEqual(hash(self.s1), hash(self.s1a))
        self.assertNotEqual(hash(self.s1), hash(self.s2))

    def test_le(self):
        """
        Test SNA less than or equal
        """
        self.assertLessEqual(self.s1, self.s1)
        self.assertLessEqual(self.s1, self.s1a)
        self.assertLessEqual(self.s1, self.s2)
        self.assertFalse(self.s2 <= self.s1)

    def test_ge(self):
        """
        Test SNA greater than or equal
        """
        self.assertGreaterEqual(self.s1, self.s1)
        self.assertGreaterEqual(self.s1, self.s1a)
        self.assertFalse(self.s1 >= self.s2)
        self.assertGreaterEqual(self.s2, self.s1)


    def test_lt(self):
        """
        Test SNA less than
        """
        self.assertFalse(self.s1 < self.s1)
        self.assertFalse(self.s1 < self.s1a)
        self.assertLess(self.s1, self.s2)
        self.assertFalse(self.s2 < self.s1)

    def test_gt(self):
        """
        Test SNA greater than
        """
        self.assertFalse(self.s1 > self.s1)
        self.assertFalse(self.s1 > self.s1a)
        self.assertFalse(self.s1 > self.s2)
        self.assertGreater(self.s2, self.s1)

    def test_add(self):
        """
        Test SNA addition
        """
        self.assertEqual(self.s1 + self.s1, self.s2)
        self.assertEqual(self.s1 + SNA(SNA.MAXADD), SNA(SNA.MAXADD + 1))
        self.assertEqual(SNA(SNA.MAXADD) + SNA(SNA.MAXADD) + SNA(2), SNA(0))

    def test_maxval(self):
        """
        Test SNA maxval
        """
        smaxplus1 = self.sMaxVal + self.s1
        self.assertGreater(smaxplus1, self.sMaxVal)
        self.assertEqual(smaxplus1, SNA(0))

    def test_max(self):
        """
        Test the SNA max function
        """
        self.assertEqual(sna_max([None, self.s1]), self.s1)
        self.assertEqual(sna_max([self.s1, None]), self.s1)
        self.assertEqual(sna_max([self.s1, self.s1a]), self.s1)
        self.assertEqual(sna_max([self.s2, self.s1a, self.s1, None]), self.s2)
        self.assertEqual(sna_max([SNA(SNA.MAXADD), self.s2, self.s1a, self.s1, None]),
                          SNA(SNA.MAXADD))
        self.assertEqual(sna_max([self.s2, self.s1a, self.s1, None, self.sMaxVal]),
                          self.s2)

    def test_dateSNA(self):
        """
        Test DateSNA construction and comparison
        """
        date1 = DateSNA('20120101000000')
        date2 = DateSNA('20130101000000')
        self.assertLess(date1, date2)

    def test_dateAdd(self):
        """
        Test DateSNA addition
        """
        date3 = DateSNA('20370101000000')
        sna1  = SNA(365*24*60*60)
        date4 = date3 + sna1
        self.assertEqual(date4.asInt(),  date3.asInt() + sna1.asInt())

    def test_asDate(self):
        """
        Test DateSNA conversion
        """
        date1 = '20120101000000'
        date1Sna = DateSNA(date1)
        self.assertEqual(date1Sna.asDate(), date1)

    def test_roundTrip(self):
        """
        Test DateSNA conversion
        """
        date1 = '20370101000000'
        date1Sna = DateSNA(date1)
        intval = date1Sna.asInt()
        sna1a = SNA(intval)

        dateSna1a = DateSNA.fromSNA(sna1a)
        self.assertEqual(date1Sna, dateSna1a)

        dateSna2 = DateSNA.fromInt(intval)
        self.assertEqual(date1Sna, dateSna2)



def assertUndefinedComparison(testCase, a, b):
    """
    C{a} and C{b} cannot be meaningfully compared.
    """
    testCase.assertFalse(a == b)
    testCase.assertFalse(a <= b)
    testCase.assertFalse(a < b)
    testCase.assertFalse(a > b)
    testCase.assertFalse(a >= b)



from functools import partial
sna2 = partial(SNA, serialBits=2)



class SNA2BitTests(unittest.TestCase):
    """
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
        self.assertEqual(SNA(0, serialBits=2).MAXADD, 1)


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
