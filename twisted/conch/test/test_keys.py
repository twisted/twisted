# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.conch.ssh.keys}.
"""

try:
    import Crypto.Cipher.DES3
except ImportError:
    # we'll have to skip these tests without PyCypto and pyasn1
    Crypto = None

try:
    import pyasn1
except ImportError:
    pyasn1 = None

if Crypto and pyasn1:
    from twisted.conch.ssh import keys, common, sexpy

import os, base64
from twisted.conch.test import keydata
from twisted.python import randbytes
from twisted.python.hashlib import sha1
from twisted.trial import unittest


class HelpersTestCase(unittest.TestCase):

    if Crypto is None:
        skip = "cannot run w/o PyCrypto"
    if pyasn1 is None:
        skip = "Cannot run without PyASN1"

    def setUp(self):
        self._secureRandom = randbytes.secureRandom
        randbytes.secureRandom = lambda x: '\x55' * x

    def tearDown(self):
        randbytes.secureRandom = self._secureRandom
        self._secureRandom = None

    def test_pkcs1(self):
        """
        Test Public Key Cryptographic Standard #1 functions.
        """
        data = 'ABC'
        messageSize = 6
        self.assertEqual(keys.pkcs1Pad(data, messageSize),
                '\x01\xff\x00ABC')
        hash = sha1().digest()
        messageSize = 40
        self.assertEqual(keys.pkcs1Digest('', messageSize),
                '\x01\xff\xff\xff\x00' + keys.ID_SHA1 + hash)

    def _signRSA(self, data):
        key = keys.Key.fromString(keydata.privateRSA_openssh)
        sig = key.sign(data)
        return key.keyObject, sig

    def _signDSA(self, data):
        key = keys.Key.fromString(keydata.privateDSA_openssh)
        sig = key.sign(data)
        return key.keyObject, sig

    def test_signRSA(self):
        """
        Test that RSA keys return appropriate signatures.
        """
        data = 'data'
        key, sig = self._signRSA(data)
        sigData = keys.pkcs1Digest(data, keys.lenSig(key))
        v = key.sign(sigData, '')[0]
        self.assertEqual(sig, common.NS('ssh-rsa') + common.MP(v))
        return key, sig

    def test_signDSA(self):
        """
        Test that DSA keys return appropriate signatures.
        """
        data = 'data'
        key, sig = self._signDSA(data)
        sigData = sha1(data).digest()
        v = key.sign(sigData, '\x55' * 19)
        self.assertEqual(sig, common.NS('ssh-dss') + common.NS(
            Crypto.Util.number.long_to_bytes(v[0], 20) +
            Crypto.Util.number.long_to_bytes(v[1], 20)))
        return key, sig


    def test_objectType(self):
        """
        Test that objectType, returns the correct type for objects.
        """
        self.assertEqual(keys.objectType(keys.Key.fromString(
            keydata.privateRSA_openssh).keyObject), 'ssh-rsa')
        self.assertEqual(keys.objectType(keys.Key.fromString(
            keydata.privateDSA_openssh).keyObject), 'ssh-dss')
        self.assertRaises(keys.BadKeyError, keys.objectType, None)


class KeyTestCase(unittest.TestCase):

    if Crypto is None:
        skip = "cannot run w/o PyCrypto"
    if pyasn1 is None:
        skip = "Cannot run without PyASN1"

    def setUp(self):
        self.rsaObj = Crypto.PublicKey.RSA.construct((1L, 2L, 3L, 4L, 5L))
        self.dsaObj = Crypto.PublicKey.DSA.construct((1L, 2L, 3L, 4L, 5L))
        self.rsaSignature = ('\x00\x00\x00\x07ssh-rsa\x00'
            '\x00\x00`N\xac\xb4@qK\xa0(\xc3\xf2h \xd3\xdd\xee6Np\x9d_'
            '\xb0>\xe3\x0c(L\x9d{\txUd|!\xf6m\x9c\xd3\x93\x842\x7fU'
            '\x05\xf4\xf7\xfaD\xda\xce\x81\x8ea\x7f=Y\xed*\xb7\xba\x81'
            '\xf2\xad\xda\xeb(\x97\x03S\x08\x81\xc7\xb1\xb7\xe6\xe3'
            '\xcd*\xd4\xbd\xc0wt\xf7y\xcd\xf0\xb7\x7f\xfb\x1e>\xf9r'
            '\x8c\xba')
        self.dsaSignature = ('\x00\x00\x00\x07ssh-dss\x00\x00'
            '\x00(\x18z)H\x8a\x1b\xc6\r\xbbq\xa2\xd7f\x7f$\xa7\xbf'
            '\xe8\x87\x8c\x88\xef\xd9k\x1a\x98\xdd{=\xdec\x18\t\xe3'
            '\x87\xa9\xc72h\x95')
        self.oldSecureRandom = randbytes.secureRandom
        randbytes.secureRandom = lambda x: '\xff' * x
        self.keyFile = self.mktemp()
        file(self.keyFile, 'wb').write(keydata.privateRSA_lsh)

    def tearDown(self):
        randbytes.secureRandom = self.oldSecureRandom
        del self.oldSecureRandom
        os.unlink(self.keyFile)

    def test__guessStringType(self):
        """
        Test that the _guessStringType method guesses string types
        correctly.
        """
        self.assertEqual(keys.Key._guessStringType(keydata.publicRSA_openssh),
                'public_openssh')
        self.assertEqual(keys.Key._guessStringType(keydata.publicDSA_openssh),
                'public_openssh')
        self.assertEqual(keys.Key._guessStringType(
            keydata.privateRSA_openssh), 'private_openssh')
        self.assertEqual(keys.Key._guessStringType(
            keydata.privateDSA_openssh), 'private_openssh')
        self.assertEqual(keys.Key._guessStringType(keydata.publicRSA_lsh),
                'public_lsh')
        self.assertEqual(keys.Key._guessStringType(keydata.publicDSA_lsh),
                'public_lsh')
        self.assertEqual(keys.Key._guessStringType(keydata.privateRSA_lsh),
                'private_lsh')
        self.assertEqual(keys.Key._guessStringType(keydata.privateDSA_lsh),
                'private_lsh')
        self.assertEqual(keys.Key._guessStringType(
            keydata.privateRSA_agentv3), 'agentv3')
        self.assertEqual(keys.Key._guessStringType(
            keydata.privateDSA_agentv3), 'agentv3')
        self.assertEqual(keys.Key._guessStringType(
            '\x00\x00\x00\x07ssh-rsa\x00\x00\x00\x01\x01'),
            'blob')
        self.assertEqual(keys.Key._guessStringType(
            '\x00\x00\x00\x07ssh-dss\x00\x00\x00\x01\x01'),
            'blob')
        self.assertEqual(keys.Key._guessStringType('not a key'),
                None)

    def _testPublicPrivateFromString(self, public, private, type, data):
        self._testPublicFromString(public, type, data)
        self._testPrivateFromString(private, type, data)

    def _testPublicFromString(self, public, type, data):
        publicKey = keys.Key.fromString(public)
        self.assertTrue(publicKey.isPublic())
        self.assertEqual(publicKey.type(), type)
        for k, v in publicKey.data().items():
            self.assertEqual(data[k], v)

    def _testPrivateFromString(self, private, type, data):
        privateKey = keys.Key.fromString(private)
        self.assertFalse(privateKey.isPublic())
        self.assertEqual(privateKey.type(), type)
        for k, v in data.items():
            self.assertEqual(privateKey.data()[k], v)

    def test_fromOpenSSH(self):
        """
        Test that keys are correctly generated from OpenSSH strings.
        """
        self._testPublicPrivateFromString(keydata.publicRSA_openssh,
                keydata.privateRSA_openssh, 'RSA', keydata.RSAData)
        self.assertEqual(keys.Key.fromString(
            keydata.privateRSA_openssh_encrypted,
            passphrase='encrypted'),
            keys.Key.fromString(keydata.privateRSA_openssh))
        self.assertEqual(keys.Key.fromString(
            keydata.privateRSA_openssh_alternate),
            keys.Key.fromString(keydata.privateRSA_openssh))
        self._testPublicPrivateFromString(keydata.publicDSA_openssh,
                keydata.privateDSA_openssh, 'DSA', keydata.DSAData)

    def test_fromOpenSSH_with_whitespace(self):
        """
        If key strings have trailing whitespace, it should be ignored.
        """
        # from bug #3391, since our test key data doesn't have
        # an issue with appended newlines
        privateDSAData = """-----BEGIN DSA PRIVATE KEY-----
