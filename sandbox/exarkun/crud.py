# -*- coding: Latin-1 -*-

import md5

user = "exarkun"
passwd = "password"
realm = "intarweb.us"
nonce = "abcdefg"
qop = "auth"
method = "REGISTER"
uri = "sip:exarkun@intarweb.us"

nc = cnonce = ''

def H(s):       
    return md5.md5(s).digest()

def KD(k, s):   
    return H(k + ":" + s)

def HEX(s):     
    return s.encode('hex')

def A1(user, realm, passwd, nonce, cnonce):
    return H(user + ":" + realm + ":" + passwd) + ":" + nonce
    return H(user + ":" + realm + ":" + passwd) + ":" + nonce + ":" + cnonce

def A2(uri, method):    
    return method + ":" + uri

def RESP(a1, nonce, nc, cnonce, qop, a2):
    return HEX(KD(H(a1), nonce + ":" + qop + ":" + HEX(H(a2))))
    return HEX(KD(H(a1), nonce + ":" + nc + ":" + cnonce + ":" + qop + ":" + HEX(H(a2))))

def g():
    return RESP(A1(user, realm, passwd, nonce, cnonce), nonce, nc, cnonce, qop, A2(uri, method))

correct = '8cf8b637395da8475d65aaf45e4cfad5'

print g(), correct, g() == correct
