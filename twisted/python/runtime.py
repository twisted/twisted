
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# System imports
import os, sys

def shortPythonVersion():
    hv = sys.hexversion
    major = (hv & 0xff000000) >> 24
    minor = (hv & 0x00ff0000) >> 16
    teeny = (hv & 0x0000ff00) >> 8
    return "%s.%s.%s" % (major,minor,teeny)

class Platform:
    """Gives us information about the platform we're running on"""
    
    def __init__(self):
        if os.name is 'nt':
            self.type = 'win32'
        elif os.name is 'posix':
            self.type = 'posix'
        elif os.name in ('java', 'org.python.modules.os'):
            self.type = 'java'
        else:
            self.type = None
    
    def isKnown(self):
        """Do we know about this platform?"""
        return self.type != None
    
    def getType(self):
        """Return 'posix', 'win32' or 'java'"""
        return self.type
    
    def isWinNT(self):
        """Are we running in Windows NT?"""
        if self.getType() == 'win32':
            import win32api, win32con
            return win32api.GetVersionEx()[3] == win32con.VER_PLATFORM_WIN32_NT
        else:
            raise ValueError, "this is not a Windows platform"


platform = Platform()
