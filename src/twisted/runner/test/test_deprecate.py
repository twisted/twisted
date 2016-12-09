# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for deprecations in L{twisted.runner}.
"""

from twisted.trial.unittest import TestCase
from twisted.python.reflect import requireModule


class PortmapDeprecationTests(TestCase):
    """
    L{twisted.runner.portmap} is deprecated.
    """

    def testDeprecated(self):
        """
        L{twisted.runner.portmap} is deprecated.
        """
        from twisted.runner import portmap

        warningsShown = self.flushWarnings()
        self.assertEqual(1, len(warningsShown))
        self.assertEqual(
            ("twisted.runner.portmap was deprecated in Twisted NEXT: "
             "There is no replacement for this module."),
            warningsShown[0]['message'])

    if not requireModule("_twisted_platform_support._portmap"):
        testDeprecated.skip = "Not relevant on this platform."
