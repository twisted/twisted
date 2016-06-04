# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
System exit support.
"""

from sys import stdout, stderr, exit as sysexit

from twisted.python.constants import Values, ValueConstant



def exit(status, message=None):
    """
    Exit the python interpreter with an optional message.

    @param status: An exit status.
    @type status: L{int} or L{ValueConstant} from L{ExitStatus}.
    """
    if isinstance(status, ValueConstant):
        code = status.value
    else:
        code = int(status)

    if message:
        if code == 0:
            out = stdout
        else:
            out = stderr
        out.write(message)
        out.write("\n")

    sysexit(code)



try:
    import posix as status
except ImportError:
    class status(object):
        """
        Object to hang C{EX_*} values off of as a substitute for L{posix}.
        """
        EX__BASE = 64

        EX_OK          = 0
        EX_USAGE       = EX__BASE
        EX_DATAERR     = EX__BASE + 1
        EX_NOINPUT     = EX__BASE + 2
        EX_NOUSER      = EX__BASE + 3
        EX_NOHOST      = EX__BASE + 4
        EX_UNAVAILABLE = EX__BASE + 5
        EX_SOFTWARE    = EX__BASE + 6
        EX_OSERR       = EX__BASE + 7
        EX_OSFILE      = EX__BASE + 8
        EX_CANTCREAT   = EX__BASE + 9
        EX_IOERR       = EX__BASE + 10
        EX_TEMPFAIL    = EX__BASE + 11
        EX_PROTOCOL    = EX__BASE + 12
        EX_NOPERM      = EX__BASE + 13
        EX_CONFIG      = EX__BASE + 14



class ExitStatus(Values):
    """
    Standard exit status codes for system programs.
    """

    EX_OK          = ValueConstant(status.EX_OK)
    EX_USAGE       = ValueConstant(status.EX_USAGE)
    EX_DATAERR     = ValueConstant(status.EX_DATAERR)
    EX_NOINPUT     = ValueConstant(status.EX_NOINPUT)
    EX_NOUSER      = ValueConstant(status.EX_NOUSER)
    EX_NOHOST      = ValueConstant(status.EX_NOHOST)
    EX_UNAVAILABLE = ValueConstant(status.EX_UNAVAILABLE)
    EX_SOFTWARE    = ValueConstant(status.EX_SOFTWARE)
    EX_OSERR       = ValueConstant(status.EX_OSERR)
    EX_OSFILE      = ValueConstant(status.EX_OSFILE)
    EX_CANTCREAT   = ValueConstant(status.EX_CANTCREAT)
    EX_IOERR       = ValueConstant(status.EX_IOERR)
    EX_TEMPFAIL    = ValueConstant(status.EX_TEMPFAIL)
    EX_PROTOCOL    = ValueConstant(status.EX_PROTOCOL)
    EX_NOPERM      = ValueConstant(status.EX_NOPERM)
    EX_CONFIG      = ValueConstant(status.EX_CONFIG)
