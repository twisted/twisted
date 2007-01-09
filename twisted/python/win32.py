# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Win32 utilities.

See also twisted.python.shortcut.
"""

import re

try:
    import win32api
    import win32con
except ImportError:
    win32api = win32con = None

from twisted.python.runtime import platform

# http://msdn.microsoft.com/library/default.asp?url=/library/en-us/debug/base/system_error_codes.asp
ERROR_FILE_NOT_FOUND = 2
ERROR_PATH_NOT_FOUND = 3
ERROR_INVALID_NAME = 123
ERROR_DIRECTORY = 267

try:
    WindowsError = WindowsError
except NameError:
    class WindowsError:
        """
        Stand-in for sometimes-builtin exception on platforms for which it
        is missing.
        """

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
    """
    Internal method for quoting a single command-line argument.

    @param s: an unquoted string that you want to quote so that something that
    does cmd.exe-style unquoting will interpret it as a single argument, even
    if it contains spaces.

    @return: a quoted string.
    """
    quote = ((" " in s) or ("\t" in s) or ('"' in s)) and '"' or ''
    return quote + _cmdLineQuoteRe2.sub(r"\1\1", _cmdLineQuoteRe.sub(r'\1\1\\"', s)) + quote

def quoteArguments(arguments):
    """
    Quote an iterable of command-line arguments for passing to CreateProcess or
    a similar API.  This allows the list passed to C{reactor.spawnProcess} to
    match the child process's C{sys.argv} properly.

    @param arglist: an iterable of C{str}, each unquoted.

    @return: a single string, with the given sequence quoted as necessary.
    """
    return ' '.join([cmdLineQuote(a) for a in arguments])
