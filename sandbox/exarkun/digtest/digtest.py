#!/usr/bin/python

import sys
from digcalc import DigestCalcHA1, DigestCalcResponse

def main(nonce, cnonce, user, realm, password, algo, ncount, method, qop, uri):
    print 'Response =', DigestCalcResponse(
        DigestCalcHA1(algo, user, realm, password, nonce, cnonce),
        nonce, ncount, cnonce, qop, method, uri, None
    )

if __name__ == '__main__':
    if len(sys.argv) != 11:
        print 'Usage: %s nonce cnonce user realm password algo ncount method qop uri' % (sys.argv[0],)
    else:
        main(*sys.argv[1:])
