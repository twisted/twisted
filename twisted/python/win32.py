# -*- test-case-name: twisted.python.test.test_win32 -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Win32 utilities.

See also twisted.python.shortcut.

@var O_BINARY: the 'binary' mode flag on Windows, or 0 on other platforms, so it
    may safely be OR'ed into a mask for os.open.
"""

from __future__ import division, absolute_import

import re
import os
import struct

try:
    import win32api
    import win32con
except ImportError:
    pass

try:
    from twisted.internet import win32conio
except ImportError:
    pass

from twisted.python.runtime import platform

# http://msdn.microsoft.com/library/default.asp?url=/library/en-us/debug/base/system_error_codes.asp
ERROR_FILE_NOT_FOUND = 2
ERROR_PATH_NOT_FOUND = 3
ERROR_INVALID_NAME = 123
ERROR_DIRECTORY = 267

O_BINARY = getattr(os, "O_BINARY", 0)

class FakeWindowsError(OSError):
    """
    Stand-in for sometimes-builtin exception on platforms for which it
    is missing.
    """

try:
    WindowsError = WindowsError
except NameError:
    WindowsError = FakeWindowsError

# XXX fix this to use python's builtin _winreg?

def getProgramsMenuPath():
    """
    Get the path to the Programs menu.

    Probably will break on non-US Windows.

    @return: the filesystem location of the common Start Menu->Programs.
    @rtype: L{str}
    """
    if not platform.isWindows():
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
        does cmd.exe-style unquoting will interpret it as a single argument,
        even if it contains spaces.
    @type s: C{str}

    @return: a quoted string.
    @rtype: C{str}
    """
    quote = ((" " in s) or ("\t" in s) or ('"' in s) or s == '') and '"' or ''
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


class _ErrorFormatter(object):
    """
    Formatter for Windows error messages.

    @ivar winError: A callable which takes one integer error number argument
        and returns an L{exceptions.WindowsError} instance for that error (like
        L{ctypes.WinError}).

    @ivar formatMessage: A callable which takes one integer error number
        argument and returns a C{str} giving the message for that error (like
        L{win32api.FormatMessage}).

    @ivar errorTab: A mapping from integer error numbers to C{str} messages
        which correspond to those erorrs (like L{socket.errorTab}).
    """
    def __init__(self, WinError, FormatMessage, errorTab):
        self.winError = WinError
        self.formatMessage = FormatMessage
        self.errorTab = errorTab

    def fromEnvironment(cls):
        """
        Get as many of the platform-specific error translation objects as
        possible and return an instance of C{cls} created with them.
        """
        try:
            from ctypes import WinError
        except ImportError:
            WinError = None
        try:
            from win32api import FormatMessage
        except ImportError:
            FormatMessage = None
        try:
            from socket import errorTab
        except ImportError:
            errorTab = None
        return cls(WinError, FormatMessage, errorTab)
    fromEnvironment = classmethod(fromEnvironment)


    def formatError(self, errorcode):
        """
        Returns the string associated with a Windows error message, such as the
        ones found in socket.error.

        Attempts direct lookup against the win32 API via ctypes and then
        pywin32 if available), then in the error table in the socket module,
        then finally defaulting to C{os.strerror}.

        @param errorcode: the Windows error code
        @type errorcode: C{int}

        @return: The error message string
        @rtype: C{str}
        """
        if self.winError is not None:
            return self.winError(errorcode).strerror
        if self.formatMessage is not None:
            return self.formatMessage(errorcode)
        if self.errorTab is not None:
            result = self.errorTab.get(errorcode)
            if result is not None:
                return result
        return os.strerror(errorcode)

formatError = _ErrorFormatter.fromEnvironment().formatError

