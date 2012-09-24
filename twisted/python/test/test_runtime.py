# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for runtime checks.
"""

from __future__ import division, absolute_import

import sys

from twisted.trial.unittest import SynchronousTestCase

from twisted.python.runtime import Platform, shortPythonVersion


class PythonVersionTests(SynchronousTestCase):
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



class PlatformTests(SynchronousTestCase):
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


    def test_isWinNT(self):
        """
        L{Platform.isWinNT} can return only C{0} or C{1} and can not return C{1}
        if L{Platform.getType} is not C{"win32"}.
        """
        platform = Platform()
        isWinNT = platform.isWinNT()
        self.assertTrue(isWinNT in (0, 1))
        if platform.getType() != "win32":
            self.assertEqual(isWinNT, 0)


    def test_supportsThreads(self):
        """
        L{Platform.supportsThreads} returns C{True} if threads can be created in
        this runtime, C{False} otherwise.
        """
        # It's difficult to test both cases of this without faking the threading
        # module.  Perhaps an adequate test is to just test the behavior with
        # the current runtime, whatever that happens to be.
        try:
            import threading
        except ImportError:
            self.assertFalse(Platform().supportsThreads())
        else:
            self.assertTrue(Platform().supportsThreads())



class ForeignPlatformTests(SynchronousTestCase):
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
