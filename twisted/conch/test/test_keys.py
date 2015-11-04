# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.conch.ssh.keys}.
"""

try:
    import cryptography
except ImportError:
    cryptography = None
    skipCryptography = 'Cannot run without cryptography.'

try:
    import Crypto.Cipher.DES3
except ImportError:
    # we'll have to skip some tests without PyCypto
    Crypto = None
    skipPyCrypto = 'Cannot run without PyCrypto.'
try:
    import pyasn1
except ImportError:
    pyasn1 = None

if cryptography and pyasn1:
    from twisted.conch.ssh import keys, common, sexpy

import os, base64
from hashlib import sha1
from twisted.conch.test import keydata
from twisted.python import randbytes
from twisted.trial import unittest


class HelpersTests(unittest.TestCase):

    if cryptography is None:
        skip = skipCryptography
    if pyasn1 is None:
        skip = "Cannot run without PyASN1"

    def setUp(self):
        self._secureRandom = randbytes.secureRandom
        randbytes.secureRandom = lambda x: '\x55' * x

    def tearDown(self):
        randbytes.secureRandom = self._secureRandom
        self._secureRandom = None

    def _signRSA(self, data):
        key = keys.Key.fromString(keydata.privateRSA_openssh)
        sig = key.sign(data)
        return key._keyObject, sig

    def _signDSA(self, data):
        key = keys.Key.fromString(keydata.privateDSA_openssh)
        sig = key.sign(data)
        return key._keyObject, sig

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
            common.int_to_bytes(v[0], 20) + common.int_to_bytes(v[1], 20)))
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


class KeyTests(unittest.TestCase):

    if cryptography is None:
        skip = skipCryptography
    if pyasn1 is None:
        skip = "Cannot run without PyASN1"

    def setUp(self):
        self.rsaObj = keys.Key._fromRSAComponents(
            n=keydata.RSAData['n'],
            e=keydata.RSAData['e'],
            d=keydata.RSAData['d'],
            p=keydata.RSAData['p'],
            q=keydata.RSAData['q'],
            u=keydata.RSAData['u'],
            )._keyObject
        self.dsaObj = keys.Key._fromDSAComponents(
            y=keydata.DSAData['y'],
            p=keydata.DSAData['p'],
            q=keydata.DSAData['q'],
            g=keydata.DSAData['g'],
            x=keydata.DSAData['x'],
            )._keyObject
        self.rsaSignature = ('\x00\x00\x00\x07ssh-rsa\x00'
            '\x00\x00`N\xac\xb4@qK\xa0(\xc3\xf2h \xd3\xdd\xee6Np\x9d_'
            '\xb0>\xe3\x0c(L\x9d{\txUd|!\xf6m\x9c\xd3\x93\x842\x7fU'
            '\x05\xf4\xf7\xfaD\xda\xce\x81\x8ea\x7f=Y\xed*\xb7\xba\x81'
            '\xf2\xad\xda\xeb(\x97\x03S\x08\x81\xc7\xb1\xb7\xe6\xe3'
            '\xcd*\xd4\xbd\xc0wt\xf7y\xcd\xf0\xb7\x7f\xfb\x1e>\xf9r'
            '\x8c\xba')
        self.dsaSignature = (
            '\x00\x00\x00\x07ssh-dss\x00\x00\x00(?\xc7\xeb\x86;\xd5TFA\xb4\xdf'
            '\x0c\xc4E@4,d\xbc\t\xd9\xae\xdd[\xed-\x82nQ\x8cf\x9b\xe8\xe1jrg'
            '\x84p<'
        )
        self.oldSecureRandom = randbytes.secureRandom
        randbytes.secureRandom = lambda x: '\xff' * x
        self.keyFile = self.mktemp()
        with open(self.keyFile, 'wb') as f:
            f.write(keydata.privateRSA_lsh)

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

    def test_fromNewerOpenSSH(self):
        """
        Newer versions of OpenSSH generate encrypted keys which have a longer
        IV than the older versions.  These newer keys are also loaded.
        """
        key = keys.Key.fromString(keydata.privateRSA_openssh_encrypted_aes,
                                  passphrase='testxp')
        self.assertEqual(key.type(), 'RSA')
        key2 = keys.Key.fromString(
            keydata.privateRSA_openssh_encrypted_aes + '\n',
            passphrase='testxp')
        self.assertEqual(key, key2)


    def test_fromLSHPublicUnsupportedType(self):
        """
        C{BadKeyError} exception is raised when public key has an unknown
        type.
        """
        sexp = sexpy.pack([['public-key', ['bad-key', ['p', '2']]]])

        self.assertRaises(
            keys.BadKeyError,
            keys.Key.fromString, data='{'+base64.encodestring(sexp)+'}',
            )


    def test_fromLSHPrivateUnsupportedType(self):
        """
        C{BadKeyError} exception is raised when private key has an unknown
        type.
        """
        sexp = sexpy.pack([['private-key', ['bad-key', ['p', '2']]]])

        self.assertRaises(
            keys.BadKeyError,
            keys.Key.fromString, sexp,
            )


    def test_fromLSHRSA(self):
        """
        RSA public and private keys can be generated from a LSH strings.
        """
        self._testPublicPrivateFromString(
            keydata.publicRSA_lsh,
            keydata.privateRSA_lsh,
            'RSA',
            keydata.RSAData,
            )


    def test_fromLSHDSA(self):
        """
        DSA public and private key can be generated from LSHs.
        """
        self._testPublicPrivateFromString(
            keydata.publicDSA_lsh,
            keydata.privateDSA_lsh,
            'DSA',
            keydata.DSAData,
            )


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
        # trying to decrypt a key with the wrong passphrase
        self.assertRaises(keys.EncryptedKeyError, keys.Key.fromString,
                keys.Key(self.rsaObj).toString('openssh', 'encrypted'))
        # key with no key data
        self.assertRaises(keys.BadKeyError, keys.Key.fromString,
                '-----BEGIN RSA KEY-----\nwA==\n')
        # key with invalid DEK Info
        self.assertRaises(
            keys.BadKeyError, keys.Key.fromString,
            """-----BEGIN ENCRYPTED RSA KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: weird type

