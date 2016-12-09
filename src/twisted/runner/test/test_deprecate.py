# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for deprecations in L{twisted.runner}.
"""

from twisted.trial.unittest import TestCase


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
