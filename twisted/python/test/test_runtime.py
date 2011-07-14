# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for runtime checks.
"""



from twisted.python.runtime import Platform
from twisted.trial.unittest import TestCase



class PlatformTests(TestCase):
    """
    Tests for the default L{Platform} initializer.
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


    def test_isMacOSXConsistency(self):
        """
        L{Platform.isMacOSX} can only return C{True} if L{Platform.getType}
        returns C{'posix'}.
        """
        platform = Platform()
        if platform.isMacOSX():
            self.assertEqual(platform.getType(), 'posix')



class ForeignPlatformTests(TestCase):
    """
    Tests for L{Platform} based overridden initializer values.
    """

    def test_getType(self):
        """
        If an operating system name is supplied to L{Platform}'s initializer,
        L{Platform.getType} returns the platform type which corresponds to that
        name.
        """
        self.assertEqual(Platform('nt').getType(), 'win32')
        self.assertEqual(Platform('ce').getType(), 'win32')
        self.assertEqual(Platform('posix').getType(), 'posix')
        self.assertEqual(Platform('java').getType(), 'java')


    def test_isMacOSX(self):
        """
        If a system platform name is supplied to L{Platform}'s initializer, it
        is used to determine the result of L{Platform.isMacOSX}, which returns
        C{True} for C{"darwin"}, C{False} otherwise.
        """
        self.assertTrue(Platform(None, 'darwin').isMacOSX())
        self.assertFalse(Platform(None, 'linux2').isMacOSX())
        self.assertFalse(Platform(None, 'win32').isMacOSX())
