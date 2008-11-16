# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.conch.ssh.keys}.
"""

try:
    import Crypto.Cipher.DES3
except ImportError:
    Crypto = None
else:
    from twisted.conch.ssh import keys, common, sexpy, asn1

from twisted.conch.test import keydata
from twisted.python import randbytes
from twisted.trial import unittest
import sha, os, base64

class SSHKeysHandlingTestCase(unittest.TestCase):
    """
    test the handling of reading/signing/verifying with RSA and DSA keys
    assumed test keys are in test/
    """

    if Crypto is None:
        skip = "cannot run w/o PyCrypto"

    def setUp(self):
        self.tmpdir = self.mktemp()
        os.mkdir(self.tmpdir)
        self.privateKeyFile = os.path.join(self.tmpdir, 'private')
        self.publicKeyFile = os.path.join(self.tmpdir, 'public')
        file(self.privateKeyFile, 'wb').write(keydata.privateRSA_openssh)
        file(self.publicKeyFile, 'wb').write('first line\n' +
                keydata.publicRSA_openssh)

    def test_readFile(self):
        """
        Test that reading a key from a file works as expected.
        """
        self.assertEquals(self.assertWarns(DeprecationWarning,
            "getPublicKeyString is deprecated since Twisted Conch 0.9.  "
            "Use Key.fromString().", unittest.__file__,
            keys.getPublicKeyString, self.publicKeyFile, 1),
                keys.Key.fromString(keydata.publicRSA_openssh).blob())
        self.assertEquals(self.assertWarns(DeprecationWarning,
            "getPrivateKeyObject is deprecated since Twisted Conch 0.9.  "
            "Use Key.fromString().", unittest.__file__,
            keys.getPrivateKeyObject, self.privateKeyFile),
                keys.Key.fromString(keydata.privateRSA_openssh).keyObject)

    def test_DSA(self):
        """
        Test DSA keys using both OpenSSH and LSH formats.
        """
        self._testKey(keydata.publicDSA_openssh, keydata.privateDSA_openssh,
                keydata.DSAData, 'openssh')
        self._testKey(keydata.publicDSA_lsh, keydata.privateDSA_lsh,
                keydata.DSAData,'lsh')
        obj = self.assertWarns(DeprecationWarning, "getPrivateKeyObject is "
                "deprecated since Twisted Conch 0.9.  Use Key.fromString().",
                unittest.__file__, keys.getPrivateKeyObject,
                data=keydata.privateDSA_agentv3)
        self._testGeneratePrivateKey(obj, keydata.privateDSA_agentv3,
                'agentv3')

    def test_RSA(self):
        """
        Same as test_DSA but for RSA keys.
        """
        self._testKey(keydata.publicRSA_openssh, keydata.privateRSA_openssh,
                keydata.RSAData, 'openssh')
        self._testKey(keydata.publicRSA_lsh, keydata.privateRSA_lsh,
                keydata.RSAData, 'lsh')
        obj = self.assertWarns(DeprecationWarning, "getPrivateKeyObject is "
                "deprecated since Twisted Conch 0.9.  Use Key.fromString().",
                unittest.__file__, keys.getPrivateKeyObject,
                data=keydata.privateRSA_agentv3)
        self._testGeneratePrivateKey(obj, keydata.privateRSA_agentv3,
                'agentv3')


    def test_fingerprint(self):
        """
        L{Key.fingerprint} returns a hex-encoded colon-separated md5 sum of the
        public key.
        """
        self.assertEquals(
            '3d:13:5f:cb:c9:79:8a:93:06:27:65:bc:3d:0b:8f:af',
            keys.Key.fromString(keydata.publicRSA_openssh).fingerprint())


    def _testKey(self, pubStr, privStr, data, keyType):
        """
        Run each of the key tests with the public/private keypairs.

        @param pubStr: The data for a public key in the format defined by
            keyType.
        @param privStr: The data for a private key in the format defined by
            keyType.
        @param data: The numerical values encoded in the key.
        @param keyType: the type of the public and private key data: either
            "openssh" or "lsh".
        """
        pubBlob = self.assertWarns(DeprecationWarning, "getPublicKeyString is "
                "deprecated since Twisted Conch 0.9.  Use Key.fromString().",
                unittest.__file__, keys.getPublicKeyString, data=pubStr)
        pubObj = self.assertWarns(DeprecationWarning, "getPublicKeyObject is "
                "deprecated since Twisted Conch 0.9.  Use Key.fromString().",
                unittest.__file__, keys.getPublicKeyObject, pubBlob)
        privObj = self.assertWarns(DeprecationWarning, "getPrivateKeyObject is "
                "deprecated since Twisted Conch 0.9.  Use Key.fromString().",
                unittest.__file__, keys.getPrivateKeyObject, data=privStr)

        self._testKeySignVerify(privObj, pubObj)
        self._testKeyFromString(privObj, pubObj, data, keyType)
        self._testGeneratePublicKey(privObj, pubObj, pubStr, keyType)
        self._testGeneratePrivateKey(privObj, privStr, keyType)
        self._testGenerateBlob(privObj, pubObj, pubBlob)

    def _testKeySignVerify(self, privObj, pubObj):
        """
        Test that signing and verifying works correctly.
        @param privObj: a private key object.
        @type privObj: C{Crypto.PublicKey.pubkey.pubkey}
        @param pubObj: a public key object.
        @type pubObj: C{Crypto.PublicKey.pubkey.pubkey}
        """

        testData = 'this is the test data'
        sig = self.assertWarns(DeprecationWarning,
                "signData is deprecated since Twisted Conch 0.9.  "
                "Use Key(obj).sign(data).", unittest.__file__, keys.signData,
                privObj, testData)
        self.assertTrue(self.assertWarns(DeprecationWarning,
            "verifySignature is deprecated since Twisted Conch 0.9.  "
            "Use Key(obj).verify(signature, data).", unittest.__file__,
            keys.verifySignature, privObj, sig, testData),
                     'verifying with private %s failed' %
                         keys.objectType(privObj))

        self.assertTrue(self.assertWarns(DeprecationWarning,
            "verifySignature is deprecated since Twisted Conch 0.9.  "
            "Use Key(obj).verify(signature, data).", unittest.__file__,
            keys.verifySignature, pubObj, sig, testData),
                     'verifying with public %s failed' %
                         keys.objectType(pubObj))

        self.failIf(self.assertWarns(DeprecationWarning,
            "verifySignature is deprecated since Twisted Conch 0.9.  "
            "Use Key(obj).verify(signature, data).", unittest.__file__,
            keys.verifySignature,privObj, sig, 'other data'),
                    'verified bad data with %s' %
                        keys.objectType(privObj))

        self.failIf(self.assertWarns(DeprecationWarning,
            "verifySignature is deprecated since Twisted Conch 0.9.  "
            "Use Key(obj).verify(signature, data).", unittest.__file__,
            keys.verifySignature, privObj, 'bad sig', testData),
                    'verified badsign with %s' %
                        keys.objectType(privObj))

    def _testKeyFromString(self, privObj, pubObj, data, keyType):
        """
        Test key object generation from a string.  The public key objects
        were generated in _testKey; just check that they were created
        correctly.
        """
        for k in data.keys():
            self.assertEquals(getattr(privObj, k), data[k])
        for k in pubObj.keydata:
            if hasattr(pubObj, k): # public key objects don't have all the
                                   # attributes
                self.assertEquals(getattr(pubObj, k), data[k])

    def _testGeneratePublicKey(self, privObj, pubObj, pubStr, keyType):
        """
        Test public key string generation from an object.
        """
        self.assertEquals(self.assertWarns(DeprecationWarning,
            "makePublicKeyString is deprecated since Twisted Conch 0.9.  "
            "Use Key(obj).toString().", unittest.__file__,
                keys.makePublicKeyString, pubObj, 'comment',
            keyType), pubStr)
        self.assertEquals(self.assertWarns(DeprecationWarning,
            "makePublicKeyString is deprecated since Twisted Conch 0.9.  "
            "Use Key(obj).toString().", unittest.__file__,
                keys.makePublicKeyString, privObj, 'comment',
            keyType), pubStr)

    def _testGeneratePrivateKey(self, privObj, privStr, keyType):
        """
        Test private key string generation from an object.
        """
        self.assertEquals(self.assertWarns(DeprecationWarning,
            "makePrivateKeyString is deprecated since Twisted Conch 0.9.  "
            "Use Key(obj).toString().", unittest.__file__,
                keys.makePrivateKeyString, privObj, kind=keyType),
                privStr)
        if keyType == 'openssh':
            encData = self.assertWarns(DeprecationWarning,
                    "makePrivateKeyString is deprecated since Twisted Conch "
                    "0.9.  Use Key(obj).toString().", unittest.__file__,
                        keys.makePrivateKeyString, privObj, passphrase='test',
                            kind=keyType)
            self.assertEquals(self.assertWarns(DeprecationWarning,
                "getPrivateKeyObject is deprecated since Twisted Conch 0.9.  "
                "Use Key.fromString().", unittest.__file__,
                keys.getPrivateKeyObject, data = encData, passphrase='test'),
                        privObj)

    def _testGenerateBlob(self, privObj, pubObj, pubBlob):
        """
        Test wire-format blob generation.
        """
        self.assertEquals(self.assertWarns(DeprecationWarning,
            "makePublicKeyBlob is deprecated since Twisted Conch 0.9.  "
            "Use Key(obj).blob().", unittest.__file__,
            keys.makePublicKeyBlob, pubObj), pubBlob)
        self.assertEquals(self.assertWarns(DeprecationWarning,
            "makePublicKeyBlob is deprecated since Twisted Conch 0.9.  "
            "Use Key(obj).blob().", unittest.__file__,
            keys.makePublicKeyBlob, privObj), pubBlob)

    def test_getPublicKeyStringErrors(self):
        """
        Test that getPublicKeyString raises errors in appropriate cases.
        """
        self.assertWarns(DeprecationWarning, "getPublicKeyString is deprecated"
                " since Twisted Conch 0.9.  Use Key.fromString().",
                unittest.__file__, self.assertRaises, keys.BadKeyError,
                keys.getPublicKeyString, self.publicKeyFile, 1,
                data=keydata.publicRSA_openssh)
        self.assertWarns(DeprecationWarning, "getPublicKeyString is deprecated"
                " since Twisted Conch 0.9.  Use Key.fromString().",
                unittest.__file__, self.assertRaises, keys.BadKeyError,
                keys.getPublicKeyString, data = 'invalid key')
        sexp = sexpy.pack([['public-key', ['bad-key', ['p', '2']]]])
        self.assertWarns(DeprecationWarning, "getPublicKeyString is deprecated"
                " since Twisted Conch 0.9.  Use Key.fromString().",
                unittest.__file__, self.assertRaises, keys.BadKeyError,
                keys.getPublicKeyString, data='{'+base64.encodestring(sexp)+'}')

    def test_getPrivateKeyObjectErrors(self):
        """
        Test that getPrivateKeyObject raises errors in appropriate cases.
        """
        self.assertWarns(DeprecationWarning, "getPrivateKeyObject is deprecated"
                " since Twisted Conch 0.9.  Use Key.fromString().",
                unittest.__file__, self.assertRaises, keys.BadKeyError,
                keys.getPrivateKeyObject, self.privateKeyFile,
                keydata.privateRSA_openssh)
        self.assertWarns(DeprecationWarning, "getPrivateKeyObject is deprecated"
                " since Twisted Conch 0.9.  Use Key.fromString().",
                unittest.__file__, self.assertRaises, keys.BadKeyError,
                keys.getPrivateKeyObject, data = 'invalid key')
        sexp = sexpy.pack([['private-key', ['bad-key', ['p', '2']]]])
        self.assertWarns(DeprecationWarning, "getPrivateKeyObject is deprecated"
                " since Twisted Conch 0.9.  Use Key.fromString().",
                unittest.__file__, self.assertRaises, keys.BadKeyError,
                keys.getPrivateKeyObject, data=sexp)
        self.assertWarns(DeprecationWarning, "getPrivateKeyObject is deprecated"
                " since Twisted Conch 0.9.  Use Key.fromString().",
                unittest.__file__, self.assertRaises, keys.BadKeyError,
                keys.getPrivateKeyObject,
                data='\x00\x00\x00\x07ssh-foo'+'\x00\x00\x00\x01\x01'*5)

    def test_makePublicKeyStringErrors(self):
        """
        Test that makePublicKeyString raises errors in appropriate cases.
        """
        self.assertWarns(DeprecationWarning, "makePublicKeyString is deprecated"
                " since Twisted Conch 0.9.  Use Key(obj).toString().",
                unittest.__file__, self.assertRaises, Exception,
                keys.makePublicKeyString, None, kind='bad type')
        self.assertWarns(DeprecationWarning, "makePublicKeyString is deprecated"
                " since Twisted Conch 0.9.  Use Key(obj).toString().",
                unittest.__file__, self.assertRaises, Exception,
                keys.makePublicKeyString, None)
        self.assertWarns(DeprecationWarning, "makePublicKeyString is deprecated"
                " since Twisted Conch 0.9.  Use Key(obj).toString().",
                unittest.__file__, self.assertRaises, Exception,
                keys.makePublicKeyString, None, kind='lsh')

    def test_getPublicKeyObjectErrors(self):
        """
        Test that getPublicKeyObject raises errors in appropriate cases.
        """
        self.assertWarns(DeprecationWarning, "getPublicKeyObject is deprecated"
                " since Twisted Conch 0.9.  Use Key.fromString().",
                unittest.__file__, self.assertRaises, keys.BadKeyError,
                keys.getPublicKeyObject, '\x00\x00\x00\x01A')

    def test_makePrivateKeyStringErrors(self):
        """
        Test that makePrivateKeyString raises errors in appropriate cases.
        """
        self.assertWarns(DeprecationWarning, "makePrivateKeyString is "
                "deprecated since Twisted Conch 0.9.  Use Key(obj).toString().",
                unittest.__file__, self.assertRaises, Exception,
                keys.makePrivateKeyString, None, kind='bad type')
        self.assertWarns(DeprecationWarning, "makePrivateKeyString is "
                "deprecated since Twisted Conch 0.9.  Use Key(obj).toString().",
                unittest.__file__, self.assertRaises, Exception,
                keys.makePrivateKeyString, None)
        self.assertWarns(DeprecationWarning, "makePrivateKeyString is "
                "deprecated since Twisted Conch 0.9.  Use Key(obj).toString().",
                unittest.__file__, self.assertRaises, Exception,
                keys.makePrivateKeyString, None, kind='lsh')

class HelpersTestCase(unittest.TestCase):

    if Crypto is None:
        skip = "cannot run w/o PyCrypto"

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
        self.assertEquals(keys.pkcs1Pad(data, messageSize),
                '\x01\xff\x00ABC')
        hash = sha.new().digest()
        messageSize = 40
        self.assertEquals(keys.pkcs1Digest('', messageSize),
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
        self.assertEquals(sig, common.NS('ssh-rsa') + common.MP(v))
        return key, sig

    def test_signDSA(self):
        """
        Test that DSA keys return appropriate signatures.
        """
        data = 'data'
        key, sig = self._signDSA(data)
        sigData = sha.new(data).digest()
        v = key.sign(sigData, '\x55' * 19)
        self.assertEquals(sig, common.NS('ssh-dss') + common.NS(
            Crypto.Util.number.long_to_bytes(v[0], 20) +
            Crypto.Util.number.long_to_bytes(v[1], 20)))
        return key, sig

    def test_verifyRSA(self):
        """
        Test that RSA signatures are verified appropriately.
        """
        data = 'data'
        key, sig = self._signRSA(data)
        self.assertTrue(self.assertWarns(DeprecationWarning, "verifySignature "
            "is deprecated since Twisted Conch 0.9.  Use "
            "Key(obj).verify(signature, data).", unittest.__file__,
            keys.verifySignature, key, sig, data))

    def test_verifyDSA(self):
        """
        Test that RSA signatures are verified appropriately.
        """
        data = 'data'
        key, sig = self._signDSA(data)
        self.assertTrue(self.assertWarns(DeprecationWarning, "verifySignature "
            "is deprecated since Twisted Conch 0.9.  Use "
            "Key(obj).verify(signature, data).", unittest.__file__,
            keys.verifySignature, key, sig, data))

    def test_objectType(self):
        """
        Test that objectType, returns the correct type for objects.
        """
        self.assertEquals(keys.objectType(keys.Key.fromString(
            keydata.privateRSA_openssh).keyObject), 'ssh-rsa')
        self.assertEquals(keys.objectType(keys.Key.fromString(
            keydata.privateDSA_openssh).keyObject), 'ssh-dss')
        self.assertRaises(keys.BadKeyError, keys.objectType, None)

    def test_asn1PackError(self):
        """
        L{asn1.pack} should raise a C{ValueError} when given a type not
        handled.
        """
        self.assertRaises(ValueError, asn1.pack, [object()])

    def test_printKey(self):
        """
        Test that the printKey function prints correctly.
        """
        obj = keys.Key.fromString(keydata.privateRSA_openssh).keyObject
        self.assertEquals(self.assertWarns(DeprecationWarning, "printKey is "
            "deprecated since Twisted Conch 0.9.  Use repr(Key(obj)).",
            unittest.__file__, keys.printKey, obj),
            """RSA Private Key (767 bits)
