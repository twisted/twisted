# -*- coding: Latin-1 -*-

import md5

user = "exarkun"
passwd = "password"
realm = "intarweb.us"
nonce = "abcdefg"
qop = "auth"
method = "REGISTER"
uri = "sip:exarkun@intarweb.us"

nc = cnonce = None

def H(s):       
    return md5.md5(s).digest()

def KD(k, s):   
    return H(JOIN(k, s))

def HEX(s):     
    return s.encode('hex')

def JOIN(*a):
    return ":".join(a)

def A1(user, realm, passwd, nonce, cnonce):
    if cnonce:
        return JOIN(H(JOIN(user, realm, passwd)), nonce, cnonce)
    return JOIN(H(JOIN(user, realm, passwd)), nonce)

def A2(uri, method):    
    return method + ":" + uri

def RESP(a1, nonce, nc, cnonce, qop, a2):
    if qop == "auth":
        return HEX(KD(H(a1), JOIN(nonce, HEX(H(a2)))))
    else:
        return HEX(KD(H(a1), JOIN(nonce, nc, cnonce, qop, HEX(H(a2)))))

def g():
    return RESP(A1(user, realm, passwd, nonce, cnonce), nonce, nc, cnonce, qop, A2(uri, method))

correct = '8cf8b637395da8475d65aaf45e4cfad5'

v = g()
print v == correct
print correct
print v