4Ed/a9OgJWHJsne7yOGWeWMzHYKsxuP9w1v0aYcp+puS75wvhHLiUnNwxz0KDi6n
T3YkKLBsoCWS68ApR2J9yeQ6R+EyS+UQDrO9nwqo3DB5BT3Ggt8S1wE7vjNLQD0H
g/SJnlqwsECNhh8aAx+Ag0m3ZKOZiRD5mCkcDQsZET7URSmFytDKOjhFn3u6ZFVB
sXrfpYc6TJtOQlHd/52JB6aAbjt6afSv955Z7enIi+5yEJ5y7oYQTaE5zrFMP7N5
9LbfJFlKXxEddy/DErRLxEjmC+t4svHesoJKc2jjjyNPiOoGGF3kJXea62vsjdNV
gMK5Eged3TBVIk2dv8rtJUvyFeCUtjQ1UJZIebScRR47KrbsIpCmU8I4/uHWm5hW
0mOwvdx1L/mqx/BHqVU9Dw2COhOdLbFxlFI92chkovkmNk4P48ziyVnpm7ME22sE
vfCMsyirdqB1mrL4CSM7FXONv+CgfBfeYVkYW8RfJac9U1L/O+JNn7yee414O/rS
hRYw4UdWnH6Gg6niklVKWNY0ZwUZC8zgm2iqy8YCYuneS37jC+OEKP+/s6HSKuqk
2bzcl3/TcZXNSM815hnFRpz0anuyAsvwPNRyvxG2/DacJHL1f6luV4B0o6W410yf
qXQx01DLo7nuyhJqoH3UGCyyXB+/QUs0mbG2PAEn3f5dVs31JMdbt+PrxURXXjKk
4cexpUcIpqqlfpIRe3RD0sDVbH4OXsGhi2kiTfPZu7mgyFxKopRbn1KwU1qKinfY
EU9O4PoTak/tPT+5jFNhaP+HrURoi/pU8EAUNSktl7xAkHYwkN/9Cm7DeBghgf3n
8+tyCGYDsB5utPD0/Xe9yx0Qhc/kMm4xIyQDyA937dk3mUvLC9vulnAP8I+Izim0
fZ182+D1bWwykoD0997mUHG/AUChWR01V1OLwRyPv2wUtiS8VNG76Y2aqKlgqP1P
V+IvIEqR4ERvSBVFzXNF8Y6j/sVxo8+aZw+d0L1Ns/R55deErGg3B8i/2EqGd3r+
0jps9BqFHHWW87n3VyEB3jWCMj8Vi2EJIfa/7pSaViFIQn8LiBLf+zxG5LTOToK5
xkN42fReDcqi3UNfKNGnv4dsplyTR2hyx65lsj4bRKDGLKOuB1y7iB0AGb0LtcAI
dcsVlcCeUquDXtqKvRnwfIMg+ZunyjqHBhj3qgRgbXbT6zjaSdNnih569aTg0Vup
VykzZ7+n/KVcGLmvX0NesdoI7TKbq4TnEIOynuG5Sf+2GpARO5bjcWKSZeN/Ybgk
gccf8Cqf6XWqiwlWd0B7BR3SymeHIaSymC45wmbgdstrbk7Ppa2Tp9AZku8M2Y7c
8mY9b+onK075/ypiwBm4L4GRNTFLnoNQJXx0OSl4FNRWsn6ztbD+jZhu8Seu10Jw
SEJVJ+gmTKdRLYORJKyqhDet6g7kAxs4EoJ25WsOnX5nNr00rit+NkMPA7xbJT+7
CfI51GQLw7pUPeO2WNt6yZO/YkzZrqvTj5FEwybkUyBv7L0gkqu9wjfDdUw0fVHE
xEm4DxjEoaIp8dW/JOzXQ2EF+WaSOgdYsw3Ac+rnnjnNptCdOEDGP6QBkt+oXj4P
-----END RSA PRIVATE KEY-----""", passphrase='encrypted')
        # key with invalid encryption type
        self.assertRaises(
            keys.BadKeyError, keys.Key.fromString,
            """-----BEGIN ENCRYPTED RSA KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: FOO-123-BAR,01234567

