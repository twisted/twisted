import random

def parseModuliFile(filename):
    lines = open(filename).readlines()
    primes = {}
    for l in lines:
        l = l.strip()
        if  not l or l[0]=='#':
            continue
        tim, typ, tst, tri, size, gen, mod = l.split()
        size = int(size) + 1
        gen = int(gen)
        mod = long(mod, 16)
        if not primes.has_key(size):
            primes[size] = []
        primes[size].append((gen, mod))
    return primes

def getDHPrimeOfBits(primes, bits):
    keys = primes.keys()
    keys.sort(lambda x,y:cmp(abs(x-bits),abs(y-bits)))
    realBits = keys[0]
    return random.choice(primes[realBits])