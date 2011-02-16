# -*- test-case-name: twisted.python.test.test_runtime -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


# System imports
import os
import sys
import time
import imp


def shortPythonVersion():
    hv = sys.hexversion
    major = (hv & 0xff000000L) >> 24
    minor = (hv & 0x00ff0000L) >> 16
    teeny = (hv & 0x0000ff00L) >> 8
    return "%s.%s.%s" % (major,minor,teeny)

knownPlatforms = {
    'nt': 'win32',
    'ce': 'win32',
    'posix': 'posix',
    'java': 'java',
    'org.python.modules.os': 'java',
    }

_timeFunctions = {
    #'win32': time.clock,
    'win32': time.time,
    }

class Platform:
    """Gives us information about the platform we're running on"""

    type = knownPlatforms.get(os.name)
    seconds = staticmethod(_timeFunctions.get(type, time.time))

    def __init__(self, name=None):
        if name is not None:
            self.type = knownPlatforms.get(name)
            self.seconds = _timeFunctions.get(self.type, time.time)

    def isKnown(self):
        """Do we know about this platform?"""
        return self.type != None

    def getType(self):
        """Return 'posix', 'win32' or 'java'"""
        return self.type

    def isMacOSX(self):
        """Return if we are runnng on Mac OS X."""
        return sys.platform == "darwin"

    def isWinNT(self):
        """Are we running in Windows NT?"""
        if self.getType() == 'win32':
            import _winreg
            try:
                k=_winreg.OpenKeyEx(_winreg.HKEY_LOCAL_MACHINE,
                                    r'Software\Microsoft\Windows NT\CurrentVersion')
                _winreg.QueryValueEx(k, 'SystemRoot')
                return 1
            except WindowsError:
                return 0
        # not windows NT
        return 0

    def isWindows(self):
        return self.getType() == 'win32'


    def isVista(self):
        """
        Check if current platform is Windows Vista or Windows Server 2008.

        @return: C{True} if the current platform has been detected as Vista
        @rtype: C{bool}
        """
        if getattr(sys, "getwindowsversion", None) is not None:
            return sys.getwindowsversion()[0] == 6
        else:
            return False


    def supportsThreads(self):
        """Can threads be created?
        """
        try:
            return imp.find_module('thread')[0] is None
        except ImportError:
            return False


    def supportsINotify(self):
        """
        Return C{True} if we can use the inotify API on this platform.

        @since: 10.1
        """
        try:
            from twisted.python._inotify import INotifyError, init
        except ImportError:
            return False
        try:
            os.close(init())
        except INotifyError:
            return False
        return True


platform = Platform()
platformType = platform.getType()
seconds = platform.seconds
