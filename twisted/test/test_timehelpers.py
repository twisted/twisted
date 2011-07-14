# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the deprecated L{twisted.test.time_helpers} module.
"""

import sys

from twisted.trial.unittest import TestCase


class TimeHelpersTests(TestCase):
    """
    A test for the deprecation of the module.
    """
    def test_deprecated(self):
        """
        Importing L{twisted.test.time_helpers} causes a deprecation warning
        to be emitted.
        """
        # Make sure we're really importing it
        sys.modules.pop('twisted.test.time_helpers', None)
        import twisted.test.time_helpers
        warnings = self.flushWarnings(
            offendingFunctions=[self.test_deprecated])
        self.assertEqual(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(
            warnings[0]['message'],
            "twisted.test.time_helpers is deprecated since Twisted 10.0.  "
            "See twisted.internet.task.Clock instead.")
