# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# 

"""
Parsing for the moduli file, which contains Diffie-Hellman prime groups.

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
