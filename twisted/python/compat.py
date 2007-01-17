# -*- test-case-name: twisted.test.test_compat -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Compatability module to provide backwards compatability
for useful Python features.

This is mainly for use of internal Twisted code. We encourage you to use
the latest version of Python directly from your code, if possible.
"""

import sys, string, socket, struct

def inet_pton(af, addr):
    if af == socket.AF_INET:
        return socket.inet_aton(addr)
    elif af == getattr(socket, 'AF_INET6', 'AF_INET6'):
        if [x for x in addr if x not in string.hexdigits + ':.']:
            raise ValueError("Illegal characters: %r" % (''.join(x),))

        parts = addr.split(':')
        elided = parts.count('')
        ipv4Component = '.' in parts[-1]

        if len(parts) > (8 - ipv4Component) or elided > 3:
            raise ValueError("Syntactically invalid address")

        if elided == 3:
            return '\x00' * 16

        if elided:
            zeros = ['0'] * (8 - len(parts) - ipv4Component + elided)

            if addr.startswith('::'):
                parts[:2] = zeros
            elif addr.endswith('::'):
                parts[-2:] = zeros
            else:
                idx = parts.index('')
                parts[idx:idx+1] = zeros

            if len(parts) != 8 - ipv4Component:
                raise ValueError("Syntactically invalid address")
        else:
            if len(parts) != (8 - ipv4Component):
                raise ValueError("Syntactically invalid address")

        if ipv4Component:
            if parts[-1].count('.') != 3:
                raise ValueError("Syntactically invalid address")
            rawipv4 = socket.inet_aton(parts[-1])
            unpackedipv4 = struct.unpack('!HH', rawipv4)
            parts[-1:] = [hex(x)[2:] for x in unpackedipv4]

        parts = [int(x, 16) for x in parts]
        return struct.pack('!8H', *parts)
    else:
        raise socket.error(97, 'Address family not supported by protocol')

def inet_ntop(af, addr):
    if af == socket.AF_INET:
        return socket.inet_ntoa(addr)
    elif af == socket.AF_INET6:
        if len(addr) != 16:
            raise ValueError("address length incorrect")
        parts = struct.unpack('!8H', addr)
        curBase = bestBase = None
        for i in range(8):
            if not parts[i]:
                if curBase is None:
                    curBase = i
                    curLen = 0
                curLen += 1
            else:
                if curBase is not None:
                    if bestBase is None or curLen > bestLen:
                        bestBase = curBase
                        bestLen = curLen
                    curBase = None
        if curBase is not None and (bestBase is None or curLen > bestLen):
            bestBase = curBase
            bestLen = curLen
        parts = [hex(x)[2:] for x in parts]
        if bestBase is not None:
            parts[bestBase:bestBase + bestLen] = ['']
        if parts[0] == '':
            parts.insert(0, '')
        if parts[-1] == '':
            parts.insert(len(parts) - 1, '')
        return ':'.join(parts)
    else:
        raise socket.error(97, 'Address family not supported by protocol')

try:
    socket.inet_pton(socket.AF_INET6, "::")
except (AttributeError, NameError, socket.error):
    socket.inet_pton = inet_pton
    socket.inet_ntop = inet_ntop
    socket.AF_INET6 = 'AF_INET6'

adict = dict

# OpenSSL/__init__.py imports OpenSSL.tsafe.  OpenSSL/tsafe.py imports
# threading.  threading imports thread.  All to make this stupid threadsafe
# version of its Connection class.  We don't even care about threadsafe
# Connections.  In the interest of not screwing over some crazy person
# calling into OpenSSL from another thread and trying to use Twisted's SSL
# support, we don't totally destroy OpenSSL.tsafe, but we will replace it
# with our own version which imports threading as late as possible.

class tsafe(object):
    class Connection:
        """
        OpenSSL.tsafe.Connection, defined in such a way as to not blow.
        """
        __module__ = 'OpenSSL.tsafe'

        def __init__(self, *args):
            from OpenSSL import SSL as _ssl
            self._ssl_conn = apply(_ssl.Connection, args)
            from threading import _RLock
            self._lock = _RLock()

        for f in ('get_context', 'pending', 'send', 'write', 'recv',
                  'read', 'renegotiate', 'bind', 'listen', 'connect',
                  'accept', 'setblocking', 'fileno', 'shutdown',
                  'close', 'get_cipher_list', 'getpeername',
                  'getsockname', 'getsockopt', 'setsockopt',
                  'makefile', 'get_app_data', 'set_app_data',
                  'state_string', 'sock_shutdown',
                  'get_peer_certificate', 'want_read', 'want_write',
                  'set_connect_state', 'set_accept_state',
                  'connect_ex', 'sendall'):

            exec """def %s(self, *args):
                self._lock.acquire()
                try:
                    return apply(self._ssl_conn.%s, args)
                finally:
                    self._lock.release()\n""" % (f, f)
sys.modules['OpenSSL.tsafe'] = tsafe

import operator
try:
    operator.attrgetter
except AttributeError:
    class attrgetter(object):
        def __init__(self, name):
            self.name = name
        def __call__(self, obj):
            return getattr(obj, self.name)
    operator.attrgetter = attrgetter


## Repair os.stat for Windows in python 2.3/2.4, if we have pywin32 installed.
import os
if sys.version_info[:2] < (2,5) and os.path.supports_unicode_filenames:
    try:
        import win32file, pywintypes
    except ImportError:
        pass
    else:
## This code is cribbed from Python 2.5's C implementation of stat on top of
## GetFileAttributesEx[W]. Even though the windows APIs actually report
## high-resolution UTC timestamps, PyWin32 "helpfully" converts the times to
## local time with only 1-second resolution.  Luckily, Python2.3 and 2.4 also
## only have 1-second resolution and timezone screwups (due to using MSCRT,
## which is designed especially to make life miserable for people trying to
## write portable programs), so, this doesn't actually hurt.  Yay, I guess...

        import calendar, time
        import stat as stat_mod

        def _PyTimeToUTC(pytime):
            """Convert the PyTime object (which is in local time) to a UTC number."""
            return calendar.timegm(time.localtime(int(pytime)))

        def _attributesToMode(attr):
            """Convert windowsish FILE_ATTRIBUTE_* to unixish mode."""
            m = 0
            if attr & win32file.FILE_ATTRIBUTE_DIRECTORY:
                m |= stat_mod.S_IFDIR | 0111
            else:
                m |= stat_mod.S_IFREG

            if attr & win32file.FILE_ATTRIBUTE_READONLY:
                m |= 0444
            else:
                m |= 0666
            return m

        def stat(fname):
            """stat(path) -> stat result

            Perform a stat system call on the given path.
            """

            try:
                 if isinstance(fname, unicode):
                     win_stat = win32file.GetFileAttributesExW(fname)
                 else:
                     win_stat = win32file.GetFileAttributesEx(fname)
            except pywintypes.error:
                raise OSError(2, 'No such file or directory: %r' % fname)

            ctime = _PyTimeToUTC(win_stat[1])
            atime = _PyTimeToUTC(win_stat[2])
            mtime = _PyTimeToUTC(win_stat[3])
            mode = _attributesToMode(win_stat[0])
            size = win_stat[4]

            # tuple is: mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime
            # dict contains the float times (which in this case don't actually have
            # higher precision.)
            if os.stat_float_times():
                time_type = float
            else:
                time_type = int
            result = os.stat_result((mode, 0L, 0, 0, 0, 0,
                                     size, atime, mtime, ctime),
                                    {'st_mtime': time_type(mtime),
                                     'st_atime': time_type(atime),
                                     'st_ctime': time_type(ctime)})
            return result

        stat.__module__ = 'os'
        os.stat = stat
