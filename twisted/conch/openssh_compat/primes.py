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

"""Parsing for the moduli file, which contains Diffie-Hellman prime groups.

This module is unstable.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

def parseModuliFile(filename):
    lines = open(filename).readlines()
    primes = {}
    for l in lines:
        l = l.strip()
        if  not l or l[0]=='#':
            continue
        tim, typ, tst, tri, size, gen, mod = l.split()
        size = int(size) + 1
        gen = long(gen)
        mod = long(mod, 16)
        if not primes.has_key(size):
            primes[size] = []
        primes[size].append((gen, mod))
    return primes
