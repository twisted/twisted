# Copyright (c) 2010 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for deprecation of twisted.persisted.journal

"""

import sys

from twisted.trial.unittest import TestCase


class JournalDeprecationTest(TestCase):
    """
    Tests for twisted.persisted.journal being deprecated.

    """
    def setUp(self):
        """
        Prepare for the deprecation test, by making sure that
        twisted.persisted.journal isn't imported.

        """
        for mod in sys.modules:
            if "twisted.persisted.journal" in mod:
                del sys.modules[mod]

    def test_deprecated(self):
        """
        Make sure that twisted.persisted.journal is deprecated, and
        check the text of its deprecation warning.

        """
        from twisted.persisted import journal
        warnings = self.flushWarnings()
        self.assertEquals(
            warnings[0]['message'],
            'twisted.persisted.journal is deprecated since Twisted 10.1')
        self.assertEquals(warnings[0]['category'], DeprecationWarning)
        self.assertEquals(len(warnings), 1)