4Ed/a9OgJWHJsne7yOGWeWMzHYKsxuP9w1v0aYcp+puS75wvhHLiUnNwxz0KDi6n
T3YkKLBsoCWS68ApR2J9yeQ6R+EyS+UQDrO9nwqo3DB5BT3Ggt8S1wE7vjNLQD0H
g/SJnlqwsECNhh8aAx+Ag0m3ZKOZiRD5mCkcDQsZET7URSmFytDKOjhFn3u6ZFVB
sXrfpYc6TJtOQlHd/52JB6aAbjt6afSv955Z7enIi+5yEJ5y7oYQTaE5zrFMP7N5
9LbfJFlKXxEddy/DErRLxEjmC+t4svHesoJKc2jjjyNPiOoGGF3kJXea62vsjdNV
gMK5Eged3TBVIk2dv8rtJUvyFeCUtjQ1UJZIebScRR47KrbsIpCmU8I4/uHWm5hW
0mOwvdx1L/mqx/BHqVU9Dw2COhOdLbFxlFI92chkovkmNk4P48ziyVnpm7ME22sE
vfCMsyirdqB1mrL4CSM7FXONv+CgfBfeYVkYW8RfJac9U1L/O+JNn7yee414O/rS
hRYw4UdWnH6Gg6niklVKWNY0ZwUZC8zgm2iqy8YCYuneS37jC+OEKP+/s6HSKuqk
2bzcl3/TcZXNSM815hnFRpz0anuyAsvwPNRyvxG2/DacJHL1f6luV4B0o6W410yf
qXQx01DLo7nuyhJqoH3UGCyyXB+/QUs0mbG2PAEn3f5dVs31JMdbt+PrxURXXjKk
4cexpUcIpqqlfpIRe3RD0sDVbH4OXsGhi2kiTfPZu7mgyFxKopRbn1KwU1qKinfY
EU9O4PoTak/tPT+5jFNhaP+HrURoi/pU8EAUNSktl7xAkHYwkN/9Cm7DeBghgf3n
8+tyCGYDsB5utPD0/Xe9yx0Qhc/kMm4xIyQDyA937dk3mUvLC9vulnAP8I+Izim0
fZ182+D1bWwykoD0997mUHG/AUChWR01V1OLwRyPv2wUtiS8VNG76Y2aqKlgqP1P
V+IvIEqR4ERvSBVFzXNF8Y6j/sVxo8+aZw+d0L1Ns/R55deErGg3B8i/2EqGd3r+
0jps9BqFHHWW87n3VyEB3jWCMj8Vi2EJIfa/7pSaViFIQn8LiBLf+zxG5LTOToK5
xkN42fReDcqi3UNfKNGnv4dsplyTR2hyx65lsj4bRKDGLKOuB1y7iB0AGb0LtcAI
dcsVlcCeUquDXtqKvRnwfIMg+ZunyjqHBhj3qgRgbXbT6zjaSdNnih569aTg0Vup
VykzZ7+n/KVcGLmvX0NesdoI7TKbq4TnEIOynuG5Sf+2GpARO5bjcWKSZeN/Ybgk
gccf8Cqf6XWqiwlWd0B7BR3SymeHIaSymC45wmbgdstrbk7Ppa2Tp9AZku8M2Y7c
8mY9b+onK075/ypiwBm4L4GRNTFLnoNQJXx0OSl4FNRWsn6ztbD+jZhu8Seu10Jw
SEJVJ+gmTKdRLYORJKyqhDet6g7kAxs4EoJ25WsOnX5nNr00rit+NkMPA7xbJT+7
CfI51GQLw7pUPeO2WNt6yZO/YkzZrqvTj5FEwybkUyBv7L0gkqu9wjfDdUw0fVHE
xEm4DxjEoaIp8dW/JOzXQ2EF+WaSOgdYsw3Ac+rnnjnNptCdOEDGP6QBkt+oXj4P
-----END RSA PRIVATE KEY-----""", passphrase='encrypted')
        # key with bad IV (AES)
        self.assertRaises(
            keys.BadKeyError, keys.Key.fromString,
            """-----BEGIN ENCRYPTED RSA KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: AES-128-CBC,01234