class FakeFcntl(object):
    """This *fake* module is for windows only
    """
    DN_ACCESS       = 1
    DN_ATTRIB       = 32
    DN_CREATE       = 4
    DN_DELETE       = 8
    DN_MODIFY       = 2
    DN_MULTISHOT    = -2147483648
    DN_RENAME       = 16
    FASYNC          = 8192
    FD_CLOEXEC      = 1
    F_DUPFD         = 0
    F_EXLCK         = 4
    F_GETFD         = 1
    F_GETFL         = 3
    F_GETLEASE      = 1025
    F_GETLK         = 12
    F_GETLK64       = 12
    F_GETOWN        = 9
    F_GETSIG        = 11
    F_NOTIFY        = 1026
    F_RDLCK         = 0
    F_SETFD         = 2
    F_SETFL         = 4
    F_SETLEASE      = 1024
    F_SETLK         = 13
    F_SETLK64       = 13
    F_SETLKW        = 14
    F_SETLKW64      = 14
    F_SETOWN        = 8
    F_SETSIG        = 10
    F_SHLCK         = 8
    F_UNLCK         = 2
    F_WRLCK         = 1
    I_ATMARK        = 21279
    I_CANPUT        = 21282
    I_CKBAND        = 21277
    I_FDINSERT      = 21264
    I_FIND          = 21259
    I_FLUSH         = 21253
    I_FLUSHBAND     = 21276
    I_GETBAND       = 21278
    I_GETCLTIME     = 21281
    I_GETSIG        = 21258
    I_GRDOPT        = 21255
    I_GWROPT        = 21268
    I_LINK          = 21260
    I_LIST          = 21269
    I_LOOK          = 21252
    I_NREAD         = 21249
    I_PEEK          = 21263
    I_PLINK         = 21270
    I_POP           = 21251
    I_PUNLINK       = 21271
    I_PUSH          = 21250
    I_RECVFD        = 21262
    I_SENDFD        = 21265
    I_SETCLTIME     = 21280
    I_SETSIG        = 21257
    I_SRDOPT        = 21254
    I_STR           = 21256
    I_SWROPT        = 21267
    I_UNLINK        = 21261
    LOCK_EX         = 2
    LOCK_MAND       = 32
    LOCK_NB         = 4
    LOCK_READ       = 64
    LOCK_RW         = 192
    LOCK_SH         = 1
    LOCK_UN         = 8
    LOCK_WRITE      = 128

    def fcntl(self, fd, op, arg=0):
        raise NotImplementedError
    def ioctl(self, fd, op, arg=0, mutate_flag=True):
        if op == tty.TIOCGWINSZ:
            width, height = win32conio.getWindowSize()
            return struct.pack("4H", height, width, 0, 0)
        else:
            raise NotImplementedError
    def flock(self, fd, op):
        raise NotImplementedError
    def lockf(self, fd, op, length=0, start=0, whence=0):
        raise NotImplementedError


