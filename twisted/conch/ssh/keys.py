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

"""Handling of RSA and DSA keys.

This module is unstable.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

# base library imports
import base64
import string
import sha, md5

# external library imports
from Crypto.Cipher import DES3
from Crypto.PublicKey import RSA, DSA
from Crypto import Util

#twisted
from twisted.python import log

# sibling imports
import asn1, common, sexpy


class BadKeyError(Exception):
    """
    raised when a key isn't what we expected from it.

    XXX: we really need to check for bad keys
    """

def getPublicKeyString(filename = None, line = 0, data = ''):
    """
    Return a public key string given a filename or data of a public key.
    Currently handles OpenSSH and LSH keys.

    @type filename: C{str}
    @type line:     C{int}
    @type data:     C{str}
    @rtype:         C{str}
    """
    if filename:
        lines = open(filename).readlines()
        data = lines[line]
    if data[0] == '{': # lsh key
        return getPublicKeyString_lsh(data)
    elif data.startswith('ssh-'): # openssh key
        return getPublicKeyString_openssh(data)
    else:
        raise BadKeyError('unknown type of key')

def getPublicKeyString_lsh(data):
    sexp = sexpy.parse(base64.decodestring(data[1:-1]))
    assert sexp[0] == 'public-key'
    kd = {}
    for name, data in sexp[1][1:]:
        kd[name] = common.NS(data)
    if sexp[1][0] == 'dsa':
        assert len(kd) == 4, len(kd)
        return '\x00\x00\x00\x07ssh-dss' + kd['p'] + kd['q'] + kd['g'] + kd['y']
    elif sexp[1][0] == 'rsa-pkcs1-sha1':
        assert len(kd) == 2, len(kd)
        return '\x00\x00\x00\x07ssh-rsa' + kd['e'] + kd['n']
    else:
        raise BadKeyError('unknown lsh key type %s' % sexp[1][0])

def getPublicKeyString_openssh(data):
    fileKind, fileData = data.split()[:2]
    #    if fileKind != kind:
    #        raise BadKeyError, 'key should be %s but instead is %s' % (kind, fileKind)
    return base64.decodestring(fileData)

def makePublicKeyString(obj, comment = '', kind = 'openssh'):
    """
    Return an public key given a C{Crypto.PublicKey.pubkey.pubkey}
    object.
    kind is one of ('openssh', 'lsh')

    @type obj:      C{Crypto.PublicKey.pubkey.pubkey}
    @type comment:  C{str}
    @type kind:     C{str}
    @rtype:         C{str}
    """

    if kind == 'lsh':
        return makePublicKeyString_lsh(obj) # no comment
    elif kind == 'openssh':
        return makePublicKeyString_openssh(obj, comment)
    else:
        raise BadKeyError('bad kind %s' % kind)

def makePublicKeyString_lsh(obj):
    keyType = objectType(obj)
    if keyType == 'ssh-rsa':
        keyData = sexpy.pack([['public-key', ['rsa-pkcs1-sha1',
                            ['n', common.MP(obj.n)[4:]],
                            ['e', common.MP(obj.e)[4:]]]]])
    elif keyType == 'ssh-dss':
        keyData = sexpy.pack([['public-key', ['dsa',
                            ['p', common.MP(obj.p)[4:]],
                            ['q', common.MP(obj.q)[4:]],
                            ['g', common.MP(obj.g)[4:]],
                            ['y', common.MP(obj.y)[4:]]]]])
    else:
        raise BadKeyError('bad keyType %s' % keyType)
    return '{' + base64.encodestring(keyData).replace('\n','') + '}'

def makePublicKeyString_openssh(obj, comment):
    keyType = objectType(obj)
    if keyType == 'ssh-rsa':
        keyData = common.MP(obj.e) + common.MP(obj.n)
    elif keyType == 'ssh-dss':
        keyData = common.MP(obj.p) 
        keyData += common.MP(obj.q) 
        keyData += common.MP(obj.g)
        keyData += common.MP(obj.y)
    else:
        raise BadKeyError('unknown key type %s' % keyType)
    b64Data = base64.encodestring(common.NS(keyType)+keyData).replace('\n', '')
    return '%s %s %s' % (keyType, b64Data, comment)
        

def getPublicKeyObject(data):
    """
    Return a C{Crypto.PublicKey.pubkey.pubkey} corresponding to the SSHv2
    public key data.  data is in the over-the-wire public key format.

    @type data:     C{str}
    @rtype:         C{Crypto.PublicKey.pubkey.pubkey}  
    """
    keyKind, rest = common.getNS(data)
    if keyKind == 'ssh-rsa':
        e, rest = common.getMP(rest)
        n, rest = common.getMP(rest)
        return RSA.construct((n, e))
    elif keyKind == 'ssh-dss':
        p, rest = common.getMP(rest)
        q, rest = common.getMP(rest)
        g, rest = common.getMP(rest)
        y, rest = common.getMP(rest)
        return DSA.construct((y, g, p, q))
    else:
        raise BadKeyError('unknown key type %s' % keyKind)

def getPrivateKeyObject(filename = None, data = '', passphrase = ''):
    """
    Return a C{Crypto.PublicKey.pubkey.pubkey} object corresponding to the
    private key file/data.  If the private key is encrypted, passphrase B{must}
    be specified, other wise a C{BadKeyError} will be raised.

    @type filename:     C{str}
    @type data:         C{str}
    @type passphrase:   C{str}
    @raises BadKeyError: if the key is invalid or a passphrase is not specified
    """
    if filename:
        data = open(filename).readlines()
    else:
        data = [x+'\n' for x in data.split('\n')]
    if data[0][0] == '(': # lsh key
        return getPrivateKeyObject_lsh(data, passphrase)
    elif data[0].startswith('-----'): # openssh key
        return getPrivateKeyObject_openssh(data, passphrase)
    else:
        raise BadKeyError('unknown private key type')

def getPrivateKeyObject_lsh(data, passphrase):
    #assert passphrase == ''
    data = ''.join(data)
    sexp = sexpy.parse(data)
    assert sexp[0] == 'private-key'
    kd = {}
    for name, data in sexp[1][1:]:
        kd[name] = common.getMP(common.NS(data))[0]
    if sexp[1][0] == 'dsa':
        assert len(kd) == 5, len(kd)
        return DSA.construct((kd['y'], kd['g'], kd['p'], kd['q'], kd['x']))
    elif sexp[1][0] == 'rsa-pkcs1':
        assert len(kd) == 8, len(kd)
        return RSA.construct((kd['n'], kd['e'], kd['d'], kd['p'], kd['q']))
    else:
        raise BadKeyError('unknown lsh key type %s' % sexp[1][0])

def getPrivateKeyObject_openssh(data, passphrase):
    kind = data[0][11: 14]
    if data[1].startswith('Proc-Type: 4,ENCRYPTED'): # encrypted key
        ivdata = data[2].split(',')[1][:-1]
        iv = ''.join([chr(int(ivdata[i:i+2],16)) for i in range(0, len(ivdata), 2)])
        if not passphrase:
            raise BadKeyError, 'encrypted key with no passphrase'
        ba = md5.new(passphrase + iv).digest()
        bb = md5.new(ba + passphrase + iv).digest()
        decKey = (ba + bb)[:24]
        b64Data = base64.decodestring(''.join(data[4:-1]))
        keyData = DES3.new(decKey, DES3.MODE_CBC, iv).decrypt(b64Data)
        removeLen = ord(keyData[-1])
        keyData = keyData[:-removeLen]
    else:
        keyData = base64.decodestring(''.join(data[1:-1]))
    try:
        decodedKey = asn1.parse(keyData)
    except Exception, e:
        raise BadKeyError, 'something wrong with decode'
    if type(decodedKey[0]) == type([]):
        decodedKey = decodedKey[0] # this happens with encrypted keys
    if kind == 'RSA':
        n,e,d,p,q=decodedKey[1:6]
        return RSA.construct((n,e,d,p,q))
    elif kind == 'DSA':
        p, q, g, y, x = decodedKey[1: 6]
        return DSA.construct((y, g, p, q, x))

def makePrivateKeyString(obj, passphrase = None, kind = 'openssh'):
    """
    Return an OpenSSH-style private key for a
    C{Crypto.PublicKey.pubkey.pubkey} object.  If passphrase is given, encrypt
    the private key with it.
    kind is one of ('openssh', 'lsh')

    @type obj:          C{Crypto.PublicKey.pubkey.pubkey}
    @type passphrase:   C{str}/C{None}
    @type kind:         C{str}
    @rtype:             C{str}
    """
    if kind == 'lsh':
        return makePrivateKeyString_lsh(obj, passphrase)
    elif kind == 'openssh':
        return makePrivateKeyString_openssh(obj, passphrase)
    else:
        raise BadKeyError('bad kind %s' % kind)

def makePrivateKeyString_lsh(obj, passphrase):
    #assert not passphrase
    keyType = objectType(obj)
    if keyType == 'ssh-rsa':
        p,q=obj.p,obj.q
        if p > q:
            (p,q)=(q,p)
        return sexpy.pack([['private-key', ['rsa-pkcs1',
                        ['n', common.MP(obj.n)[4:]],
                        ['e', common.MP(obj.e)[4:]],
                        ['d', common.MP(obj.d)[4:]],
                        ['p', common.MP(q)[4:]],
                        ['q', common.MP(p)[4:]],
                        ['a', common.MP(obj.d%(q-1))[4:]],
                        ['b', common.MP(obj.d%(p-1))[4:]],
                        ['c', common.MP(Util.number.inverse(p, q))[4:]]]]])
    elif keyType == 'ssh-dss':
        return sexpy.pack([['private-key', ['dsa',
                        ['p', common.MP(obj.p)[4:]],
                        ['q', common.MP(obj.q)[4:]],
                        ['g', common.MP(obj.g)[4:]],
                        ['y', common.MP(obj.y)[4:]],
                        ['x', common.MP(obj.x)[4:]]]]])
    else:
        raise BadKeyError('bad keyType %s' % keyType)

def makePrivateKeyString_openssh(obj, passphrase):
    keyType = objectType(obj)
    if keyType == 'ssh-rsa':
        keyData = '-----BEGIN RSA PRIVATE KEY-----\n'
        p,q=obj.p,obj.q
        if p > q:
            (p,q) = (q,p)
        # p is less than q
        objData = [0, obj.n, obj.e, obj.d, q, p, obj.d%(q-1), obj.d%(p-1),Util.number.inverse(p, q)]
    elif keyType == 'ssh-dss':
        keyData = '-----BEGIN DSA PRIVATE KEY-----\n'
        objData = [0, obj.p, obj.q, obj.g, obj.y, obj.x]
    else:
        raise BadKeyError('unknown key type %s' % keyType)
    if passphrase:
        iv = common.entropy.get_bytes(8)
        hexiv = ''.join(['%02X' % ord(x) for x in iv])
        keyData += 'Proc-Type: 4,ENCRYPTED\n'
        keyData += 'DEK-Info: DES-EDE3-CBC,%s\n\n' % hexiv
        ba = md5.new(passphrase + iv).digest()
        bb = md5.new(ba + passphrase + iv).digest()
        encKey = (ba + bb)[:24]
    asn1Data = asn1.pack([objData])
    if passphrase:
        padLen = 8 - (len(asn1Data) % 8)
        asn1Data += (chr(padLen) * padLen)
        asn1Data = DES3.new(encKey, DES3.MODE_CBC, iv).encrypt(asn1Data)
    b64Data = base64.encodestring(asn1Data).replace('\n','')
    b64Data = '\n'.join([b64Data[i:i+64] for i in range(0,len(b64Data),64)])
    keyData += b64Data + '\n'
    if keyType == 'ssh-rsa':
        keyData += '-----END RSA PRIVATE KEY-----'
    elif keyType == 'ssh-dss':
        keyData += '-----END DSA PRIVATE KEY-----'
    return keyData

def makePublicKeyBlob(obj):
    keyType = objectType(obj) 
    if keyType == 'ssh-rsa':
        keyData = common.MP(obj.e) + common.MP(obj.n)
    elif keyType == 'ssh-dss':
        keyData = common.MP(obj.p) 
        keyData += common.MP(obj.q) 
        keyData += common.MP(obj.g)
        keyData += common.MP(obj.y)
    return common.NS(keyType)+keyData

def makePrivateKeyBlob(obj):
    keyType = objectType(obj)
    if keyType == 'ssh-rsa':
        return common.NS(keyType) + common.MP(obj.n) + common.MP(obj.e) + \
               common.MP(obj.d) + common.MP(obj.u) + common.MP(obj.q) + \
               common.MP(obj.p)
    elif keyType == 'ssh-dss':
        return common.NS(keyType) + common.MP(obj.p) + common.MP(obj.q) + \
               common.MP(obj.g) + common.MP(obj.y) + common.MP(obj.x)
    else:
        raise ValueError('trying to get blob for invalid key type: %s' % keyType)

def objectType(obj):
    """
    Return the SSH key type corresponding to a C{Crypto.PublicKey.pubkey.pubkey}
    object.

    @type obj:  C{Crypto.PublicKey.pubkey.pubkey}
    @rtype:     C{str}
    """
    keyDataMapping = {
        ('n', 'e', 'd', 'p', 'q'): 'ssh-rsa',
        ('n', 'e', 'd', 'p', 'q', 'u'): 'ssh-rsa',
        ('y', 'g', 'p', 'q', 'x'): 'ssh-dss'
    }
    return keyDataMapping[tuple(obj.keydata)]

def pkcs1Pad(data, lMod):
    lenPad = lMod-2-len(data)
    return '\x01'+('\xff'*lenPad)+'\x00'+data

def pkcs1Digest(data, lMod):
    digest = sha.new(data).digest()
    return pkcs1Pad(ID_SHA1+digest, lMod)

def lenSig(obj):
    return obj.size()/8

def signData(obj, data):
    """
    Sign the data with the given C{Crypto.PublicKey.pubkey.pubkey} object.

    @type obj:  C{Crypto.PublicKey.pubkey.pubkey}
    @type data: C{str}
    @rtype:     C{str}
    """
    mapping = {
        'ssh-rsa': signData_rsa, 
        'ssh-dss': signData_dsa
    }
    objType = objectType(obj)
    return common.NS(objType)+mapping[objType](obj, data)

def signData_rsa(obj, data):
    sigData = pkcs1Digest(data, lenSig(obj))
    sig = obj.sign(sigData, '')[0]
    return common.NS(Util.number.long_to_bytes(sig)) # get around adding the \x00 byte

def signData_dsa(obj, data):
    sigData = sha.new(data).digest()
    randData = common.entropy.get_bytes(19)
    sig = obj.sign(sigData, randData)
    # SSH insists that the DSS signature blob be two 160-bit integers
    # concatenated together. The sig[0], [1] numbers from obj.sign are just
    # numbers, and could be any length from 0 to 160 bits. Make sure they
    # are padded out to 160 bits (20 bytes each)
    return common.NS(Util.number.long_to_bytes(sig[0], 20) +
                     Util.number.long_to_bytes(sig[1], 20))

def verifySignature(obj, sig, data):
    """
    Verify that the signature for the data is valid.

    @type obj:  C{Crypto.PublicKey.pubkey.pubkey}
    @type sig:  C{str}
    @type data: C{str}
    @rtype:     C{bool}
    """
    mapping = {
        'ssh-rsa': verifySignature_rsa, 
        'ssh-dss': verifySignature_dsa, 
     }
    objType = objectType(obj)
    sigType, sigData = common.getNS(sig)
    if objType != sigType: # object and signature are not of same type
        return 0
    return mapping[objType](obj, sigData, data)

def verifySignature_rsa(obj, sig, data):
    sigTuple = [common.getMP(sig)[0]]
    return obj.verify(pkcs1Digest(data, lenSig(obj)), sigTuple)

def verifySignature_dsa(obj, sig, data):
    sig = common.getNS(sig)[0]
    assert(len(sig) == 40)
    l = len(sig)/2
    sigTuple = map(Util.number.bytes_to_long, [sig[: l], sig[l:]])
    return obj.verify(sha.new(data).digest(), sigTuple)

def printKey(obj):
    """
    Pretty print a C{Crypto.PublicKey.pubkey.pubkey} object.

    @type obj: C{Crypto.PublicKey.pubkey.pubkey}
    """
    print '%s %s (%s bits)'%(objectType(obj), 
                               obj.hasprivate()and 'Private Key'or 'Public Key', 
                               obj.size())
    for k in obj.keydata:
        if hasattr(obj, k):
            print 'attr', k
            by = common.MP(getattr(obj, k))[4:]
            while by:
                m = by[: 15]
                by = by[15:]
                o = ''
                for c in m:
                    o = o+'%02x:'%ord(c)
                if len(m) < 15:
                    o = o[:-1]
                print '\t'+o

ID_SHA1 = '\x30\x21\x30\x09\x06\x05\x2b\x0e\x03\x02\x1a\x05\x00\x04\x14'
