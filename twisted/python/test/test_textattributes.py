# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.textattributes}.
"""

from twisted.trial import unittest
from twisted.python._textattributes import DefaultCharacterAttribute



class DefaultCharacterAttributeTests(unittest.TestCase):
    """
    Tests for L{twisted.python._textattributes.DefaultCharacterAttribute}.
    """
    def test_equality(self):
        """
        L{DefaultCharacterAttribute}s are always equal to other
        L{DefaultCharacterAttribute}s.
        """
        b = DefaultCharacterAttribute()
        self.assertEquals(
            DefaultCharacterAttribute(),
            DefaultCharacterAttribute())
        self.assertNotEquals(
            DefaultCharacterAttribute(),
            'hello')
