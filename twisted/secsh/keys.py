# base library imports
import base64
import os.path
import string
import sha

# external library imports
from Crypto.PublicKey import RSA, DSA
from Crypto import Util

# sibling imports
import asn1, common

class BadKeyError(Exception):
    """
    raised when a key isn't what we expected from it.

    XXX: we really need to check for bad keys    
    """

def getPublicKeyString(filename, line=0):
    lines = open(filename).readlines()
    data = lines[line]
    fileKind, fileData, desc = data.split()
#    if fileKind != kind:
#        raise BadKeyError, 'key should be %s but instead is %s' % (kind, fileKind)
    return base64.decodestring(fileData)

def getPublicKeyObject(filename=None, line = 0, data = ''):
    if not filename:
        publicKey = data
    else:
        publicKey = getPublicKeyString(filename, line)
    keyKind, rest = common.getNS(publicKey)
    if keyKind == 'ssh-rsa':
        e, rest = common.getMP(rest)
        n, rest = common.getMP(rest)
        return RSA.construct((n,e))
    elif keyKind == 'ssh-dss':
        p, rest = common.getMP(rest)
        q, rest = common.getMP(rest)
        g, rest = common.getMP(rest)
        y, rest = common.getMP(rest)
        return DSA.construct((y,g,p,q))

def getPrivateKeyObject(filename):
    objectMapping = {
        'RSA':RSA,
        'DSA':DSA,
    }
    data = open(filename).readlines()
    kind = data[0][11:14]
    keyData = base64.decodestring(''.join(data[1:-1]))
    decodedKey = asn1.parse(keyData)
    return objectMapping[kind].construct(decodedKey[1:6])

def objectType(obj):
    keyDataMapping = {
        ('n', 'e', 'd', 'p','q'):'ssh-rsa',
        ('y', 'g', 'p', 'q', 'x'):'ssh-dss'
    }
    return keyDataMapping[tuple(obj.keydata)]

def pkcs1Pad(data, lMod):
    print 'len', lMod
    lenPad = lMod - 2 - len(data)
    return '\x01' + ('\xff'*lenPad) + '\x00' + data

def pkcs1Digest(data, lMod):
    digest = sha.new(data).digest()
    return pkcs1Pad(ID_SHA1 + digest, lMod)

def lenSig(obj):
    print 'obj size', obj.size()
    return obj.size()/8

def pkcs1Sign(obj, data):
    objType = objectType(obj)
    sigData =pkcs1Digest(data, lenSig(obj))
    sig = obj.sign(sigData, '\x03')
    if objType == 'ssh-dss':
        ret = ''.join(map(Util.number.long_to_bytes, sig))
    elif objType == 'ssh-rsa':
        ret = common.MP(sig[0])
    return common.NS(objType)+ret

def pkcs1Verify(obj, sig, data):
    objType = objectType(obj)
    sigType, sigData, rest = common.getNS(sig, 2)
    assert objType == sigType, 'object and signature are not of same type'
    #original = obj.encrypt(sigData, '\x03')[0] # make the data random
    if sigType == 'ssh-dss':
        sigTuple = map(Util.number.bytes_to_long, [sigData[:20],sigData[20:]])
        print sigTuple, len(sigData)
    elif sigType == 'ssh-rsa':
        sigTuple = [Util.number.bytes_to_long(sigData)]
    return obj.verify(pkcs1Digest(data, lenSig(obj)), sigTuple)

ID_SHA1 = '\x30\x21\x30\x09\x06\x05\x2b\x0e\x03\x02\x1a\x05\x00\x04\x14'