class FakeTermios(object):
    B0                  = 0
    B110                = 3
    B115200             = 4098
    B1200               = 9
    B134                = 4
    B150                = 5
    B1800               = 10
    B19200              = 14
    B200                = 6
    B230400             = 4099
    B2400               = 11
    B300                = 7
    B38400              = 15
    B460800             = 4100
    B4800               = 12
    B50                 = 1
    B57600              = 4097
    B600                = 8
    B75                 = 2
    B9600               = 13
    BRKINT              = 2
    BS0                 = 0
    BS1                 = 8192
    BSDLY               = 8192
    CBAUD               = 4111
    CBAUDEX             = 4096
    CDSUSP              = 25
    CEOF                = 4
    CEOL                = 0
    CEOT                = 4
    CERASE              = 127
    CFLUSH              = 15
    CIBAUD              = 269418496
    CINTR               = 3
    CKILL               = 21
    CLNEXT              = 22
    CLOCAL              = 2048
    CQUIT               = 28
    CR0                 = 0
    CR1                 = 512
    CR2                 = 1024
    CR3                 = 1536
    CRDLY               = 1536
    CREAD               = 128
    CRPRNT              = 18
    CRTSCTS             = -2147483648
    CS5                 = 0
    CS6                 = 16
    CS7                 = 32
    CS8                 = 48
    CSIZE               = 48
    CSTART              = 17
    CSTOP               = 19
    CSTOPB              = 64
    CSUSP               = 26
    CWERASE             = 23
    ECHO                = 8
    ECHOCTL             = 512
    ECHOE               = 16
    ECHOK               = 32
    ECHOKE              = 2048
    ECHONL              = 64
    ECHOPRT             = 1024
    EXTA                = 14
    EXTB                = 15
    FF0                 = 0
    FF1                 = 32768
    FFDLY               = 32768
    FIOASYNC            = 21586
    FIOCLEX             = 21585
    FIONBIO             = 21537
    FIONCLEX            = 21584
    FIONREAD            = 21531
    FLUSHO              = 4096
    HUPCL               = 1024
    ICANON              = 2
    ICRNL               = 256
    IEXTEN              = 32768
    IGNBRK              = 1
    IGNCR               = 128
    IGNPAR              = 4
    IMAXBEL             = 8192
    INLCR               = 64
    INPCK               = 16
    IOCSIZE_MASK        = 1073676288
    IOCSIZE_SHIFT       = 16
    ISIG                = 1
    ISTRIP              = 32
    IUCLC               = 512
    IXANY               = 2048
    IXOFF               = 4096
    IXON                = 1024
    NCC                 = 8
    NCCS                = 32
    NL0                 = 0
    NL1                 = 256
    NLDLY               = 256
    NOFLSH              = 128
    N_MOUSE             = 2
    N_PPP               = 3
    N_SLIP              = 1
    N_STRIP             = 4
    N_TTY               = 0
    OCRNL               = 8
    OFDEL               = 128
    OFILL               = 64
    OLCUC               = 2
    ONLCR               = 4
    ONLRET              = 32
    ONOCR               = 16
    OPOST               = 1
    PARENB              = 256
    PARMRK              = 8
    PARODD              = 512
    PENDIN              = 16384
    TAB0                = 0
    TAB1                = 2048
    TAB2                = 4096
    TAB3                = 6144
    TABDLY              = 6144
    TCFLSH              = 21515
    TCGETA              = 21509
    TCGETS              = 21505
    TCIFLUSH            = 0
    TCIOFF              = 2
    TCIOFLUSH           = 2
    TCION               = 3
    TCOFLUSH            = 1
    TCOOFF              = 0
    TCOON               = 1
    TCSADRAIN           = 1
    TCSAFLUSH           = 2
    TCSANOW             = 0
    TCSBRK              = 21513
    TCSBRKP             = 21541
    TCSETA              = 21510
    TCSETAF             = 21512
    TCSETAW             = 21511
    TCSETS              = 21506
    TCSETSF             = 21508
    TCSETSW             = 21507
    TCXONC              = 21514
    TIOCCONS            = 21533
    TIOCEXCL            = 21516
    TIOCGETD            = 21540
    TIOCGICOUNT         = 21597
    TIOCGLCKTRMIOS      = 21590
    TIOCGPGRP           = 21519
    TIOCGSERIAL         = 21534
    TIOCGSOFTCAR        = 21529
    TIOCGWINSZ          = 21523
    TIOCINQ             = 21531
    TIOCLINUX           = 21532
    TIOCMBIC            = 21527
    TIOCMBIS            = 21526
    TIOCMGET            = 21525
    TIOCMIWAIT          = 21596
    TIOCMSET            = 21528
    TIOCM_CAR           = 64
    TIOCM_CD            = 64
    TIOCM_CTS           = 32
    TIOCM_DSR           = 256
    TIOCM_DTR           = 2
    TIOCM_LE            = 1
    TIOCM_RI            = 128
    TIOCM_RNG           = 128
    TIOCM_RTS           = 4
    TIOCM_SR            = 16
    TIOCM_ST            = 8
    TIOCNOTTY           = 21538
    TIOCNXCL            = 21517
    TIOCOUTQ            = 21521
    TIOCPKT             = 21536
    TIOCPKT_DATA        = 0
    TIOCPKT_DOSTOP      = 32
    TIOCPKT_FLUSHREAD   = 1
    TIOCPKT_FLUSHWRITE  = 2
    TIOCPKT_NOSTOP      = 16
    TIOCPKT_START       = 8
    TIOCPKT_STOP        = 4
    TIOCSCTTY           = 21518
    TIOCSERCONFIG       = 21587
    TIOCSERGETLSR       = 21593
    TIOCSERGETMULTI     = 21594
    TIOCSERGSTRUCT      = 21592
    TIOCSERGWILD        = 21588
    TIOCSERSETMULTI     = 21595
    TIOCSERSWILD        = 21589
    TIOCSER_TEMT        = 1
    TIOCSETD            = 21539
    TIOCSLCKTRMIOS      = 21591
    TIOCSPGRP           = 21520
    TIOCSSERIAL         = 21535
    TIOCSSOFTCAR        = 21530
    TIOCSTI             = 21522
    TIOCSWINSZ          = 21524
    TOSTOP              = 256
    VDISCARD            = 13
    VEOF                = 4
    VEOL                = 11
    VEOL2               = 16
    VERASE              = 2
    VINTR               = 0
    VKILL               = 3
    VLNEXT              = 15
    VMIN                = 6
    VQUIT               = 1
    VREPRINT            = 12
    VSTART              = 8
    VSTOP               = 9
    VSUSP               = 10
    VSWTC               = 7
    VSWTCH              = 7
    VT0                 = 0
    VT1                 = 16384
    VTDLY               = 16384
    VTIME               = 5
    VWERASE             = 14
    XCASE               = 4
    XTABS               = 6144

    class error(Exception):
        pass

    def tcdrain(self, fd):
        raise NotImplementedError

    def tcflow(self, fd, action):
        raise NotImplementedError

    def tcflush(self, fd, queue):
        raise NotImplementedError

    def tcgetattr(self, fd):
        raise NotImplementedError

    def tcsendbreak(self, fd, duration):
        raise NotImplementedError

    def tcsetattr(self, fd, when, attributes):
        raise NotImplementedError


class FakeTTY(FakeTermios):
    IFLAG   = 0
    OFLAG   = 1
    CFLAG   = 2
    LFLAG   = 3
    ISPEED  = 4
    OSPEED  = 5
    CC      = 6

    def setcbreak(self, fd, when=FakeTermios.TCSAFLUSH):
        raise NotImplementedError

    def setraw(self, fd, when=FakeTermios.TCSAFLUSH):
        raise NotImplementedError


try:
    import fcntl
except ImportError:
    fcntl = FakeFcntl()

try:
    import termios
except ImportError:
    termios = FakeTermios()

try:
    import tty
except ImportError:
    tty = FakeTTY()

