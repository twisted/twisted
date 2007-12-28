# Copyright (c) 2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.conch.scripts}.
"""

from twisted.conch.scripts import tkconch

from twisted.trial.unittest import TestCase



class TkConchTestCase(TestCase):
    """
    Tests for L{tkconch}.
    """

    def test_deferredAskFrameWithoutCallback(self):
        """
        L{tkconch.deferredAskFrame} should raises a C{ValueError} when the top
        frame already has a callback.
        """
        class FakeFrame(object):
            callback = lambda: None
        self.patch(tkconch, 'frame', FakeFrame())
        self.assertRaises(ValueError, tkconch.deferredAskFrame, None, None)

