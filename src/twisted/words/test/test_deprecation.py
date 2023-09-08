# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import annotations

from importlib import reload

import twisted.words
from twisted import words
from twisted.trial import unittest


class WordsDeprecationTests(unittest.TestCase):
    """
    Ensures that importing twisted.words or any sub-package
    raises a deprecation warning.
    """

    def test_deprecationDirect(self):
        """
        An import direct will raise the deprecation
        """
        reload(twisted.words)
        warnings = self.flushWarnings([self.test_deprecationDirect])
        self.assertEqual(1, len(warnings))
        self.assertEqual(
            "twisted.words is deprecated since Twisted NEXT", warnings[0]["message"]
        )

    def test_deprecationRootPackage(self):
        """
        An import direct will raise the deprecation
        """
        reload(words)
        warnings = self.flushWarnings([self.test_deprecationRootPackage])
        self.assertEqual(1, len(warnings))
        self.assertEqual(
            "twisted.words is deprecated since Twisted NEXT", warnings[0]["message"]
        )
