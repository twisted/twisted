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
# base library imports
import base64
import os.path
import string
import sha

# external library imports
from Crypto.PublicKey import RSA, DSA
from Crypto import Util

#twisted
from twisted.python import log

# sibling imports
import asn1, common


class BadKeyError(Exception):
    """
    raised when a key isn't what we expected from it.

    XXX: we really need to check for bad keys
    """

def getPublicKeyString(filename = None, line = 0, data = ''):
    if filename:
        lines = open(filename).readlines()
        data = lines[line]
    fileKind, fileData, desc = data.split()
    #    if fileKind != kind:
    #        raise BadKeyError, 'key should be %s but instead is %s' % (kind, fileKind)
    return base64.decodestring(fileData)

def getPublicKeyObject(filename = None, line = 0, data = '', b64data = ''):
    # b64data is the kind of data we'd get from reading a key file
    if data:
        publicKey = data
    elif b64data:
        publicKey = getPublicKeyString(data = b64data)
    else:
        publicKey = getPublicKeyString(filename, line)
    keyKind, rest = common.getNS(publicKey)
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

def getPrivateKeyObject(filename = None, data = ''):
    if filename:
        data = open(filename).readlines()
    else:
        data = [x+'\n' for x in data.split('\n')]
    kind = data[0][11: 14]
    keyData = base64.decodestring(''.join(data[1:-1]))
    decodedKey = asn1.parse(keyData)
    if kind == 'RSA':
        return RSA.construct(decodedKey[1: 6])
    elif kind == 'DSA':
        p, q, g, y, x = decodedKey[1: 6]
        return DSA.construct((y, g, p, q, x))
    
def objectType(obj):
    keyDataMapping = {
    ('n', 'e', 'd', 'p', 'q'): 'ssh-rsa', 
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
    return common.NS(''.join(map(Util.number.long_to_bytes, sig)))

def verifySignature(obj, sig, data):
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
    l = len(sig)/2
    sigTuple = map(Util.number.bytes_to_long, [sig[: l], sig[l:]])
    return obj.verify(sha.new(data).digest(), sigTuple)

def printKey(obj):
    log.msg('%s %s (%s bits)'%(objectType(obj), 
                               obj.hasprivate()and 'Private Key'or 'Public Key', 
                               obj.size()))
    for k in obj.keydata:
        if hasattr(obj, k):
            log.msg('attr', k)
            by = common.MP(getattr(obj, k))[4:]
            while by:
                m = by[: 15]
                by = by[15:]
                o = ''
                for c in m:
                    o = o+'%02x:'%ord(c)
                if len(m) < 15:
                    o = o[:-1]
                log.msg('\t'+o)

ID_SHA1 = '\x30\x21\x30\x09\x06\x05\x2b\x0e\x03\x02\x1a\x05\x00\x04\x14'

