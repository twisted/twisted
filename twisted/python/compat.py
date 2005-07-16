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

from __future__ import generators

import os, sys, string, types, socket, struct, __builtin__, exceptions, UserDict

#elif sys.version_info[:2] == (2, 2):
#    def dict(*arg, **kwargs):
#        d = types.DictType(*arg)
#        d.update(kwargs)
#        return d
#    dict.__doc__ = _dict_doc
#    __builtin__.dict = dict


if not hasattr(UserDict, 'DictMixin'):
    from twisted.python.pymodules import UserDictExtras
    UserDict.DictMixin = UserDictExtras.DictMixin

try:
    import heapq
except ImportError:
    from twisted.python.pymodules import heapq
    sys.modules['heapq'] = heapq

if sys.version_info[:3] == (2, 2, 0):
    __builtin__.True = (1 == 1)
    __builtin__.False = (1 == 0)
    def bool(value):
        """Demote a value to 0 or 1, depending on its truth value

        This is not to be confused with types.BooleanType, which is
        way too hard to duplicate in 2.1 to be worth the trouble.
        """
        return not not value
    __builtin__.bool = bool
    del bool

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

if sys.version_info[:3] in ((2, 2, 0), (2, 2, 1)):
    def lstrip(s, c=string.whitespace):
        while s and s[0] in c:
            s = s[1:]
        return s
    def rstrip(s, c=string.whitespace):
        while s and s[-1] in c:
            s = s[:-1]
        return s
    def strip(s, c=string.whitespace, l=lstrip, r=rstrip):
        return l(r(s, c), c)

    object.__setattr__(str, 'lstrip', lstrip)
    object.__setattr__(str, 'rstrip', rstrip)
    object.__setattr__(str, 'strip', strip)

# dict(key=value) compatibility hack
if sys.version_info[:2] == (2,2):
    def adict(mapping=None, **kw):
        d = {}
        if mapping is not None:
            d.update(dict(mapping))
        if kw:
            for k, v in kw.iteritems():
                d[k] = v
        return d
else:
    adict = dict

try:
    os.walk
except AttributeError:
    def walk(top, topdown=True, onerror=None):
        from os.path import join, isdir, islink

        try:
            names = os.listdir(top)
        except OSError, e:
            if onerror is not None:
                onerror(err)
            return

        nondir, dir = [], []
        nameLists = [nondir, dir]
        for name in names:
            nameLists[isdir(join(top, name))].append(name)

        if topdown:
            yield top, dir, nondir

        for name in dir:
            path = join(top, name)
            if not islink(path):
                for x in walk(path, topdown, onerror):
                    yield x

        if not topdown:
            yield top, dir, nondir
    os.walk = walk

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


# Compatibility with compatibility
# We want to get rid of these as quickly as we can
# Unfortunately some code imports them by name

True = True
False = False
bool = bool
dict = dict
StopIteration = StopIteration
iter = iter
isinstance = isinstance
