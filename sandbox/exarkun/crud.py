# -*- coding: Latin-1 -*-

import md5

##
correct = '8cf8b637395da8475d65aaf45e4cfad5'
user = "exarkun"
passwd = "password"
realm = "intarweb.us"
nonce = "abcdefg"
qop = "auth"
method = "REGISTER"
uri = "sip:intarweb.us"
nc = None
cnonce = None
##

##
correct = "d388dad90d4bbd760a152321f2143af7"
method = "LOGIN"
user = "chris"
passwd = "secret"
realm = "elwood.innosoft.com"
nonce = "OA6MG9tEQGm2hh"
nc = "00000001"
cnonce = "OA6MHXh6VqTrRk"
uri = "imap/elwood.innosoft.com"
qop = "auth"
##

##
correct = ''
method = "GET"
user = "Mufasa"
passwd = "Circle Of Life"
realm = "testrealm@host.com"
nonce = "dcd98b7102dd2f0e8b11d0f600bfb0c093"
nc = "00000001"
cnonce = "0a4f113b"
uri = "/dir/index.html"
qop = "auth"
##

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

def RESP(user, realm, pwd, nonce, cnonce, nc, qop, uri, method):
    a1 = H(A1(user, realm, pwd, nonce, cnonce))
    a2 = HEX(H(A2(uri, method)))

    if qop == "auth":
        return HEX(KD(a1, JOIN(nonce, a2)))
    else:
        return HEX(KD(a1, JOIN(nonce, nc, cnonce, qop, a2)))

def RESP(user, realm, pwd, nonce, cnonce, nc, qop, uri, method, algo='md5', bodyHash=''):
    front = md5.md5("%s:%s:%s" % (user, realm, pwd)).digest()
    if algo == "md5-sess":
        front = md5.md5("%s:%s:%s" % (front, nonce, cnonce)).hexdigest()
    
    back = "%s:%s" % (method, uri)
    if qop == "auth-int":
        back = "%s:%s" % (back, bodyHash)
    back = md5.md5(back).digest()
    
    response = "%s:%s" % (front, nonce)
    if qop:
        response = "%s:%s:%s:%s" % (response, nc, cnonce, qop)
    response = "%s:%s" % (response, back)
    response = md5.md5(response).hexdigest()
    return response
        

def g():
    return RESP(user, realm, passwd, nonce, cnonce, nc, qop, uri, method)


v = g()
print v == correct
print correct
print v