4Ed/a9OgJWHJsne7yOGWeWMzHYKsxuP9w1v0aYcp+puS75wvhHLiUnNwxz0KDi6n
T3YkKLBsoCWS68ApR2J9yeQ6R+EyS+UQDrO9nwqo3DB5BT3Ggt8S1wE7vjNLQD0H
g/SJnlqwsECNhh8aAx+Ag0m3ZKOZiRD5mCkcDQsZET7URSmFytDKOjhFn3u6ZFVB
sXrfpYc6TJtOQlHd/52JB6aAbjt6afSv955Z7enIi+5yEJ5y7oYQTaE5zrFMP7N5
9LbfJFlKXxEddy/DErRLxEjmC+t4svHesoJKc2jjjyNPiOoGGF3kJXea62vsjdNV
gMK5Eged3TBVIk2dv8rtJUvyFeCUtjQ1UJZIebScRR47KrbsIpCmU8I4/uHWm5hW
0mOwvdx1L/mqx/BHqVU9Dw2COhOdLbFxlFI92chkovkmNk4P48ziyVnpm7ME22sE
vfCMsyirdqB1mrL4CSM7FXONv+CgfBfeYVkYW8RfJac9U1L/O+JNn7yee414O/rS
hRYw4UdWnH6Gg6niklVKWNY0ZwUZC8zgm2iqy8YCYuneS37jC+OEKP+/s6HSKuqk
2bzcl3/TcZXNSM815hnFRpz0anuyAsvwPNRyvxG2/DacJHL1f6luV4B0o6W410yf
qXQx01DLo7nuyhJqoH3UGCyyXB+/QUs0mbG2PAEn3f5dVs31JMdbt+PrxURXXjKk
4cexpUcIpqqlfpIRe3RD0sDVbH4OXsGhi2kiTfPZu7mgyFxKopRbn1KwU1qKinfY
EU9O4PoTak/tPT+5jFNhaP+HrURoi/pU8EAUNSktl7xAkHYwkN/9Cm7DeBghgf3n
8+tyCGYDsB5utPD0/Xe9yx0Qhc/kMm4xIyQDyA937dk3mUvLC9vulnAP8I+Izim0
fZ182+D1bWwykoD0997mUHG/AUChWR01V1OLwRyPv2wUtiS8VNG76Y2aqKlgqP1P
V+IvIEqR4ERvSBVFzXNF8Y6j/sVxo8+aZw+d0L1Ns/R55deErGg3B8i/2EqGd3r+
0jps9BqFHHWW87n3VyEB3jWCMj8Vi2EJIfa/7pSaViFIQn8LiBLf+zxG5LTOToK5
xkN42fReDcqi3UNfKNGnv4dsplyTR2hyx65lsj4bRKDGLKOuB1y7iB0AGb0LtcAI
dcsVlcCeUquDXtqKvRnwfIMg+ZunyjqHBhj3qgRgbXbT6zjaSdNnih569aTg0Vup
VykzZ7+n/KVcGLmvX0NesdoI7TKbq4TnEIOynuG5Sf+2GpARO5bjcWKSZeN/Ybgk
gccf8Cqf6XWqiwlWd0B7BR3SymeHIaSymC45wmbgdstrbk7Ppa2Tp9AZku8M2Y7c
8mY9b+onK075/ypiwBm4L4GRNTFLnoNQJXx0OSl4FNRWsn6ztbD+jZhu8Seu10Jw
SEJVJ+gmTKdRLYORJKyqhDet6g7kAxs4EoJ25WsOnX5nNr00rit+NkMPA7xbJT+7
CfI51GQLw7pUPeO2WNt6yZO/YkzZrqvTj5FEwybkUyBv7L0gkqu9wjfDdUw0fVHE
xEm4DxjEoaIp8dW/JOzXQ2EF+WaSOgdYsw3Ac+rnnjnNptCdOEDGP6QBkt+oXj4P
-----END RSA PRIVATE KEY-----""", passphrase='encrypted')
        # key with bad IV (DES3)
        self.assertRaises(
            keys.BadKeyError, keys.Key.fromString,
            """-----BEGIN ENCRYPTED RSA KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: DES-EDE3-CBC,01234

