# -*- test-case-name: twisted.conch.test.test_ssh -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Common functions for the SSH classes.

Maintainer: Paul Swartz
"""
from __future__ import absolute_import, division

import binascii
import struct

from twisted.python.compat import _PY3, long


def bytes_to_int(b):
    return int(binascii.hexlify(b), 16)



def int_to_bytes(val, endianness='big'):
    """
    From: http://stackoverflow.com/a/14527004/539264

    FIXME add padding

    Use :ref:`string formatting` and :func:`~binascii.unhexlify` to
    convert ``val``, a :func:`long`, to a byte :func:`str`.

    :param long val: The value to pack

    :param str endianness: The endianness of the result. ``'big'`` for
      big-endian, ``'little'`` for little-endian.

    If you want byte- and word-ordering to differ, you're on your own.

    Using :ref:`string formatting` lets us use Python's C innards.
    """

    # one (1) hex digit per four (4) bits
    width = val.bit_length()

    # unhexlify wants an even multiple of eight (8) bits, but we don't
    # want more digits than we need (hence the ternary-ish 'or')
    width += 8 - ((width % 8) or 8)

    # format width specifier: four (4) bits per hex digit
    fmt = '%%0%dx' % (width // 4)

    # prepend zero (0) to the width, to zero-pad the output
    s = binascii.unhexlify(fmt % val)

    if endianness == 'little':
        # see http://stackoverflow.com/a/931095/309233
        s = s[::-1]

    return s



def NS(t):
    """
    net string
    """
    return struct.pack('!L', len(t)) + t



def getNS(s, count=1):
    """
    get net string
    """
    ns = []
    c = 0
    for i in range(count):
        l, = struct.unpack('!L',s[c:c + 4])
        ns.append(s[c + 4:4 + l + c])
        c += 4 + l
    return tuple(ns) + (s[c:],)



def MP(number):
    if number == 0: return b'\000'*4
    assert number > 0
    bn = int_to_bytes(number)
    if ord(bn[0:1]) & 128:
        bn = b'\000' + bn
    return struct.pack('>L', len(bn)) + bn



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
        length, = struct.unpack('>L', data[c:c + 4])
        mp.append(bytes_to_int(data[c + 4:c + 4 + length]))
        c += 4 + length
    return tuple(mp) + (data[c:],)



def _MPpow(x, y, z):
    """
    Return the MP version of C{(x ** y) % z}.
    """
    return MP(pow(x,y,z))



def ffs(c, s):
    """
    first from second
    goes through the first list, looking for items in the second, returns the first one
    """
    for i in c:
        if i in s:
            return i



getMP_py = getMP
MP_py = MP
_MPpow_py = _MPpow
pyPow = pow



def _fastgetMP(data, count=1):
    mp = []
    c = 0
    for i in range(count):
        length = struct.unpack('!L', data[c:c + 4])[0]
        mp.append(long(
            gmpy.mpz(data[c + 4:c + 4 + length][::-1] + b'\x00', 256)))
        c += length + 4
    return tuple(mp) + (data[c:],)



def _fastMP(i):
    i2 = gmpy.mpz(i).binary()[::-1]
    return struct.pack('!L', len(i2)) + i2



def _fastMPpow(x, y, z=None):
    r = pyPow(gmpy.mpz(x), y, z).binary()[::-1]
    return struct.pack('!L', len(r)) + r



def install():
    global getMP, MP, _MPpow
    getMP = _fastgetMP
    MP = _fastMP
    _MPpow = _fastMPpow
    # XXX: We override builtin pow so that other code can benefit too.
    # This is monkeypatching, and therefore VERY BAD.
    def _fastpow(x, y, z=None, mpz=gmpy.mpz):
        if type(x) in (long, int):
            x = mpz(x)
        return pyPow(x, y, z)
    if not _PY3:
        import __builtin__
        __builtin__.pow = _fastpow
    else:
        __builtins__['pow'] = _fastpow

try:
    import gmpy
    install()
except ImportError:
    pass
