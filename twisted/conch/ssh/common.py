# -*- test-case-name: twisted.conch.test.test_ssh -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Common functions for the SSH classes.

Maintainer: Paul Swartz
"""

import struct, warnings

try:
    from Crypto import Util
except ImportError:
    warnings.warn("PyCrypto not installed, but continuing anyways!",
            RuntimeWarning)

from twisted.python import randbytes


def NS(t):
    """
    net string
    """
    return struct.pack('!L',len(t)) + t

def getNS(s, count=1):
    """
    get net string
    """
    ns = []
    c = 0
    for i in range(count):
        l, = struct.unpack('!L',s[c:c+4])
        ns.append(s[c+4:4+l+c])
        c += 4 + l
    return tuple(ns) + (s[c:],)

def MP(number):
    if number==0: return '\000'*4
    assert number>0
    bn = Util.number.long_to_bytes(number)
    if ord(bn[0])&128:
        bn = '\000' + bn
    return struct.pack('>L',len(bn)) + bn

def getMP(data, count=1):
    """
    Get multiple precision integer out of the string.  A multiple precision
    integer is stored as a 4-byte length followed by length bytes of the
    integer.  If count is specified, get count integers out of the string.
    The return value is a tuple of count integers followed by the rest of
    the data.
    """
    mp = []
    c = 0
    for i in range(count):
        length, = struct.unpack('>L',data[c:c+4])
        mp.append(Util.number.bytes_to_long(data[c+4:c+4+length]))
        c += 4 + length
    return tuple(mp) + (data[c:],)

def _MPpow(x, y, z):
    """return the MP version of (x**y)%z
    """
    return MP(pow(x,y,z))

def ffs(c, s):
    """
    first from second
    goes through the first list, looking for items in the second, returns the first one
    """
    for i in c:
        if i in s: return i

getMP_py = getMP
MP_py = MP
_MPpow_py = _MPpow
pyPow = pow

def _fastgetMP(data, count=1):
    mp = []
    c = 0
    for i in range(count):
        length = struct.unpack('!L', data[c:c+4])[0]
        mp.append(long(gmpy.mpz(data[c + 4:c + 4 + length][::-1] + '\x00', 256)))
        c += length + 4
    return tuple(mp) + (data[c:],)

def _fastMP(i):
    i2 = gmpy.mpz(i).binary()[::-1]
    return struct.pack('!L', len(i2)) + i2

def _fastMPpow(x, y, z=None):
    r = pyPow(gmpy.mpz(x),y,z).binary()[::-1]
    return struct.pack('!L', len(r)) + r

def install():
    global getMP, MP, _MPpow
    getMP = _fastgetMP
    MP = _fastMP
    _MPpow = _fastMPpow
    # XXX: We override builtin pow so that PyCrypto can benefit from gmpy too.
    def _fastpow(x, y, z=None, mpz=gmpy.mpz):
        if type(x) in (long, int):
            x = mpz(x)
        return pyPow(x, y, z)
    __builtins__['pow'] = _fastpow # evil evil

try:
    import gmpy
    install()
except ImportError:
    pass