attr e:
\t23
attr d:
\t6e:1f:b5:55:97:eb:ed:67:ed:2b:99:6e:ec:c1:ed:
\ta8:4d:52:d6:f3:d6:65:06:04:df:e5:54:9f:cc:89:
\t00:3c:9b:67:87:ec:65:a0:ab:cd:6f:65:90:8a:97:
\t90:4d:c6:21:8f:a8:8d:d8:59:86:43:b5:81:b1:b4:
\td7:5f:2c:22:0a:61:c1:25:8a:47:12:b4:9a:f8:7a:
\t11:1c:4a:a8:8b:75:c4:91:09:3b:be:04:ca:45:d9:
\t57:8a:0d:27:cb:23
attr n:
\t00:af:32:71:f0:e6:0e:9c:99:b3:7f:8b:5f:04:4b:
\tcb:8b:c0:d5:3e:b2:77:fd:cf:64:d8:8f:c0:cf:ae:
\t1f:c6:31:df:f6:29:b2:44:96:e2:c6:d4:21:94:7f:
\t65:7c:d8:d4:23:1f:b8:2e:6a:c9:1f:94:0d:46:c1:
\t69:a2:b7:07:0c:a3:93:c1:34:d8:2e:1e:4a:99:1a:
\t6c:96:46:07:46:2b:dc:25:29:1b:87:f0:be:05:1d:
\tee:b4:34:b9:e7:99:95
attr q:
\t00:dc:9f:6b:d9:98:21:56:11:8d:e9:5f:03:9d:0a:
\td3:93:6e:13:77:41:3c:85:4f:00:70:fd:05:54:ff:
\tbc:3d:09:bf:83:f6:97:7f:64:10:91:04:fe:a2:67:
\t47:54:42:6b
attr p:
\t00:cb:4a:4b:d0:40:47:e8:45:52:f7:c7:af:0c:20:
\t6d:43:0d:b6:39:94:f9:da:a5:e5:03:06:76:83:24:
\teb:88:a1:55:a2:a8:de:12:3b:77:49:92:8a:a9:71:
\td2:02:93:ff
attr u:
\t00:b4:73:97:4b:50:10:a3:17:b3:a8:47:f1:3a:14:
\t76:52:d1:38:2a:cf:12:14:34:c1:a8:54:4c:29:35:
\t80:a0:38:b8:f0:fa:4c:c4:c2:85:ab:db:87:82:ba:
\tdc:eb:db:2a""")

class KeyTestCase(unittest.TestCase):

    if Crypto is None:
        skip = "cannot run w/o PyCrypto"

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
        self.assertEquals(keys.Key._guessStringType(keydata.publicRSA_openssh),
                'public_openssh')
        self.assertEquals(keys.Key._guessStringType(keydata.publicDSA_openssh),
                'public_openssh')
        self.assertEquals(keys.Key._guessStringType(
            keydata.privateRSA_openssh), 'private_openssh')
        self.assertEquals(keys.Key._guessStringType(
            keydata.privateDSA_openssh), 'private_openssh')
        self.assertEquals(keys.Key._guessStringType(keydata.publicRSA_lsh),
                'public_lsh')
        self.assertEquals(keys.Key._guessStringType(keydata.publicDSA_lsh),
                'public_lsh')
        self.assertEquals(keys.Key._guessStringType(keydata.privateRSA_lsh),
                'private_lsh')
        self.assertEquals(keys.Key._guessStringType(keydata.privateDSA_lsh),
                'private_lsh')
        self.assertEquals(keys.Key._guessStringType(
            keydata.privateRSA_agentv3), 'agentv3')
        self.assertEquals(keys.Key._guessStringType(
            keydata.privateDSA_agentv3), 'agentv3')
        self.assertEquals(keys.Key._guessStringType(
            '\x00\x00\x00\x07ssh-rsa\x00\x00\x00\x01\x01'),
            'blob')
        self.assertEquals(keys.Key._guessStringType(
            '\x00\x00\x00\x07ssh-dss\x00\x00\x00\x01\x01'),
            'blob')
        self.assertEquals(keys.Key._guessStringType('not a key'),
                None)

    def _testPublicPrivateFromString(self, public, private, type, data):
        self._testPublicFromString(public, type, data)
        self._testPrivateFromString(private, type, data)

    def _testPublicFromString(self, public, type, data):
        publicKey = keys.Key.fromString(public)
        self.assertTrue(publicKey.isPublic())
        self.assertEquals(publicKey.type(), type)
        for k, v in publicKey.data().items():
            self.assertEquals(data[k], v)

    def _testPrivateFromString(self, private, type, data):
        privateKey = keys.Key.fromString(private)
        self.assertFalse(privateKey.isPublic())
        self.assertEquals(privateKey.type(), type)
        for k, v in data.items():
            self.assertEquals(privateKey.data()[k], v)

    def test_fromOpenSSH(self):
        """
        Test that keys are correctly generated from OpenSSH strings.
        """
        self._testPublicPrivateFromString(keydata.publicRSA_openssh,
                keydata.privateRSA_openssh, 'RSA', keydata.RSAData)
        self.assertEquals(keys.Key.fromString(
            keydata.privateRSA_openssh_encrypted,
            passphrase='encrypted'),
            keys.Key.fromString(keydata.privateRSA_openssh))
        self.assertEquals(keys.Key.fromString(
            keydata.privateRSA_openssh_alternate),
            keys.Key.fromString(keydata.privateRSA_openssh))
        self._testPublicPrivateFromString(keydata.publicDSA_openssh,
                keydata.privateDSA_openssh, 'DSA', keydata.DSAData)

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
        Test that fromString raises errors appropriately.
        """
        self.assertRaises(keys.BadKeyError, keys.Key.fromString, '')
        self.assertRaises(keys.BadKeyError, keys.Key.fromString, '',
                'bad_type')
        self.assertRaises(keys.BadKeyError, keys.Key.fromString,
                keydata.publicRSA_lsh, passphrase = 'unencrypted')
        self.assertRaises(keys.EncryptedKeyError, keys.Key.fromString,
                keys.Key(self.rsaObj).toString('openssh', 'encrypted'))
        self.assertRaises(keys.BadKeyError, keys.Key.fromString,
                '-----BEGIN RSA KEY-----\nwA==\n')

    def test_fromFile(self):
        """
        Test that fromFile works correctly.
        """
        self.assertEquals(keys.Key.fromFile(self.keyFile),
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
        self.assertEquals(key.keyObject, obj)

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
        self.assertEquals(keys.Key(self.rsaObj).type(), 'RSA')
        self.assertEquals(keys.Key(self.rsaObj).sshType(), 'ssh-rsa')
        self.assertEquals(keys.Key(self.dsaObj).type(), 'DSA')
        self.assertEquals(keys.Key(self.dsaObj).sshType(), 'ssh-dss')
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
        self.assertEquals(rsaKey.data(), {'e':2L, 'n':3L})
        self.assertTrue(dsaKey.isPublic())
        self.assertEquals(dsaKey.data(), {'p':2L, 'q':3L, 'g':4L, 'y':5L})
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
        self.assertEquals(keys.Key(self.rsaObj).blob(),
                '\x00\x00\x00\x07ssh-rsa\x00\x00\x00\x01\x02'
                '\x00\x00\x00\x01\x01')
        self.assertEquals(keys.Key(self.dsaObj).blob(),
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
        self.assertEquals(keys.Key(self.rsaObj).privateBlob(),
                '\x00\x00\x00\x07ssh-rsa\x00\x00\x00\x01\x01'
                '\x00\x00\x00\x01\x02\x00\x00\x00\x01\x03\x00'
                '\x00\x00\x01\x04\x00\x00\x00\x01\x04\x00\x00'
                '\x00\x01\x05')
        self.assertEquals(keys.Key(self.dsaObj).privateBlob(),
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
        self.assertEquals(key.toString('openssh'), keydata.privateRSA_openssh)
        self.assertEquals(key.toString('openssh', 'encrypted'),
                keydata.privateRSA_openssh_encrypted)
        self.assertEquals(key.public().toString('openssh'),
                keydata.publicRSA_openssh[:-8]) # no comment
        self.assertEquals(key.public().toString('openssh', 'comment'),
                keydata.publicRSA_openssh)
        key = keys.Key.fromString(keydata.privateDSA_lsh)
        self.assertEquals(key.toString('openssh'), keydata.privateDSA_openssh)
        self.assertEquals(key.public().toString('openssh', 'comment'),
                keydata.publicDSA_openssh)
        self.assertEquals(key.public().toString('openssh'),
                keydata.publicDSA_openssh[:-8]) # no comment

    def test_toLSH(self):
        """
        Test that the Key object generates LSH keys correctly.
        """
        key = keys.Key.fromString(keydata.privateRSA_openssh)
        self.assertEquals(key.toString('lsh'), keydata.privateRSA_lsh)
        self.assertEquals(key.public().toString('lsh'),
                keydata.publicRSA_lsh)
        key = keys.Key.fromString(keydata.privateDSA_openssh)
        self.assertEquals(key.toString('lsh'), keydata.privateDSA_lsh)
        self.assertEquals(key.public().toString('lsh'),
                keydata.publicDSA_lsh)

    def test_toAgentv3(self):
        """
        Test that the Key object generates Agent v3 keys correctly.
        """
        key = keys.Key.fromString(keydata.privateRSA_openssh)
        self.assertEquals(key.toString('agentv3'), keydata.privateRSA_agentv3)
        key = keys.Key.fromString(keydata.privateDSA_openssh)
        self.assertEquals(key.toString('agentv3'), keydata.privateDSA_agentv3)

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
        self.assertEquals(key.sign(''), self.rsaSignature)
        key = keys.Key.fromString(keydata.privateDSA_openssh)
        self.assertEquals(key.sign(''), self.dsaSignature)


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
        self.assertEquals(repr(keys.Key(self.rsaObj)),
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

class WarningsTestCase(unittest.TestCase):
    """
    Test that deprecated functions warn the user of their deprecation.
    """
    if Crypto is None:
        skip = "cannot run w/o PyCrypto"

    def setUp(self):
        self.keyObject = keys.Key.fromString(keydata.privateRSA_lsh).keyObject

    def test_getPublicKeyString(self):
        """
        Test that getPublicKeyString warns with a DeprecationWarning.
        """
        self.assertWarns(DeprecationWarning,
            "getPublicKeyString is deprecated since Twisted Conch 0.9."
            "  Use Key.fromString().",
            unittest.__file__, keys.getPublicKeyString,
            data=keydata.publicRSA_openssh)

    def test_makePublicKeyString(self):
        """
        Test that makePublicKeyString warns with a DeprecationWarning.
        """
        self.assertWarns(DeprecationWarning,
            "makePublicKeyString is deprecated since Twisted Conch 0.9."
            "  Use Key(obj).toString().", unittest.__file__,
            keys.makePublicKeyString, self.keyObject)

    def test_getPublicKeyObject(self):
        """
        Test that getPublicKeyObject warns with a DeprecationWarning.
        """
        self.assertWarns(DeprecationWarning,
            "getPublicKeyObject is deprecated since Twisted Conch 0.9."
            "  Use Key.fromString().", unittest.__file__,
            keys.getPublicKeyObject, keydata.publicRSA_lsh)

    def test_getPrivateKeyObject(self):
        """
        Test that getPrivateKeyObject warns with a DeprecationWarning.
        """
        self.assertWarns(DeprecationWarning,
            "getPrivateKeyObject is deprecated since Twisted Conch 0.9."
            "  Use Key.fromString().", unittest.__file__,
            keys.getPrivateKeyObject, data=keydata.privateRSA_lsh)

    def test_makePrivateKeyString(self):
        """
        Test that makePrivateKeyString warns with a DeprecationWarning.
        """
        self.assertWarns(DeprecationWarning,
            "makePrivateKeyString is deprecated since Twisted Conch 0.9."
            "  Use Key(obj).toString().", unittest.__file__,
            keys.makePrivateKeyString, self.keyObject)

    def test_makePublicKeyBlob(self):
        """
        Test that makePublicKeyBlob warns with a DeprecationWarning.
        """
        self.assertWarns(DeprecationWarning,
            "makePublicKeyBlob is deprecated since Twisted Conch 0.9."
            "  Use Key(obj).blob().", unittest.__file__,
            keys.makePublicKeyBlob, self.keyObject)

    def test_signData(self):
        """
        Test that signData warns with a DeprecationWarning.
        """
        self.assertWarns(DeprecationWarning,
            "signData is deprecated since Twisted Conch 0.9."
            "  Use Key(obj).sign(data).", unittest.__file__,
            keys.signData, self.keyObject, '')

    def test_verifySignature(self):
        """
        Test that signData warns with a DeprecationWarning.
        """
        self.assertWarns(DeprecationWarning,
            "verifySignature is deprecated since Twisted Conch 0.9."
            "  Use Key(obj).verify(signature, data).", unittest.__file__,
            keys.verifySignature, self.keyObject, '\x00\x00\x00\x00', '')

    def test_printKey(self):
        """
        Test that signData warns with a DeprecationWarning.
        """
        self.assertWarns(DeprecationWarning,
            "printKey is deprecated since Twisted Conch 0.9."
            "  Use repr(Key(obj)).", unittest.__file__,
            keys.printKey, self.keyObject)

