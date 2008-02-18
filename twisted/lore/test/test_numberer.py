# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.lore.numberer}.
"""

from twisted.trial.unittest import TestCase

from twisted.lore.numberer import Numberer, reset, getFilenum


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



class GlobalTests(TestCase):
    """
    Tests for the deprecated global numberer API.
    """
    def setUp(self):
        """
        Reset the global numberer state.  This relies on L{reset} working
        correctly.
        """
        reset()

    tearDown = setUp


    def test_initialFileNumber(self):
        """
        The first file number reported by L{getFilenum} is C{0}.
        """
        self.assertEqual(
            self.callDeprecated(_unreleasedVersion, getFilenum),
            0)