MIIBuwIBAAKBgQDylESNuc61jq2yatCzZbenlr9llG+p9LhIpOLUbXhhHcwC6hrh
EZIdCKqTO0USLrGoP5uS9UHAUoeN62Z0KXXWTwOWGEQn/syyPzNJtnBorHpNUT9D
Qzwl1yUa53NNgEctpo4NoEFOx8PuU6iFLyvgHCjNn2MsuGuzkZm7sI9ZpQIVAJiR
9dPc08KLdpJyRxz8T74b4FQRAoGAGBc4Z5Y6R/HZi7AYM/iNOM8su6hrk8ypkBwR
a3Dbhzk97fuV3SF1SDrcQu4zF7c4CtH609N5nfZs2SUjLLGPWln83Ysb8qhh55Em
AcHXuROrHS/sDsnqu8FQp86MaudrqMExCOYyVPE7jaBWW+/JWFbKCxmgOCSdViUJ
esJpBFsCgYEA7+jtVvSt9yrwsS/YU1QGP5wRAiDYB+T5cK4HytzAqJKRdC5qS4zf
C7R0eKcDHHLMYO39aPnCwXjscisnInEhYGNblTDyPyiyNxAOXuC8x7luTmwzMbNJ
/ow0IqSj0VF72VJN9uSoPpFd4lLT0zN8v42RWja0M8ohWNf+YNJluPgCFE0PT4Vm
SUrCyZXsNh6VXwjs3gKQ
-----END DSA PRIVATE KEY-----"""
        self.assertEqual(keys.Key.fromString(privateDSAData),
                         keys.Key.fromString(privateDSAData + '\n'))

    def test_fromLSH(self):
        """
        Test that keys are correctly generated from LSH strings.
        """
        self._testPublicPrivateFromString(keydata.publicRSA_lsh,
                keydata.privateRSA_lsh, 'RSA', keydata.RSAData)
        self._testPublicPrivateFromString(keydata.publicDSA_lsh,
                keydata.privateDSA_lsh, 'DSA', keydata.DSAData)
        sexp = sexpy.pack([['public-key', ['bad-key', ['p', '2']]]])
        self.assertRaises(keys.BadKeyError, keys.Key.fromString,
                data='{'+base64.encodestring(sexp)+'}')
        sexp = sexpy.pack([['private-key', ['bad-key', ['p', '2']]]])
        self.assertRaises(keys.BadKeyError, keys.Key.fromString,
                sexp)

    def test_fromAgentv3(self):
        """
        Test that keys are correctly generated from Agent v3 strings.
        """
        self._testPrivateFromString(keydata.privateRSA_agentv3, 'RSA',
                keydata.RSAData)
        self._testPrivateFromString(keydata.privateDSA_agentv3, 'DSA',
                keydata.DSAData)
        self.assertRaises(keys.BadKeyError, keys.Key.fromString,
                '\x00\x00\x00\x07ssh-foo'+'\x00\x00\x00\x01\x01'*5)

    def test_fromStringErrors(self):
        """
        keys.Key.fromString should raise BadKeyError when the key is invalid.
        """
        self.assertRaises(keys.BadKeyError, keys.Key.fromString, '')
        # no key data with a bad key type
        self.assertRaises(keys.BadKeyError, keys.Key.fromString, '',
                'bad_type')
        # trying to decrypt a key which doesn't support encryption
        self.assertRaises(keys.BadKeyError, keys.Key.fromString,
                keydata.publicRSA_lsh, passphrase = 'unencrypted')
        # trying to decrypt an unencrypted key
        self.assertRaises(keys.EncryptedKeyError, keys.Key.fromString,
                keys.Key(self.rsaObj).toString('openssh', 'encrypted'))
        # key with no key data
        self.assertRaises(keys.BadKeyError, keys.Key.fromString,
                '-----BEGIN RSA KEY-----\nwA==\n')

    def test_fromFile(self):
        """
        Test that fromFile works correctly.
        """
        self.assertEqual(keys.Key.fromFile(self.keyFile),
                keys.Key.fromString(keydata.privateRSA_lsh))
        self.assertRaises(keys.BadKeyError, keys.Key.fromFile,
                self.keyFile, 'bad_type')
        self.assertRaises(keys.BadKeyError, keys.Key.fromFile,
                self.keyFile, passphrase='unencrypted')

    def test_init(self):
        """
        Test that the PublicKey object is initialized correctly.
        """
        obj = Crypto.PublicKey.RSA.construct((1L, 2L))
        key = keys.Key(obj)
        self.assertEqual(key.keyObject, obj)

    def test_equal(self):
        """
        Test that Key objects are compared correctly.
        """
        rsa1 = keys.Key(self.rsaObj)
        rsa2 = keys.Key(self.rsaObj)
        rsa3 = keys.Key(Crypto.PublicKey.RSA.construct((1L, 2L)))
        dsa = keys.Key(self.dsaObj)
        self.assertTrue(rsa1 == rsa2)
        self.assertFalse(rsa1 == rsa3)
        self.assertFalse(rsa1 == dsa)
        self.assertFalse(rsa1 == object)
        self.assertFalse(rsa1 == None)

    def test_notEqual(self):
        """
        Test that Key objects are not-compared correctly.
        """
        rsa1 = keys.Key(self.rsaObj)
        rsa2 = keys.Key(self.rsaObj)
        rsa3 = keys.Key(Crypto.PublicKey.RSA.construct((1L, 2L)))
        dsa = keys.Key(self.dsaObj)
        self.assertFalse(rsa1 != rsa2)
        self.assertTrue(rsa1 != rsa3)
        self.assertTrue(rsa1 != dsa)
        self.assertTrue(rsa1 != object)
        self.assertTrue(rsa1 != None)

    def test_type(self):
        """
        Test that the type method returns the correct type for an object.
        """
        self.assertEqual(keys.Key(self.rsaObj).type(), 'RSA')
        self.assertEqual(keys.Key(self.rsaObj).sshType(), 'ssh-rsa')
        self.assertEqual(keys.Key(self.dsaObj).type(), 'DSA')
        self.assertEqual(keys.Key(self.dsaObj).sshType(), 'ssh-dss')
        self.assertRaises(RuntimeError, keys.Key(None).type)
        self.assertRaises(RuntimeError, keys.Key(None).sshType)
        self.assertRaises(RuntimeError, keys.Key(self).type)
        self.assertRaises(RuntimeError, keys.Key(self).sshType)

    def test_fromBlob(self):
        """
        Test that a public key is correctly generated from a public key blob.
        """
        rsaBlob = common.NS('ssh-rsa') + common.MP(2) + common.MP(3)
        rsaKey = keys.Key.fromString(rsaBlob)
        dsaBlob = (common.NS('ssh-dss') + common.MP(2) + common.MP(3) +
                common.MP(4) + common.MP(5))
        dsaKey = keys.Key.fromString(dsaBlob)
        badBlob = common.NS('ssh-bad')
        self.assertTrue(rsaKey.isPublic())
        self.assertEqual(rsaKey.data(), {'e':2L, 'n':3L})
        self.assertTrue(dsaKey.isPublic())
        self.assertEqual(dsaKey.data(), {'p':2L, 'q':3L, 'g':4L, 'y':5L})
        self.assertRaises(keys.BadKeyError,
                keys.Key.fromString, badBlob)


    def test_fromPrivateBlob(self):
        """
        Test that a private key is correctly generated from a private key blob.
        """
        rsaBlob = (common.NS('ssh-rsa') + common.MP(2) + common.MP(3) +
                   common.MP(4) + common.MP(5) + common.MP(6) + common.MP(7))
        rsaKey = keys.Key._fromString_PRIVATE_BLOB(rsaBlob)
        dsaBlob = (common.NS('ssh-dss') + common.MP(2) + common.MP(3) +
                   common.MP(4) + common.MP(5) + common.MP(6))
        dsaKey = keys.Key._fromString_PRIVATE_BLOB(dsaBlob)
        badBlob = common.NS('ssh-bad')
        self.assertFalse(rsaKey.isPublic())
        self.assertEqual(
            rsaKey.data(), {'n':2L, 'e':3L, 'd':4L, 'u':5L, 'p':6L, 'q':7L})
        self.assertFalse(dsaKey.isPublic())
        self.assertEqual(dsaKey.data(), {'p':2L, 'q':3L, 'g':4L, 'y':5L, 'x':6L})
        self.assertRaises(
            keys.BadKeyError, keys.Key._fromString_PRIVATE_BLOB, badBlob)


    def test_blob(self):
        """
        Test that the Key object generates blobs correctly.
        """
        self.assertEqual(keys.Key(self.rsaObj).blob(),
                '\x00\x00\x00\x07ssh-rsa\x00\x00\x00\x01\x02'
                '\x00\x00\x00\x01\x01')
        self.assertEqual(keys.Key(self.dsaObj).blob(),
                '\x00\x00\x00\x07ssh-dss\x00\x00\x00\x01\x03'
                '\x00\x00\x00\x01\x04\x00\x00\x00\x01\x02'
                '\x00\x00\x00\x01\x01')

        badKey = keys.Key(None)
        self.assertRaises(RuntimeError, badKey.blob)


    def test_privateBlob(self):
        """
        L{Key.privateBlob} returns the SSH protocol-level format of the private
        key and raises L{RuntimeError} if the underlying key object is invalid.
        """
        self.assertEqual(keys.Key(self.rsaObj).privateBlob(),
                '\x00\x00\x00\x07ssh-rsa\x00\x00\x00\x01\x01'
                '\x00\x00\x00\x01\x02\x00\x00\x00\x01\x03\x00'
                '\x00\x00\x01\x04\x00\x00\x00\x01\x04\x00\x00'
                '\x00\x01\x05')
        self.assertEqual(keys.Key(self.dsaObj).privateBlob(),
                '\x00\x00\x00\x07ssh-dss\x00\x00\x00\x01\x03'
                '\x00\x00\x00\x01\x04\x00\x00\x00\x01\x02\x00'
                '\x00\x00\x01\x01\x00\x00\x00\x01\x05')

        badKey = keys.Key(None)
        self.assertRaises(RuntimeError, badKey.privateBlob)


    def test_toOpenSSH(self):
        """
        Test that the Key object generates OpenSSH keys correctly.
        """
        key = keys.Key.fromString(keydata.privateRSA_lsh)
        self.assertEqual(key.toString('openssh'), keydata.privateRSA_openssh)
        self.assertEqual(key.toString('openssh', 'encrypted'),
                keydata.privateRSA_openssh_encrypted)
        self.assertEqual(key.public().toString('openssh'),
                keydata.publicRSA_openssh[:-8]) # no comment
        self.assertEqual(key.public().toString('openssh', 'comment'),
                keydata.publicRSA_openssh)
        key = keys.Key.fromString(keydata.privateDSA_lsh)
        self.assertEqual(key.toString('openssh'), keydata.privateDSA_openssh)
        self.assertEqual(key.public().toString('openssh', 'comment'),
                keydata.publicDSA_openssh)
        self.assertEqual(key.public().toString('openssh'),
                keydata.publicDSA_openssh[:-8]) # no comment

    def test_toLSH(self):
        """
        Test that the Key object generates LSH keys correctly.
        """
        key = keys.Key.fromString(keydata.privateRSA_openssh)
        self.assertEqual(key.toString('lsh'), keydata.privateRSA_lsh)
        self.assertEqual(key.public().toString('lsh'),
                keydata.publicRSA_lsh)
        key = keys.Key.fromString(keydata.privateDSA_openssh)
        self.assertEqual(key.toString('lsh'), keydata.privateDSA_lsh)
        self.assertEqual(key.public().toString('lsh'),
                keydata.publicDSA_lsh)

    def test_toAgentv3(self):
        """
        Test that the Key object generates Agent v3 keys correctly.
        """
        key = keys.Key.fromString(keydata.privateRSA_openssh)
        self.assertEqual(key.toString('agentv3'), keydata.privateRSA_agentv3)
        key = keys.Key.fromString(keydata.privateDSA_openssh)
        self.assertEqual(key.toString('agentv3'), keydata.privateDSA_agentv3)

    def test_toStringErrors(self):
        """
        Test that toString raises errors appropriately.
        """
        self.assertRaises(keys.BadKeyError, keys.Key(self.rsaObj).toString,
                'bad_type')

    def test_sign(self):
        """
        Test that the Key object generates correct signatures.
        """
        key = keys.Key.fromString(keydata.privateRSA_openssh)
        self.assertEqual(key.sign(''), self.rsaSignature)
        key = keys.Key.fromString(keydata.privateDSA_openssh)
        self.assertEqual(key.sign(''), self.dsaSignature)


    def test_verify(self):
        """
        Test that the Key object correctly verifies signatures.
        """
        key = keys.Key.fromString(keydata.publicRSA_openssh)
        self.assertTrue(key.verify(self.rsaSignature, ''))
        self.assertFalse(key.verify(self.rsaSignature, 'a'))
        self.assertFalse(key.verify(self.dsaSignature, ''))
        key = keys.Key.fromString(keydata.publicDSA_openssh)
        self.assertTrue(key.verify(self.dsaSignature, ''))
        self.assertFalse(key.verify(self.dsaSignature, 'a'))
        self.assertFalse(key.verify(self.rsaSignature, ''))

    def test_repr(self):
        """
        Test the pretty representation of Key.
        """
        self.assertEqual(repr(keys.Key(self.rsaObj)),
"""<RSA Private Key (0 bits)
attr e:
\t02
attr d:
\t03
attr n:
\t01
attr q:
\t05
attr p:
\t04
attr u:
\t04>""")
