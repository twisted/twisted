# -*- test-case-name: twisted.conch.test.test_keys -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Handling of RSA and DSA keys.
"""

import base64
import itertools
from hashlib import md5, sha1

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.interfaces import (
    DSAPrivateKey, DSAPublicKey, RSAPrivateKey, RSAPublicKey
)
from cryptography.hazmat.primitives.asymmetric import dsa, rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from pyasn1.error import PyAsn1Error
from pyasn1.type import univ
from pyasn1.codec.ber import decoder as berDecoder
from pyasn1.codec.ber import encoder as berEncoder

from twisted.conch.ssh import common, sexpy
from twisted.python import randbytes



class BadKeyError(Exception):
    """
    Raised when a key isn't what we expected from it.

    XXX: we really need to check for bad keys
    """



class EncryptedKeyError(Exception):
    """
    Raised when an encrypted key is presented to fromString/fromFile without
    a password.
    """



class Key(object):
    """
    An object representing a key.  A key can be either a public or
    private key.  A public key can verify a signature; a private key can
    create or verify a signature.  To generate a string that can be stored
    on disk, use the toString method.  If you have a private key, but want
    the string representation of the public key, use Key.public().toString().

    @ivar keyObject: DEPRECATED. The C{Crypto.PublicKey} object
        that operations are performed with.
    """

    def fromFile(Class, filename, type=None, passphrase=None):
        """
        Return a Key object corresponding to the data in filename.  type
        and passphrase function as they do in fromString.
        """
        return Class.fromString(file(filename, 'rb').read(), type, passphrase)
    fromFile = classmethod(fromFile)


    def fromString(Class, data, type=None, passphrase=None):
        """
        Return a Key object corresponding to the string data.
        type is optionally the type of string, matching a _fromString_*
        method.  Otherwise, the _guessStringType() classmethod will be used
        to guess a type.  If the key is encrypted, passphrase is used as
        the decryption key.

        @type data: C{str}
        @type type: C{None}/C{str}
        @type passphrase: C{None}/C{str}
        @rtype: C{Key}
        """
        if type is None:
            type = Class._guessStringType(data)
        if type is None:
            raise BadKeyError('cannot guess the type of %r' % data)
        method = getattr(Class, '_fromString_%s' % type.upper(), None)
        if method is None:
            raise BadKeyError('no _fromString method for %s' % type)
        if method.func_code.co_argcount == 2:  # no passphrase
            if passphrase:
                raise BadKeyError('key not encrypted')
            return method(data)
        else:
            return method(data, passphrase)
    fromString = classmethod(fromString)


    @classmethod
    def _fromString_BLOB(cls, blob):
        """
        Return a public key object corresponding to this public key blob.
        The format of a RSA public key blob is::
            string 'ssh-rsa'
            integer e
            integer n

        The format of a DSA public key blob is::
            string 'ssh-dss'
            integer p
            integer q
            integer g
            integer y

        @type blob: C{str}
        @return: A new key.
        @rtype: L{twisted.conch.ssh.keys.Key}
        @raises BadKeyError: if the key type (the first string) is unknown.
        """
        keyType, rest = common.getNS(blob)
        if keyType == 'ssh-rsa':
            e, n, rest = common.getMP(rest, 2)
            return cls(rsa.RSAPublicNumbers(e, n).public_key(default_backend()))
        elif keyType == 'ssh-dss':
            p, q, g, y, rest = common.getMP(rest, 4)
            return cls(
                dsa.DSAPublicNumbers(
                    y=y,
                    parameter_numbers=dsa.DSAParameterNumbers(
                        p=p,
                        q=q,
                        g=g
                    )
                ).public_key(default_backend())
            )
        else:
            raise BadKeyError('unknown blob type: %s' % keyType)


    @classmethod
    def _fromString_PRIVATE_BLOB(cls, blob):
        """
        Return a private key object corresponding to this private key blob.
        The blob formats are as follows:

        RSA keys::
            string 'ssh-rsa'
            integer n
            integer e
            integer d
            integer u
            integer p
            integer q

        DSA keys::
            string 'ssh-dss'
            integer p
            integer q
            integer g
            integer y
            integer x

        @type blob: C{str}
        @return: A new key.
        @rtype: L{twisted.conch.ssh.keys.Key}
        @raises BadKeyError: if the key type (the first string) is unknown.
        """
        keyType, rest = common.getNS(blob)

        if keyType == 'ssh-rsa':
            n, e, d, u, p, q, rest = common.getMP(rest, 6)
            return cls._fromRSAComponents(n=n, e=e, d=d, p=p, q=q, u=u)
        elif keyType == 'ssh-dss':
            p, q, g, y, x, rest = common.getMP(rest, 5)
            return cls._fromDSAComponents(y=y, g=g, p=p, q=q, x=x)
        else:
            raise BadKeyError('unknown blob type: %s' % keyType)


    @classmethod
    def _fromString_PUBLIC_OPENSSH(cls, data):
        """
        Return a public key object corresponding to this OpenSSH public key
        string.  The format of an OpenSSH public key string is::
            <key type> <base64-encoded public key blob>

        @type data: C{str}
        @return: A new key.
        @rtype: L{twisted.conch.ssh.keys.Key}
        @raises BadKeyError: if the blob type is unknown.
        """
        blob = base64.decodestring(data.split()[1])
        return cls._fromString_BLOB(blob)


    @classmethod
    def _fromString_PRIVATE_OPENSSH(cls, data, passphrase):
        """
        Return a private key object corresponding to this OpenSSH private key
        string.  If the key is encrypted, passphrase MUST be provided.
        Providing a passphrase for an unencrypted key is an error.

        The format of an OpenSSH private key string is::
            -----BEGIN <key type> PRIVATE KEY-----
            [Proc-Type: 4,ENCRYPTED
            DEK-Info: DES-EDE3-CBC,<initialization value>]
            <base64-encoded ASN.1 structure>
            ------END <key type> PRIVATE KEY------

        The ASN.1 structure of a RSA key is::
            (0, n, e, d, p, q)

        The ASN.1 structure of a DSA key is::
            (0, p, q, g, y, x)

        @type data: C{str}
        @type passphrase: C{str}
        @return: A new key.
        @rtype: L{twisted.conch.ssh.keys.Key}
        @raises BadKeyError: if
            * a passphrase is provided for an unencrypted key
            * the ASN.1 encoding is incorrect
        @raises EncryptedKeyError: if
            * a passphrase is not provided for an encrypted key
        """
        lines = data.strip().split('\n')
        kind = lines[0][11:14]
        if lines[1].startswith('Proc-Type: 4,ENCRYPTED'):  # encrypted key
            if not passphrase:
                raise EncryptedKeyError('Passphrase must be provided '
                                        'for an encrypted key')

            # Determine cipher and initialization vector
            try:
                _, cipher_iv_info = lines[2].split(' ', 1)
                cipher, ivdata = cipher_iv_info.rstrip().split(',', 1)
            except ValueError:
                raise BadKeyError('invalid DEK-info %r' % lines[2])

            if cipher == 'AES-128-CBC':
                AlgorithmClass = algorithms.AES
                keySize = 16
                if len(ivdata) != 32:
                    raise BadKeyError('AES encrypted key with a bad IV')
            elif cipher == 'DES-EDE3-CBC':
                AlgorithmClass = algorithms.TripleDES
                keySize = 24
                if len(ivdata) != 16:
                    raise BadKeyError('DES encrypted key with a bad IV')
            else:
                raise BadKeyError('unknown encryption type %r' % cipher)

            # extract keyData for decoding
            iv = ''.join([chr(int(ivdata[i:i + 2], 16))
                          for i in range(0, len(ivdata), 2)])
            ba = md5(passphrase + iv[:8]).digest()
            bb = md5(ba + passphrase + iv[:8]).digest()
            decKey = (ba + bb)[:keySize]
            b64Data = base64.decodestring(''.join(lines[3:-1]))

            decryptor = Cipher(
                AlgorithmClass(decKey),
                modes.CBC(iv),
                backend=default_backend()
            ).decryptor()
            keyData = decryptor.update(b64Data) + decryptor.finalize()

            removeLen = ord(keyData[-1])
            keyData = keyData[:-removeLen]
        else:
            b64Data = ''.join(lines[1:-1])
            keyData = base64.decodestring(b64Data)

        try:
            decodedKey = berDecoder.decode(keyData)[0]
        except PyAsn1Error as e:
            raise BadKeyError('Failed to decode key (Bad Passphrase?): %s' % e)

        if kind == 'RSA':
            if len(decodedKey) == 2:  # alternate RSA key
                decodedKey = decodedKey[0]
            if len(decodedKey) < 6:
                raise BadKeyError('RSA key failed to decode properly')

            n, e, d, p, q, dmp1, dmq1, iqmp = [
                long(value) for value in decodedKey[1:9]
            ]
            if p > q:  # make p smaller than q
                p, q = q, p
            return cls(
                rsa.RSAPrivateNumbers(
                    p=p,
                    q=q,
                    d=d,
                    dmp1=dmp1,
                    dmq1=dmq1,
                    iqmp=iqmp,
                    public_numbers=rsa.RSAPublicNumbers(e=e, n=n),
                ).private_key(default_backend())
            )
        elif kind == 'DSA':
            p, q, g, y, x = [long(value) for value in decodedKey[1: 6]]
            if len(decodedKey) < 6:
                raise BadKeyError('DSA key failed to decode properly')
            return cls(
                dsa.DSAPrivateNumbers(
                    x=x,
                    public_numbers=dsa.DSAPublicNumbers(
                        y=y,
                        parameter_numbers=dsa.DSAParameterNumbers(
                            p=p,
                            q=q,
                            g=g
                        )
                    )
                ).private_key(backend=default_backend())
            )


    @classmethod
    def _fromString_PUBLIC_LSH(cls, data):
        """
        Return a public key corresponding to this LSH public key string.
        The LSH public key string format is::
            <s-expression: ('public-key', (<key type>, (<name, <value>)+))>

        The names for a RSA (key type 'rsa-pkcs1-sha1') key are: n, e.
        The names for a DSA (key type 'dsa') key are: y, g, p, q.

        @type data: C{str}
        @return: A new key.
        @rtype: L{twisted.conch.ssh.keys.Key}
        @raises BadKeyError: if the key type is unknown
        """
        sexp = sexpy.parse(base64.decodestring(data[1:-1]))
        assert sexp[0] == 'public-key'
        kd = {}
        for name, data in sexp[1][1:]:
            kd[name] = common.getMP(common.NS(data))[0]
        if sexp[1][0] == 'dsa':
            return cls._fromDSAComponents(
                y=kd['y'], g=kd['g'], p=kd['p'], q=kd['q'])
        elif sexp[1][0] == 'rsa-pkcs1-sha1':
            return cls._fromRSAComponents(n=kd['n'], e=kd['e'])
        else:
            raise BadKeyError('unknown lsh key type %s' % sexp[1][0])


    @classmethod
    def _fromString_PRIVATE_LSH(cls, data):
        """
        Return a private key corresponding to this LSH private key string.
        The LSH private key string format is::
            <s-expression: ('private-key', (<key type>, (<name>, <value>)+))>

        The names for a RSA (key type 'rsa-pkcs1-sha1') key are: n, e, d, p, q.
        The names for a DSA (key type 'dsa') key are: y, g, p, q, x.

        @type data: C{str}
        @return: A new key.
        @rtype: L{twisted.conch.ssh.keys.Key}
        @raises BadKeyError: if the key type is unknown
        """
        sexp = sexpy.parse(data)
        assert sexp[0] == 'private-key'
        kd = {}
        for name, data in sexp[1][1:]:
            kd[name] = common.getMP(common.NS(data))[0]
        if sexp[1][0] == 'dsa':
            assert len(kd) == 5, len(kd)
            return cls._fromDSAComponents(
                y=kd['y'], g=kd['g'], p=kd['p'], q=kd['q'], x=kd['x'])
        elif sexp[1][0] == 'rsa-pkcs1':
            assert len(kd) == 8, len(kd)
            if kd['p'] > kd['q']:  # make p smaller than q
                kd['p'], kd['q'] = kd['q'], kd['p']
            return cls._fromRSAComponents(
                n=kd['n'], e=kd['e'], d=kd['d'], p=kd['p'], q=kd['q'])
        else:
            raise BadKeyError('unknown lsh key type %s' % sexp[1][0])


    @classmethod
    def _fromString_AGENTV3(cls, data):
        """
        Return a private key object corresponsing to the Secure Shell Key
        Agent v3 format.

        The SSH Key Agent v3 format for a RSA key is::
            string 'ssh-rsa'
            integer e
            integer d
            integer n
            integer u
            integer p
            integer q

        The SSH Key Agent v3 format for a DSA key is::
            string 'ssh-dss'
            integer p
            integer q
            integer g
            integer y
            integer x

        @type data: C{str}
        @return: A new key.
        @rtype: L{twisted.conch.ssh.keys.Key}
        @raises BadKeyError: if the key type (the first string) is unknown
        """
        keyType, data = common.getNS(data)
        if keyType == 'ssh-dss':
            p, data = common.getMP(data)
            q, data = common.getMP(data)
            g, data = common.getMP(data)
            y, data = common.getMP(data)
            x, data = common.getMP(data)
            return cls._fromDSAComponents(y=y, g=g, p=p, q=q, x=x)
        elif keyType == 'ssh-rsa':
            e, data = common.getMP(data)
            d, data = common.getMP(data)
            n, data = common.getMP(data)
            u, data = common.getMP(data)
            p, data = common.getMP(data)
            q, data = common.getMP(data)
            return cls._fromRSAComponents(n=n, e=e, d=d, p=p, q=q, u=u)
        else:
            raise BadKeyError("unknown key type %s" % keyType)


    def _guessStringType(Class, data):
        """
        Guess the type of key in data.  The types map to _fromString_*
        methods.
        """
        if data.startswith('ssh-'):
            return 'public_openssh'
        elif data.startswith('-----BEGIN'):
            return 'private_openssh'
        elif data.startswith('{'):
            return 'public_lsh'
        elif data.startswith('('):
            return 'private_lsh'
        elif data.startswith('\x00\x00\x00\x07ssh-'):
            ignored, rest = common.getNS(data)
            count = 0
            while rest:
                count += 1
                ignored, rest = common.getMP(rest)
            if count > 4:
                return 'agentv3'
            else:
                return 'blob'
    _guessStringType = classmethod(_guessStringType)


    @classmethod
    def _fromRSAComponents(cls, n, e, d=None, p=None, q=None, u=None):
        """
        """
        publicNumbers = rsa.RSAPublicNumbers(e=e, n=n)
        if d is None:
            # We have public components.
            keyObject = publicNumbers.public_key(default_backend())
        else:
            if u is None:
                u = rsa.rsa_crt_iqmp(p, q)
            privateNumbers = rsa.RSAPrivateNumbers(
                p=p,
                q=q,
                d=d,
                dmp1=rsa.rsa_crt_dmp1(d, p),
                dmq1=rsa.rsa_crt_dmq1(d, q),
                iqmp=u,
                public_numbers=publicNumbers,
                )
            keyObject = privateNumbers.private_key(default_backend())

        return cls(keyObject)


    @classmethod
    def _fromDSAComponents(cls, y, p, q, g, x=None):
        """
        """
        publicNumbers = dsa.DSAPublicNumbers(
            y=y, parameter_numbers=dsa.DSAParameterNumbers(p=p, q=q, g=g))
        if x is None:
            # We have public components.
            keyObject = publicNumbers.public_key(default_backend())
        else:
            privateNumbers = dsa.DSAPrivateNumbers(
                x=x, public_numbers=publicNumbers)
            keyObject = privateNumbers.private_key(default_backend())

        return cls(keyObject)


    def __init__(self, keyObject):
        """
        Initialize with a private or public
        C{cryptography.hazmat.primitives.asymmetric} key.

        @param keyObject: Low level key.
        @type keyObject: C{cryptography.hazmat.primitives.asymmetric} key.
        """
        self._keyObject = keyObject


    def __eq__(self, other):
        """
        Return True if other represents an object with the same key.
        """
        if type(self) == type(other):
            return self.type() == other.type() and self.data() == other.data()
        else:
            return NotImplemented


    def __ne__(self, other):
        """
        Return True if other represents anything other than this key.
        """
        result = self.__eq__(other)
        if result == NotImplemented:
            return result
        return not result


    def __repr__(self):
        """
        Return a pretty representation of this object.
        """
        lines = [
            '<%s %s (%s bits)' % (
                self.type(),
                self.isPublic() and 'Public Key' or 'Private Key',
                self._keyObject.key_size)]
        for k, v in sorted(self.data().items()):
            lines.append('attr %s:' % k)
            by = common.MP(v)[4:]
            while by:
                m = by[:15]
                by = by[15:]
                o = ''
                for c in m:
                    o = o + '%02x:' % ord(c)
                if len(m) < 15:
                    o = o[:-1]
                lines.append('\t' + o)
        lines[-1] = lines[-1] + '>'
        return '\n'.join(lines)


    @property
    def keyObject(self):
        """
        An C{Crypto.PublicKey} object similar to this key.

        This instance member is deprecated.

        It provides the compatibility layer for PyCryto during the transition.
        """
        # Lazy import to have PyCrypto as a soft dependency.
        from Crypto.PublicKey import DSA, RSA

        keyObject = None
        keyType = self.type()
        keyData = self.data()
        isPublic = self.isPublic()

        if keyType == 'RSA':
            if isPublic:
                keyObject = RSA.construct((
                    keyData['n'],
                    long(keyData['e']),
                    ))
            else:
                keyObject = RSA.construct((
                    keyData['n'],
                    long(keyData['e']),
                    keyData['d'],
                    keyData['p'],
                    keyData['q'],
                    keyData['u'],
                    ))
        elif keyType == 'DSA':
            if isPublic:
                keyObject = DSA.construct((
                    keyData['y'],
                    keyData['g'],
                    keyData['p'],
                    keyData['q'],
                    ))
            else:
                keyObject = DSA.construct((
                    keyData['y'],
                    keyData['g'],
                    keyData['p'],
                    keyData['q'],
                    keyData['x'],
                    ))
        else:
           raise BadKeyError('Unsupported key type.')

        return keyObject


    @keyObject.setter
    def keyObject(self, value):
        # Lazy import to have PyCrypto as a soft dependency.
        from Crypto.PublicKey import DSA, RSA

        if isinstance(value, RSA._RSAobj):
            rawKey = value.key
            if rawKey.has_private():
                newKey = self._fromRSAComponents(
                    e=rawKey.e,
                    n=rawKey.n,
                    p=rawKey.p,
                    q=rawKey.q,
                    d=rawKey.d,
                    u=rawKey.u,
                    )
            else:
                newKey = self._fromRSAComponents(e=rawKey.e, n=rawKey.n)

        elif isinstance(value, DSA._DSAobj):
            rawKey = value.key
            if rawKey.has_private():
                newKey = self._fromDSAComponents(
                    y=rawKey.y,
                    p=rawKey.p,
                    q=rawKey.q,
                    g=rawKey.g,
                    x=rawKey.x,
                    )
            else:
                newKey = self._fromDSAComponents(
                    y=rawKey.y,
                    p=rawKey.p,
                    q=rawKey.q,
                    g=rawKey.g,
                    )

        else:
            raise BadKeyError('PyCrytpo key type not supported.')


        self._keyObject = newKey._keyObject


    def isPublic(self):
        """
        Returns True if this Key is a public key.
        """
        return isinstance(self._keyObject, (RSAPublicKey, DSAPublicKey))


    def public(self):
        """
        Returns a version of this key containing only the public key data.
        If this is a public key, this may or may not be the same object
        as self.
        """
        return Key(self._keyObject.public_key())


    def fingerprint(self):
        """
        Get the user presentation of the fingerprint of this L{Key}.  As
        described by U{RFC 4716 section
        4<http://tools.ietf.org/html/rfc4716#section-4>}::

            The fingerprint of a public key consists of the output of the MD5
            message-digest algorithm [RFC1321].  The input to the algorithm is
            the public key data as specified by [RFC4253].  (...)  The output
            of the (MD5) algorithm is presented to the user as a sequence of 16
            octets printed as hexadecimal with lowercase letters and separated
            by colons.

        @since: 8.2

        @return: the user presentation of this L{Key}'s fingerprint, as a
        string.

        @rtype: L{str}
        """
        return ':'.join([x.encode('hex') for x in md5(self.blob()).digest()])


    def type(self):
        """
        Return the type of the object we wrap.  Currently this can only be
        'RSA' or 'DSA'.
        """
        if isinstance(self._keyObject, (RSAPublicKey, RSAPrivateKey)):
            return 'RSA'
        elif isinstance(self._keyObject, (DSAPublicKey, DSAPrivateKey)):
            return 'DSA'
        else:
            raise RuntimeError('unknown type of object: %r' % self._keyObject)


    def sshType(self):
        """
        Return the type of the object we wrap as defined in the ssh protocol.
        Currently this can only be 'ssh-rsa' or 'ssh-dss'.
        """
        return {'RSA': 'ssh-rsa', 'DSA': 'ssh-dss'}[self.type()]

    def size(self):
        """
        Return the size of the object we wrap.

        @return: The size of the key.
        @rtype: C{int}
        """
        if self._keyObject is None:
            return 0
        return self._keyObject.key_size


    def data(self):
        """
        Return the values of the public key as a dictionary.

        @rtype: C{dict}
        """
        if isinstance(self._keyObject, RSAPublicKey):
            numbers = self._keyObject.public_numbers()
            return {
                "n": numbers.n,
                "e": numbers.e,
            }
        elif isinstance(self._keyObject, RSAPrivateKey):
            numbers = self._keyObject.private_numbers()
            return {
                "n": numbers.public_numbers.n,
                "e": numbers.public_numbers.e,
                "d": numbers.d,
                "p": numbers.p,
                "q": numbers.q,
                "u": numbers.iqmp,
            }
        elif isinstance(self._keyObject, DSAPublicKey):
            numbers = self._keyObject.public_numbers()
            return {
                "y": numbers.y,
                "g": numbers.parameter_numbers.g,
                "p": numbers.parameter_numbers.p,
                "q": numbers.parameter_numbers.q,
            }
        elif isinstance(self._keyObject, DSAPrivateKey):
            numbers = self._keyObject.private_numbers()
            return {
                "x": numbers.x,
                "y": numbers.public_numbers.y,
                "g": numbers.public_numbers.parameter_numbers.g,
                "p": numbers.public_numbers.parameter_numbers.p,
                "q": numbers.public_numbers.parameter_numbers.q,
            }
        else:
            raise RuntimeError("Unexpected key type: %s" % self._keyObject)


    def blob(self):
        """
        Return the public key blob for this key.  The blob is the
        over-the-wire format for public keys:

        RSA keys::
            string  'ssh-rsa'
            integer e
            integer n

        DSA keys::
            string  'ssh-dss'
            integer p
            integer q
            integer g
            integer y

        @rtype: C{str}
        """
        type = self.type()
        data = self.data()
        if type == 'RSA':
            return (common.NS('ssh-rsa') + common.MP(data['e']) +
                    common.MP(data['n']))
        elif type == 'DSA':
            return (common.NS('ssh-dss') + common.MP(data['p']) +
                    common.MP(data['q']) + common.MP(data['g']) +
                    common.MP(data['y']))


    def privateBlob(self):
        """
        Return the private key blob for this key.  The blob is the
        over-the-wire format for private keys:

        RSA keys::
            string 'ssh-rsa'
            integer n
            integer e
            integer d
            integer u
            integer p
            integer q

        DSA keys::
            string 'ssh-dss'
            integer p
            integer q
            integer g
            integer y
            integer x
        """
        type = self.type()
        data = self.data()
        if type == 'RSA':
            return (common.NS('ssh-rsa') + common.MP(data['n']) +
                    common.MP(data['e']) + common.MP(data['d']) +
                    common.MP(data['u']) + common.MP(data['p']) +
                    common.MP(data['q']))
        elif type == 'DSA':
            return (common.NS('ssh-dss') + common.MP(data['p']) +
                    common.MP(data['q']) + common.MP(data['g']) +
                    common.MP(data['y']) + common.MP(data['x']))


    def toString(self, type, extra=None):
        """
        Create a string representation of this key.  If the key is a private
        key and you want the represenation of its public key, use
        C{key.public().toString()}.  type maps to a _toString_* method.

        @param type: The type of string to emit.  Currently supported values
            are C{'OPENSSH'}, C{'LSH'}, and C{'AGENTV3'}.
        @type type: L{str}

        @param extra: Any extra data supported by the selected format which
            is not part of the key itself.  For public OpenSSH keys, this is
            a comment.  For private OpenSSH keys, this is a passphrase to
            encrypt with.
        @type extra: L{str} or L{NoneType}

        @rtype: L{str}
        """
        method = getattr(self, '_toString_%s' % type.upper(), None)
        if method is None:
            raise BadKeyError('unknown type: %s' % type)
        if method.func_code.co_argcount == 2:
            return method(extra)
        else:
            return method()


    def _toString_OPENSSH(self, extra):
        """
        Return a public or private OpenSSH string.  See
        _fromString_PUBLIC_OPENSSH and _fromString_PRIVATE_OPENSSH for the
        string formats.  If extra is present, it represents a comment for a
        public key, or a passphrase for a private key.

        @param extra: Comment for a public key or passphrase for a
            private key
        @type extra: C{str}

        @rtype: C{str}
        """
        data = self.data()
        if self.isPublic():
            b64Data = base64.encodestring(self.blob()).replace('\n', '')
            if not extra:
                extra = ''
            return ('%s %s %s' % (self.sshType(), b64Data, extra)).strip()
        else:
            lines = ['-----BEGIN %s PRIVATE KEY-----' % self.type()]
            if self.type() == 'RSA':
                p, q = data['p'], data['q']
                objData = (0, data['n'], data['e'], data['d'], q, p,
                           data['d'] % (q - 1), data['d'] % (p - 1),
                           data['u'])
            else:
                objData = (0, data['p'], data['q'], data['g'], data['y'],
                           data['x'])
            asn1Sequence = univ.Sequence()
            for index, value in itertools.izip(itertools.count(), objData):
                asn1Sequence.setComponentByPosition(index, univ.Integer(value))
            asn1Data = berEncoder.encode(asn1Sequence)
            if extra:
                iv = randbytes.secureRandom(8)
                hexiv = ''.join(['%02X' % ord(x) for x in iv])
                lines.append('Proc-Type: 4,ENCRYPTED')
                lines.append('DEK-Info: DES-EDE3-CBC,%s\n' % hexiv)
                ba = md5(extra + iv).digest()
                bb = md5(ba + extra + iv).digest()
                encKey = (ba + bb)[:24]
                padLen = 8 - (len(asn1Data) % 8)
                asn1Data += (chr(padLen) * padLen)

                encryptor = Cipher(
                    algorithms.TripleDES(encKey),
                    modes.CBC(iv),
                    backend=default_backend()
                ).encryptor()

                asn1Data = encryptor.update(asn1Data) + encryptor.finalize()

            b64Data = base64.encodestring(asn1Data).replace('\n', '')
            lines += [b64Data[i:i + 64] for i in range(0, len(b64Data), 64)]
            lines.append('-----END %s PRIVATE KEY-----' % self.type())
            return '\n'.join(lines)


    def _toString_LSH(self):
        """
        Return a public or private LSH key.  See _fromString_PUBLIC_LSH and
        _fromString_PRIVATE_LSH for the key formats.

        @rtype: C{str}
        """
        data = self.data()
        if self.isPublic():
            if self.type() == 'RSA':
                keyData = sexpy.pack([['public-key',
                                       ['rsa-pkcs1-sha1',
                                        ['n', common.MP(data['n'])[4:]],
                                        ['e', common.MP(data['e'])[4:]]]]])
            elif self.type() == 'DSA':
                keyData = sexpy.pack([['public-key',
                                       ['dsa',
                                        ['p', common.MP(data['p'])[4:]],
                                        ['q', common.MP(data['q'])[4:]],
                                        ['g', common.MP(data['g'])[4:]],
                                        ['y', common.MP(data['y'])[4:]]]]])
            return '{' + base64.encodestring(keyData).replace('\n', '') + '}'
        else:
            if self.type() == 'RSA':
                p, q = data['p'], data['q']
                return sexpy.pack([['private-key',
                                    ['rsa-pkcs1',
                                     ['n', common.MP(data['n'])[4:]],
                                     ['e', common.MP(data['e'])[4:]],
                                     ['d', common.MP(data['d'])[4:]],
                                     ['p', common.MP(q)[4:]],
                                     ['q', common.MP(p)[4:]],
                                     ['a', common.MP(data['d'] % (q - 1))[4:]],
                                     ['b', common.MP(data['d'] % (p - 1))[4:]],
                                     ['c', common.MP(data['u'])[4:]]]]])
            elif self.type() == 'DSA':
                return sexpy.pack([['private-key',
                                    ['dsa',
                                     ['p', common.MP(data['p'])[4:]],
                                     ['q', common.MP(data['q'])[4:]],
                                     ['g', common.MP(data['g'])[4:]],
                                     ['y', common.MP(data['y'])[4:]],
                                     ['x', common.MP(data['x'])[4:]]]]])


    def _toString_AGENTV3(self):
        """
        Return a private Secure Shell Agent v3 key.  See
        _fromString_AGENTV3 for the key format.

        @rtype: C{str}
        """
        data = self.data()
        if not self.isPublic():
            if self.type() == 'RSA':
                values = (data['e'], data['d'], data['n'], data['u'],
                          data['p'], data['q'])
            elif self.type() == 'DSA':
                values = (data['p'], data['q'], data['g'], data['y'],
                          data['x'])
            return common.NS(self.sshType()) + ''.join(map(common.MP, values))


    def sign(self, data):
        """
        Returns a signature with this Key.

        @type data: C{str}
        @rtype: C{str}
        """
        if self.type() == 'RSA':
            signer = self._keyObject.signer(
                padding.PKCS1v15(), hashes.SHA1())

        elif self.type() == 'DSA':
            # FIXME: see how to insert the random part into PyCA code.
            randomBytes = randbytes.secureRandom(19)
            signer = self._keyObject.signer(hashes.SHA1())

        signer.update(data)
        ret = common.NS(signer.finalize())

        return common.NS(self.sshType()) + ret


    def verify(self, signature, data):
        """
        Returns true if the signature for data is valid for this Key.

        @type signature: C{str}
        @type data: C{str}
        @rtype: C{bool}
        """
        if len(signature) == 40:
            # DSA key with no padding
            signatureType, signature = 'ssh-dss', common.NS(signature)
        else:
            signatureType, signature = common.getNS(signature)
        if signatureType != self.sshType():
            return False
        if self.type() == 'RSA':
            verifier = self._keyObject.verifier(
                common.getNS(signature)[0],
                padding.PKCS1v15(),
                hashes.SHA1(),
            )
        elif self.type() == 'DSA':
            verifier = self._keyObject.verifier(
                common.getNS(signature)[0],
                hashes.SHA1(),
                )

        verifier.update(data)
        try:
            verifier.verify()
        except InvalidSignature:
            return False
        else:
            return True



def objectType(obj):
    """
    Return the SSH key type corresponding to a
    C{Crypto.PublicKey.pubkey.pubkey} object.

    @type obj:  C{Crypto.PublicKey.pubkey.pubkey}
    @rtype:     C{str}
    """
    if isinstance(obj, (RSAPublicKey, RSAPrivateKey)):
        return 'ssh-rsa'
    elif isinstance(obj, (DSAPublicKey, DSAPrivateKey)):
        return 'ssh-dss'
    else:
        raise BadKeyError("invalid key object", obj)
