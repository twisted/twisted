# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for runtime checks.
"""

import sys

from twisted.python.runtime import Platform, shortPythonVersion
from twisted.trial.unittest import TestCase



class PythonVersionTests(TestCase):
    """
    Tests the shortPythonVersion method.
    """

    def test_shortPythonVersion(self):
        """
        Verify if the Python version is returned correctly.
        """
        ver = shortPythonVersion().split('.')
        for i in range(3):
            self.assertEqual(int(ver[i]), sys.version_info[i])



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


    def test_isLinuxConsistency(self):
        """
        L{Platform.isLinux} can only return C{True} if L{Platform.getType}
        returns C{'posix'} and L{sys.platform} starts with C{"linux"}.
        """
        platform = Platform()
        if platform.isLinux():
            self.assertTrue(sys.platform.startswith("linux"))



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


    def test_isLinux(self):
        """
        If a system platform name is supplied to L{Platform}'s initializer, it
        is used to determine the result of L{Platform.isLinux}, which returns
        C{True} for values beginning with C{"linux"}, C{False} otherwise.
        """
        self.assertFalse(Platform(None, 'darwin').isLinux())
        self.assertTrue(Platform(None, 'linux').isLinux())
        self.assertTrue(Platform(None, 'linux2').isLinux())
        self.assertTrue(Platform(None, 'linux3').isLinux())
        self.assertFalse(Platform(None, 'win32').isLinux())
