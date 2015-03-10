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
from hashlib import sha1
from twisted.conch.test import keydata
from twisted.python import randbytes
from twisted.trial import unittest


class HelpersTests(unittest.TestCase):

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


class KeyTests(unittest.TestCase):

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
