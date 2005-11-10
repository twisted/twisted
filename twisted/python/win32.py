# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Win32 utilities.

See also twisted.python.shortcut.
"""

# system imports
import win32api, win32con, re

# sibling import
from runtime import platform


# XXX fix this to use python's builtin _winreg?

def getProgramsMenuPath():
    """Get the path to the Programs menu.

    Probably will break on non-US Windows.
    
    @returns: the filesystem location of the common Start Menu->Programs.
    """
    if not platform.isWinNT():
        return "C:\\Windows\\Start Menu\\Programs"
    keyname = 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Shell Folders'
    hShellFolders = win32api.RegOpenKeyEx(win32con.HKEY_LOCAL_MACHINE, 
                                          keyname, 0, win32con.KEY_READ)
    return win32api.RegQueryValueEx(hShellFolders, 'Common Programs')[0]


def getProgramFilesPath():
    """Get the path to the Program Files folder."""
    keyname = 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion'
    currentV = win32api.RegOpenKeyEx(win32con.HKEY_LOCAL_MACHINE, 
                                     keyname, 0, win32con.KEY_READ)
    return win32api.RegQueryValueEx(currentV, 'ProgramFilesDir')[0]

_cmdLineQuoteRe = re.compile(r'(\\*)"')
_cmdLineQuoteRe2 = re.compile(r'(\\+)\Z')
def cmdLineQuote(s):
    quote = ((" " in s) or ("\t" in s) or ('"' in s)) and '"' or ''
    return quote + _cmdLineQuoteRe2.sub(r"\1\1", _cmdLineQuoteRe.sub(r'\1\1\\"', s)) + quote
