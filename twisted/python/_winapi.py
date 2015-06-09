# -*- test-case-name: twisted.python.test.test_winapi -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Wrapped Windows API functions for use by Twisted.  This module is designed
to replace the pywin32 package.
"""

import cffi

from twisted.python.util import sibpath

try:
    LONG = long
except NameError:
    # Python 3
    LONG = int

ffi = cffi.FFI()
ffi.set_unicode(True)


class WindowsAPIError(Exception):
    """
    An error which is raised when a Windows API call has failed.
    """
    def __init__(self, code, function, error):
        super(WindowsAPIError, self).__init__(code, function, error)
        self.code = code
        self.function = function
        self.error = error



def loadLibrary(library):
    """
    This function will load and return a dynamic library object
    for the given name.

    @param library: The name of the library you wish to load, 'kernel32' for
                    example.  Please note, you must have a corresponding header
                    named '_winapi_<library>.h'
    @type library: C{str}

    @return: returns the dynamically loaded library
    @rtype: C{cffi.api.FFILibrary}
    """
    headerPath = sibpath(__file__, "_winapi_{name}.h".format(name=library))
    with open(headerPath, "rb") as header:
        ffi.cdef(header.read())

    return ffi.dlopen(library)


# Load libraries which will be used in the rest of the module.
kernel32 = loadLibrary("kernel32")


def raiseErrorIfZero(ok, function):
    """
    Checks to see if there was an error while calling
    a Windows API function.  This function should only
    be used on Windows API calls which have a return
    value of non-zero for success and zero for failure.

    @param ok: The return value from a Windows API function.
    @type ok: C{int,long}

    @param function: The name of the function that was called
    @type function: C{str}

    @raises WindowsAPIError: Raised if ok != 0
    @raises TypeError: Raised if `ok` is not an integer
    """
    # Be sure we're getting an integer here.  Because we're working
    # with cffi it's possible we could get an object that acts like
    # an integer without in fact being in integer to `ok`.
    if not isinstance(ok, (int, LONG)):
        raise TypeError("Internal error, expected integer for `ok`")

    if ok == 0:
        code, error = ffi.getwinerror()
        raise WindowsAPIError(code, function, error)



def OpenProcess(dwProcessId, dwDesiredAccess=0, bInheritHandle=False):
    """
    This function wraps Microsoft's OpenProcess() function:

        https://msdn.microsoft.com/en-us/library/windows/desktop/ms684320(v=vs.85).aspx

    @param dwProcessId: The process ID we're attempting to open
    @type dwProcessId: C{int}

    @param dwDesiredAccess: The desired access right(s) to the process
    @type dwDesiredAccess: C{int}

    @param bInheritHandle: Should child processes inherit the handle of
                           this process
    @type bInheritHandle: C{bool}

    @return: This function does not return anything
    """
    kernel32.OpenProcess(dwDesiredAccess, bInheritHandle, dwProcessId)
    code, error = ffi.getwinerror()
    if code != 0:
        raise WindowsAPIError(code, "OpenProcess", error)
