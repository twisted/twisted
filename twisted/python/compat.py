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

import os, sys, types, socket, struct, __builtin__, exceptions, UserDict

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


if not hasattr(socket, 'inet_pton'):
    def inet_pton(af, addr):
        if af == socket.AF_INET:
            parts = map(int, addr.split('.'))
            return struct.pack('!BBBB', *parts)
        elif af == getattr(socket, 'AF_INET6', None):
            parts = addr.split(':')
            elide = parts.count('')
            if elide == 3:
                return '\x00' * 16
            elif elide == 2:
                i = parts.index('')
                parts[i:i+2] = ['0'] * (10 - len(parts))
            elif elide == 1:
                i = parts.index('')
                parts[i:i+1] = ['0'] * (9 - len(parts))
            parts = [int(x, 16) for x in parts]
            return struct.pack('!HHHHHHHH', *parts)
        else:
            raise socket.error(97, 'Address family not supported by protocol')

    def inet_ntop(af, addr):
        if af == socket.AF_INET:
            parts = struct.unpack('!BBBB', addr)
            return '.'.join(map(str, parts))
        elif af == getattr(socket, 'AF_INET6', None):
            parts = struct.unpack('!HHHHHHHH', addr)
            return ':'.join([hex(x)[2:] for x in parts])
        else:
            raise socket.error(97, 'Address family not supported by protocol')

    socket.inet_pton = inet_pton
    socket.inet_ntop = inet_ntop

if sys.version_info[:3] in ((2, 2, 0), (2, 2, 1)):
    import string
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
