# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.python.logger._levels}.
"""

from twisted.trial import unittest

from .._levels import InvalidLogLevelError
from .._levels import LogLevel



class LogLevelTests(unittest.TestCase):
    """
    Tests for L{LogLevel}.
    """

    def test_levelWithName(self):
        """
        Look up log level by name.
        """
        for level in LogLevel.iterconstants():
            self.assertIdentical(LogLevel.levelWithName(level.name), level)


    def test_levelWithInvalidName(self):
        """
        You can't make up log level names.
        """
        bogus = "*bogus*"
        try:
            LogLevel.levelWithName(bogus)
        except InvalidLogLevelError as e:
            self.assertIdentical(e.level, bogus)
        else:
            self.fail("Expected InvalidLogLevelError.")
