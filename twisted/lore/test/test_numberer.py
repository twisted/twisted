# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.lore.numberer}.
"""

from twisted.trial.unittest import TestCase

from twisted.lore.numberer import Numberer
from twisted.lore.numberer import getNumberSections, setNumberSections
from twisted.lore.numberer import reset, getFilenum, setFilenum, getNextFilenum
from twisted.lore.numberer import resetFilenum
from twisted.lore.numberer import _unreleasedVersion


class NumbererTests(TestCase):
    """
    L{Numberer} tracks the numbering of different files in a multi-file
    document.
    """
    def test_initialFileNumber(self):
        """
        The first file number reported by a newly created L{Numberer} via its
        C{getFileNumber} method is C{0}.
        """
        numberer = Numberer()
        self.assertEqual(numberer.getFileNumber(), 0)


    def test_initialNumberSections(self):
        """
        L{Numberer.numberSections} is initially C{False}.
        """
        numberer = Numberer()
        self.assertFalse(numberer.numberSections)


    def test_setFileNumber(self):
        """
        L{Numberer.setFileNumber} sets the file number.
        """
        numberer = Numberer()
        numberer.setFileNumber(7)
        self.assertEqual(numberer.getFileNumber(), 7)
        self.assertEqual(numberer.getNextFileNumber(), 8)


    def test_getNextFileNumber(self):
        """
        Each call to L{Numberer.getNextFileNumber} returns the next larger
        integer.
        """
        numberer = Numberer()
        self.assertEqual(numberer.getNextFileNumber(), 1)
        self.assertEqual(numberer.getNextFileNumber(), 2)
        self.assertEqual(numberer.getNextFileNumber(), 3)
        self.assertEqual(numberer.getFileNumber(), 3)


    def test_resetFileNumber(self):
        """
        L{Numberer.resetFileNumber} sets the file counter back to C{0}.
        """
        numberer = Numberer()
        numberer.setFileNumber(13)
        numberer.resetFileNumber()
        self.assertEqual(numberer.getFileNumber(), 0)


    def test_reset(self):
        """
        L{Numberer.reset} sets the file counter back to C{0} and
        C{numberSections} to C{False}.
        """
        numberer = Numberer()
        numberer.setFileNumber(5)
        numberer.numberSections = True
        numberer.reset()
        self.assertEqual(numberer.getFileNumber(), 0)
        self.assertFalse(numberer.numberSections)



class GlobalTests(TestCase):
    """
    Tests for the deprecated global numberer API.
    """
    def setUp(self):
        """
        Reset the global numberer state.  This relies on L{reset} working
        correctly.
        """
        self.callDeprecated(_unreleasedVersion, reset)

    tearDown = setUp


    def test_initialFileNumber(self):
        """
        The first file number reported by L{getFilenum} is C{0}.
        """
        self.assertEqual(
            self.callDeprecated(_unreleasedVersion, getFilenum),
            0)


    def test_setFilenum(self):
        """
        L{setFilenum} sets the current file number.
        """
        self.callDeprecated(_unreleasedVersion, setFilenum, 7)
        self.assertEqual(
            self.callDeprecated(_unreleasedVersion, getFilenum),
            7)


    def test_getNextFilenum(self):
        """
        Each call to L{getNextFilenum} returns the next larger integer.
        """
        for number in range(1, 4):
            self.assertEqual(
                self.callDeprecated(_unreleasedVersion, getNextFilenum),
                number)


    def test_getNumberSections(self):
        """
        L{getNumberSections} initially returns C{False}.
        """
        self.assertFalse(
            self.callDeprecated(_unreleasedVersion, getNumberSections))


    def test_setNumberSections(self):
        """
        L{setNumberSections} changes the return value of L{getNumberSections}.
        """
        self.callDeprecated(_unreleasedVersion, setNumberSections, True)
        self.assertTrue(
            self.callDeprecated(_unreleasedVersion, getNumberSections))
        self.callDeprecated(_unreleasedVersion, setNumberSections, False)
        self.assertFalse(
            self.callDeprecated(_unreleasedVersion, getNumberSections))


    def test_resetFilenum(self):
        """
        L{resetFilenum} sets the current file number back to C{0}.
        """
        self.callDeprecated(_unreleasedVersion, setFilenum, 13)
        self.callDeprecated(_unreleasedVersion, resetFilenum)
        self.assertEqual(
            self.callDeprecated(_unreleasedVersion, getFilenum),
            0)


    def test_reset(self):
        """
        L{reset} changes the current file number back to C{0} and section
        numbering to C{False}.
        """
        self.callDeprecated(_unreleasedVersion, setFilenum, 20)
        self.callDeprecated(_unreleasedVersion, setNumberSections, True)
        self.callDeprecated(_unreleasedVersion, reset)
        self.assertEqual(
            self.callDeprecated(_unreleasedVersion, getFilenum),
            0)
        self.assertFalse(
            self.callDeprecated(_unreleasedVersion, getNumberSections))