4Ed/a9OgJWHJsne7yOGWeWMzHYKsxuP9w1v0aYcp+puS75wvhHLiUnNwxz0KDi6n
T3YkKLBsoCWS68ApR2J9yeQ6R+EyS+UQDrO9nwqo3DB5BT3Ggt8S1wE7vjNLQD0H
g/SJnlqwsECNhh8aAx+Ag0m3ZKOZiRD5mCkcDQsZET7URSmFytDKOjhFn3u6ZFVB
sXrfpYc6TJtOQlHd/52JB6aAbjt6afSv955Z7enIi+5yEJ5y7oYQTaE5zrFMP7N5
9LbfJFlKXxEddy/DErRLxEjmC+t4svHesoJKc2jjjyNPiOoGGF3kJXea62vsjdNV
gMK5Eged3TBVIk2dv8rtJUvyFeCUtjQ1UJZIebScRR47KrbsIpCmU8I4/uHWm5hW
0mOwvdx1L/mqx/BHqVU9Dw2COhOdLbFxlFI92chkovkmNk4P48ziyVnpm7ME22sE
vfCMsyirdqB1mrL4CSM7FXONv+CgfBfeYVkYW8RfJac9U1L/O+JNn7yee414O/rS
hRYw4UdWnH6Gg6niklVKWNY0ZwUZC8zgm2iqy8YCYuneS37jC+OEKP+/s6HSKuqk
2bzcl3/TcZXNSM815hnFRpz0anuyAsvwPNRyvxG2/DacJHL1f6luV4B0o6W410yf
qXQx01DLo7nuyhJqoH3UGCyyXB+/QUs0mbG2PAEn3f5dVs31JMdbt+PrxURXXjKk
4cexpUcIpqqlfpIRe3RD0sDVbH4OXsGhi2kiTfPZu7mgyFxKopRbn1KwU1qKinfY
EU9O4PoTak/tPT+5jFNhaP+HrURoi/pU8EAUNSktl7xAkHYwkN/9Cm7DeBghgf3n
8+tyCGYDsB5utPD0/Xe9yx0Qhc/kMm4xIyQDyA937dk3mUvLC9vulnAP8I+Izim0
fZ182+D1bWwykoD0997mUHG/AUChWR01V1OLwRyPv2wUtiS8VNG76Y2aqKlgqP1P
V+IvIEqR4ERvSBVFzXNF8Y6j/sVxo8+aZw+d0L1Ns/R55deErGg3B8i/2EqGd3r+
0jps9BqFHHWW87n3VyEB3jWCMj8Vi2EJIfa/7pSaViFIQn8LiBLf+zxG5LTOToK5
xkN42fReDcqi3UNfKNGnv4dsplyTR2hyx65lsj4bRKDGLKOuB1y7iB0AGb0LtcAI
dcsVlcCeUquDXtqKvRnwfIMg+ZunyjqHBhj3qgRgbXbT6zjaSdNnih569aTg0Vup
VykzZ7+n/KVcGLmvX0NesdoI7TKbq4TnEIOynuG5Sf+2GpARO5bjcWKSZeN/Ybgk
gccf8Cqf6XWqiwlWd0B7BR3SymeHIaSymC45wmbgdstrbk7Ppa2Tp9AZku8M2Y7c
8mY9b+onK075/ypiwBm4L4GRNTFLnoNQJXx0OSl4FNRWsn6ztbD+jZhu8Seu10Jw
SEJVJ+gmTKdRLYORJKyqhDet6g7kAxs4EoJ25WsOnX5nNr00rit+NkMPA7xbJT+7
CfI51GQLw7pUPeO2WNt6yZO/YkzZrqvTj5FEwybkUyBv7L0gkqu9wjfDdUw0fVHE
xEm4DxjEoaIp8dW/JOzXQ2EF+WaSOgdYsw3Ac+rnnjnNptCdOEDGP6QBkt+oXj4P
-----END RSA PRIVATE KEY-----""", passphrase='encrypted')

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
        obj = keys.Key._fromRSAComponents(n=5L, e=3L)._keyObject
        key = keys.Key(obj)
        self.assertEqual(key._keyObject, obj)

    def test_equal(self):
        """
        Test that Key objects are compared correctly.
        """
        rsa1 = keys.Key(self.rsaObj)
        rsa2 = keys.Key(self.rsaObj)
        rsa3 = keys.Key(keys.Key._fromRSAComponents(n=5L, e=3L)._keyObject)
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
        rsa3 = keys.Key(keys.Key._fromRSAComponents(n=5L, e=3L)._keyObject)
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

    def test_fromBlobUnsupportedType(self):
        """
        A C{BadKeyError} error is raised whey the blob has an unsupported
        key type.
        """
        badBlob = common.NS('ssh-bad')

        self.assertRaises(keys.BadKeyError,
                keys.Key.fromString, badBlob)

    def test_fromBlobRSA(self):
        """
        A public RSA key is correctly generated from a public key blob.
        """
        rsaPublicData = {
            'n': keydata.RSAData['n'],
            'e': keydata.RSAData['e'],
            }
        rsaBlob = (
            common.NS('ssh-rsa') +
            common.MP(rsaPublicData['e']) +
            common.MP(rsaPublicData['n'])
            )

        rsaKey = keys.Key.fromString(rsaBlob)

        self.assertTrue(rsaKey.isPublic())
        self.assertEqual(rsaPublicData, rsaKey.data())


    def test_fromBlobDSA(self):
        """
        A public DSA key is correctly generated from a public key blob.
        """
        dsaPublicData = {
            'p': keydata.DSAData['p'],
            'q': keydata.DSAData['q'],
            'g': keydata.DSAData['g'],
            'y': keydata.DSAData['y'],
            }
        dsaBlob = (
            common.NS('ssh-dss') +
            common.MP(dsaPublicData['p']) +
            common.MP(dsaPublicData['q']) +
            common.MP(dsaPublicData['g']) +
            common.MP(dsaPublicData['y'])
            )

        dsaKey = keys.Key.fromString(dsaBlob)

        self.assertTrue(dsaKey.isPublic())
        self.assertEqual(dsaPublicData, dsaKey.data())

    def test_fromPrivateBlobUnsupportedType(self):
        """
        C{BadKeyError} is raised when loading a private blob with an
        unsupported type.
        """
        badBlob = common.NS('ssh-bad')

        self.assertRaises(
            keys.BadKeyError, keys.Key._fromString_PRIVATE_BLOB, badBlob)


    def test_fromPrivateBlobRSA(self):
        """
        A private RSA key is correctly generated from a private key blob.
        """
        rsaBlob = (
            common.NS('ssh-rsa') +
            common.MP(keydata.RSAData['n']) +
            common.MP(keydata.RSAData['e']) +
            common.MP(keydata.RSAData['d']) +
            common.MP(keydata.RSAData['u']) +
            common.MP(keydata.RSAData['p']) +
            common.MP(keydata.RSAData['q'])
            )

        rsaKey = keys.Key._fromString_PRIVATE_BLOB(rsaBlob)

        self.assertFalse(rsaKey.isPublic())
        self.assertEqual(keydata.RSAData, rsaKey.data())


    def test_fromPrivateBlobDSA(self):
        """
        A private DSA key is correctly generated from a private key blob.
        """
        dsaBlob = (
            common.NS('ssh-dss') +
            common.MP(keydata.DSAData['p']) +
            common.MP(keydata.DSAData['q']) +
            common.MP(keydata.DSAData['g']) +
            common.MP(keydata.DSAData['y']) +
            common.MP(keydata.DSAData['x'])
            )

        dsaKey = keys.Key._fromString_PRIVATE_BLOB(dsaBlob)

        self.assertFalse(dsaKey.isPublic())
        self.assertEqual(keydata.DSAData, dsaKey.data())


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


    def test_privateBlobRSA(self):
        """
        Returns the SSH protocol-level format of the RSA private key.
        """
        self.assertEqual(keys.Key(self.rsaObj).privateBlob(),
                '\x00\x00\x00\x07ssh-rsa\x00\x00\x00\x01\x01'
                '\x00\x00\x00\x01\x02\x00\x00\x00\x01\x03\x00'
                '\x00\x00\x01\x04\x00\x00\x00\x01\x04\x00\x00'
                '\x00\x01\x05')


    def test_privateBlobDSA(self):
        """
        Returns the SSH protocol-level format of the DSA private key.
        """
        self.assertEqual(keys.Key(self.dsaObj).privateBlob(),
                '\x00\x00\x00\x07ssh-dss\x00\x00\x00\x01\x03'
                '\x00\x00\x00\x01\x04\x00\x00\x00\x01\x02\x00'
                '\x00\x00\x01\x01\x00\x00\x00\x01\x05')


    def test_privateBlobNoKeyObject(self):
        """
        Raises L{RuntimeError} if the underlying key object does not exists.
        """
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


    def test_verifyDSANoPrefix(self):
        """
        Some commercial SSH servers send DSA keys as 2 20-byte numbers;
        they are still verified as valid keys.
        """
        key = keys.Key.fromString(keydata.publicDSA_openssh)
        self.assertTrue(key.verify(self.dsaSignature[-40:], ''))


    def test_repr(self):
        """
        Test the pretty representation of Key.
        """
        self.assertEqual(repr(keys.Key(self.rsaObj)),
"""<RSA Private Key (0 bits)
attr d:
\t03
attr e:
\t02
attr n:
\t01
attr p:
\t04
attr q:
\t05
attr u:
\t04>""")



class KeyKeyObjectTests(unittest.TestCase):
    """
    Unit test for the Key.keyObject deprecated ivar which provide the
    compatibility layer to PyCryto during the transition.
    """

    if cryptography is None:
        skip = skipCryptography

    if Crypto is None:
        skip = skipPyCrypto

    def test_keyObjectGetRSAPublic(self):
        """
        It will return the PyCypto RSA instance with the same components as
        a public RSA key.
        """
        key = keys.Key.fromString(keydata.publicRSA_openssh)

        result = key.keyObject

        self.assertIsInstance(result, Crypto.PublicKey.RSA._RSAobj)
        self.assertEqual(keydata.RSAData['e'], result.key.e)
        self.assertEqual(keydata.RSAData['n'], result.key.n)

    def test_keyObjectGetRSAPrivate(self):
        """
        It will return the PyCypto RSA instance with the same components as
        a private RSA key.
        """
        key = keys.Key.fromString(keydata.privateRSA_openssh)

        result = key.keyObject

        self.assertIsInstance(result, Crypto.PublicKey.RSA._RSAobj)
        self.assertEqual(keydata.RSAData['e'], result.key.e)
        self.assertEqual(keydata.RSAData['n'], result.key.n)
        self.assertEqual(keydata.RSAData['d'], result.key.d)
        self.assertEqual(keydata.RSAData['p'], result.key.p)
        self.assertEqual(keydata.RSAData['q'], result.key.q)
        self.assertEqual(keydata.RSAData['u'], result.key.u)


    def test_keyObjectGetDSAPublic(self):
        """
        It will return the PyCypto DSA instance with the same components as
        a public DSA key.
        """
        key = keys.Key.fromString(keydata.publicDSA_openssh)

        result = key.keyObject

        self.assertIsInstance(result, Crypto.PublicKey.DSA._DSAobj)
        self.assertEqual(keydata.DSAData['y'], result.key.y)
        self.assertEqual(keydata.DSAData['g'], result.key.g)
        self.assertEqual(keydata.DSAData['p'], result.key.p)
        self.assertEqual(keydata.DSAData['q'], result.key.q)


    def test_keyObjectGetDSAPrivate(self):
        """
        It will return the PyCypto DSA instance with the same components as
        a private DSA key.
        """
        key = keys.Key.fromString(keydata.privateDSA_openssh)

        result = key.keyObject

        self.assertIsInstance(result, Crypto.PublicKey.DSA._DSAobj)
        self.assertEqual(keydata.DSAData['y'], result.key.y)
        self.assertEqual(keydata.DSAData['g'], result.key.g)
        self.assertEqual(keydata.DSAData['p'], result.key.p)
        self.assertEqual(keydata.DSAData['q'], result.key.q)
        self.assertEqual(keydata.DSAData['x'], result.key.x)


    def test_keyObjectSetRSAPublic(self):
        """
        It will update the key based on a public PyCrpto RSA key.
        """
        key = keys.Key.fromString(keydata.publicDSA_openssh)
        newPyCryptoKey =  Crypto.PublicKey.RSA.construct((
            keydata.RSAData['n'],
            keydata.RSAData['e'],
            ))
        self.assertEqual('DSA', key.type())

        key.keyObject = newPyCryptoKey

        self.assertEqual('RSA', key.type())
        self.assertEqual({
            'n': keydata.RSAData['n'],
            'e': keydata.RSAData['e'],
            },
            key.data())

    def test_keyObjectSetRSAPrivate(self):
        """
        It will update the key based on a private PyCrpto RSA key.
        """
        key = keys.Key.fromString(keydata.publicDSA_openssh)
        newPyCryptoKey =  Crypto.PublicKey.RSA.construct((
            keydata.RSAData['n'],
            keydata.RSAData['e'],
            keydata.RSAData['d'],
            keydata.RSAData['p'],
            keydata.RSAData['q'],
            keydata.RSAData['u'],
            ))
        self.assertEqual('DSA', key.type())

        key.keyObject = newPyCryptoKey

        self.assertEqual('RSA', key.type())
        self.assertEqual({
            'n': keydata.RSAData['n'],
            'e': keydata.RSAData['e'],
            'd': keydata.RSAData['d'],
            'p': keydata.RSAData['p'],
            'q': keydata.RSAData['q'],
            'u': keydata.RSAData['u'],
            },
            key.data())

    def test_keyObjectSetDSAPublic(self):
        """
        It will update the key based on a public PyCrpto DSA key.
        """
        key = keys.Key.fromString(keydata.publicRSA_openssh)
        newPyCryptoKey =  Crypto.PublicKey.DSA.construct((
            keydata.DSAData['y'],
            keydata.DSAData['g'],
            keydata.DSAData['p'],
            keydata.DSAData['q'],
            ))
        self.assertEqual('RSA', key.type())

        key.keyObject = newPyCryptoKey

        self.assertEqual('DSA', key.type())
        self.assertEqual({
            'y': keydata.DSAData['y'],
            'g': keydata.DSAData['g'],
            'p': keydata.DSAData['p'],
            'q': keydata.DSAData['q'],
            },
            key.data())

    def test_keyObjectSetDSAPrivate(self):
        """
        It will update the key based on a private PyCrpto DSA key.
        """
        key = keys.Key.fromString(keydata.publicRSA_openssh)
        newPyCryptoKey =  Crypto.PublicKey.DSA.construct((
            keydata.DSAData['y'],
            keydata.DSAData['g'],
            keydata.DSAData['p'],
            keydata.DSAData['q'],
            keydata.DSAData['x'],
            ))
        self.assertEqual('RSA', key.type())

        key.keyObject = newPyCryptoKey

        self.assertEqual('DSA', key.type())
        self.assertEqual({
            'y': keydata.DSAData['y'],
            'g': keydata.DSAData['g'],
            'p': keydata.DSAData['p'],
            'q': keydata.DSAData['q'],
            'x': keydata.DSAData['x'],
            },
            key.data())
