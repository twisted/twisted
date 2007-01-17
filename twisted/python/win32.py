# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Win32 utilities.

See also twisted.python.shortcut.
"""

import re
import exceptions

try:
    import win32api
    import win32con
    import win32file
    import pywintypes
except ImportError:
    # Make sure they're either all here or none
    win32api = win32con = win32file = pywintypes = None

from twisted.python.runtime import platform

# http://msdn.microsoft.com/library/default.asp?url=/library/en-us/debug/base/system_error_codes.asp
ERROR_FILE_NOT_FOUND = 2
ERROR_PATH_NOT_FOUND = 3
ERROR_INVALID_NAME = 123
ERROR_DIRECTORY = 267

def _determineWindowsError():
    """
    Determine which WindowsError name to export.
    """
    return getattr(exceptions, 'WindowsError', FakeWindowsError)

class FakeWindowsError(OSError):
    """
    Stand-in for sometimes-builtin exception on platforms for which it
    is missing.
    """

WindowsError = _determineWindowsError()

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

# Routine to translate a 'pywintypes.error' exception into the exception that an
# operation would normally generate in this version of python. (either OSError
# or WindowsError).

# This dict is used in python < 2.5. The mapping is in an automatically
# generated C switch statement in Python 2.5, and not present in older versions.
# It was extracted from Python 2.5 using the following code:

# import errno
# d={}
# for x in range(65500):
#     e=WindowsError(x, 'foo')
#     if e.errno != errno.EINVAL:
#         d[e.winerror]=e.errno
# print '{'+', '.join('%d:%d' % x for x in sorted(d.items()))+'}'

_winerr2errno = {
    2:2, 3:2, 4:24, 5:13, 6:9, 7:12, 8:12, 9:12, 10:7, 11:8, 15:2,
    16:13, 17:18, 18:2, 19:13, 20:13, 21:13, 22:13, 23:13, 24:13,
    25:13, 26:13, 27:13, 28:13, 29:13, 30:13, 31:13, 32:13, 33:13,
    34:13, 35:13, 36:13, 53:2, 65:13, 67:2, 80:17, 82:13, 83:13,
    89:11, 108:13, 109:32, 112:28, 114:9, 128:10, 129:10, 130:9,
    132:13, 145:41, 158:13, 161:2, 164:11, 167:13, 183:17, 188:8,
    189:8, 190:8, 191:8, 192:8, 193:8, 194:8, 195:8, 196:8, 197:8,
    198:8, 199:8, 200:8, 201:8, 202:8, 206:2, 215:11, 1816:12}

if sys.version_info[0:2] >= (2,5):
    def _makeStandardException(pywin32error):
        raise WindowsError(pywin32error[0], pywin32error[2])
else:
    def _makeStandardException(pywin32error):
        raise OSError(_winerr2errno.get(pywin32error[0], errno.EINVAL), pywin32error[2])

if win32file:
    # If we're got pywin32 installed, do a rename with the special argument to
    # allow replacing an existing file. Otherwise, do an unlink/rename pairing.
    def rename(src, dest):
        """Rename src to dest. Unlike os.rename, will replace an existing
        destination file, like os.rename on unix."""
        if not isinstance(src, unicode):
            src = src.decode('mbcs')
        if not isinstance(dest, unicode):
            dest = dest.decode('mbcs')

        try:
            win32file.MoveFileExW(src, dest,
                                  win32file.MOVEFILE_REPLACE_EXISTING)
        except pywintypes.error, e:
            raise _makeStandardException(e)
else:
    def rename(src, dest):
        """Rename src to dest. Unlike os.rename, will replace an existing
        destination file, like os.rename on unix."""
        if ospath.exists(dest):
            os.unlink(dest)
        os.rename(src, dest)
