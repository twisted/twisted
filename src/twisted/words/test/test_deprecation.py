# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import annotations

from importlib import reload

import twisted.words
from twisted import words
from twisted.trial import unittest


class WordsDeprecationTests(unittest.TestCase):
    """
    Ensures that importing twisted.words directly or as a
    module of twisted raises a deprecation warning.
    """

    def test_deprecationDirect(self) -> None:
        """
        A direct import will raise the deprecation warning.
        """
        reload(twisted.words)
        warnings = self.flushWarnings([self.test_deprecationDirect])
        self.assertEqual(1, len(warnings))
        self.assertEqual(
            "twisted.words was deprecated at Twisted NEXT", warnings[0]["message"]
        )

    def test_deprecationRootPackage(self) -> None:
        """
        Importing as sub-module of C{twisted} raises the deprecation warning.
        """
        reload(words)
        warnings = self.flushWarnings([self.test_deprecationRootPackage])
        self.assertEqual(1, len(warnings))
        self.assertEqual(
            "twisted.words was deprecated at Twisted NEXT", warnings[0]["message"]
        )
