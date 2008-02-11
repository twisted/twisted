
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
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

try:
    import _posix_clock
    # Make sure the monotonic clock source exists
    _posix_clock.gettime(_posix_clock.CLOCK_MONOTONIC)
except:
    _posix_clock = None

class Platform:
    """Gives us information about the platform we're running on"""

    type = knownPlatforms.get(os.name)
    seconds = time.time

    _lastTicks = 0
    _offset = 0
    
    def __init__(self, name=None):
        if name is not None:
            self.type = knownPlatforms.get(name)

    def monotonicTicks(self):
        """Returns the current number of nanoseconds as an integer
        since some undefined epoch. The only hard requirement is that
        the number returned from this function is always strictly
        greater than any other number returned by it.
        
        Additionally, it is very good if time never skips around (such
        as by the user setting their system clock).

        This default implementation doesn't have that property, as it
        is based upon the system clock, which can be set forward and
        backward in time. An implementation based upon
        clock_gettime(CLOCK_MONOTONIC) is used when available.
        """
        
        cur = int(self.seconds() * 1000000000) + self._offset
        if self._lastTicks >= cur:
            if self._lastTicks < cur + 10000000: # 0.01s
                # Just pretend epsilon more time has gone by.
                cur = self._lastTicks + 1
            else:
                # If lastSeconds is much larger than cur time, clock
                # must've moved backwards! Adjust the offset to keep
                # monotonicity.
                self._offset += self._lastTicks - cur
        
        self._lastTicks = cur
        return cur
    
    if _posix_clock:
        def monotonicTicks2(self):
            cur = _posix_clock.gettime(_posix_clock.CLOCK_MONOTONIC)
            if self._lastTicks >= cur:
                cur += 1
            self._lastTicks = cur
            return cur
        
        monotonicTicks2.__doc__=monotonicTicks.__doc__
        monotonicTicks=monotonicTicks2
        del monotonicTicks2

    def ticksToTime(self, ticks):
        """Returns the time (as returned by time.time) that
        corresponds to the given ticks value. If the time epoch
        changes via the user setting their system time,
        the time value of given ticks may or may not also change.
        """
        curticks = self.monotonicTicks()
        curtime = time.time()
        return (ticks - curticks)/1000000000. + curtime
        
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

    def supportsThreads(self):
        """Can threads be created?
        """
        try:
            return imp.find_module('thread')[0] is None
        except ImportError:
            return False

platform = Platform()
platformType = platform.getType()
seconds = platform.seconds
monotonicTicks = platform.monotonicTicks
ticksToTime = platform.ticksToTime
