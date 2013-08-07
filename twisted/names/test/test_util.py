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
