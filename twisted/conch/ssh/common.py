# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
# 

"""Common functions for the SSH classes.

This module is unstable.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

import struct
from Crypto import Util
from Crypto.Util import randpool

entropy = randpool.RandomPool()
entropy.stir()


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
    for i in range(count):
        l = struct.unpack('!L',s[:4])[0]
        ns.append(s[4:4+l])
        s = s[4+l:]
    return tuple(ns) + (s,)

def MP(number):
    if number==0: return '\000'*4
    assert number>0
    bn = Util.number.long_to_bytes(number)
    if ord(bn[0])&128:
        bn = '\000' + bn
    return struct.pack('>L',len(bn)) + bn

def getMP(data):
    """
    get multiple precision integer
    """
    length=struct.unpack('>L',data[:4])[0]
    return Util.number.bytes_to_long(data[4:4+length]),data[4+length:]

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

def _fastgetMP(i):
    l = struct.unpack('!L', i[:4])[0]
    n = i[4:l+4][::-1]
    return long(gmpy.mpz(n+'\x00', 256)), i[4+l:]

def _fastMP(i):
    i2 = gmpy.mpz(i).binary()[::-1]
    return struct.pack('!L', len(i2)) + i2

def _fastMPpow(x, y, z=None):
    r = pow(gmpy.mpz(x),y,z).binary()[::-1]
    return struct.pack('!L', len(r)) + r

def _fastpow(x, y, z=None):
    return pyPow(gmpy.mpz(x), y, z)

try:
    import gmpy
    getMP = _fastgetMP
    MP = _fastMP
    _MPpow = _fastMPpow
    __builtins__['pow'] = _fastpow # this is probably evil
except ImportError:
    pass
