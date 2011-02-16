# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for runtime checks.
"""



from twisted.python.runtime import Platform
from twisted.trial.unittest import TestCase



class PlatformTests(TestCase):
    """
    Tests for L{Platform}.
    """

    def test_isVistaConsistency(self):
        """
        Verify consistency of L{Platform.isVista}: it can only be C{True} if
        L{Platform.isWinNT} and L{Platform.isWindows} are C{True}.
        """
        platform = Platform()
        if platform.isVista():
            self.assertTrue(platform.isWinNT())
            self.assertTrue(platform.isWindows())
            self.assertFalse(platform.isMacOSX())
