# -*- test-case-name: twisted.conch.test.test_keys -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Handling of RSA and DSA keys.

Maintainer: U{Paul Swartz}
"""

import base64
import itertools
from hashlib import md5, sha1

from Crypto.Cipher import DES3, AES
from Crypto.PublicKey import RSA, DSA
from Crypto import Util
from pyasn1.error import PyAsn1Error
from pyasn1.type import univ
from pyasn1.codec.ber import decoder as berDecoder
from pyasn1.codec.ber import encoder as berEncoder

from twisted.python import randbytes
from twisted.conch.ssh import common, sexpy



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

    @ivar keyObject: The underlying wrapped key object.
    @type keyObject: C{Crypto.PublicKey.pubkey.pubkey}
    """
    @classmethod
    def fromFile(cls, filename, type=None, passphrase=None):
        """
        Return a L{Key} object corresponding to the data in filename.

        @param filename: The filename of the file containing key data.
        @type filename: L{bytes}

        @param type: As with L{fromString<Key.fromString>}.
        @type type: As with L{fromString<Key.fromString>}.

        @param passphrase: As with L{fromString<Key.fromString>}.
        @type passphrase: As with L{fromString<Key.fromString>}.
        """
        return cls.fromString(file(filename, 'rb').read(), type, passphrase)


    @classmethod
    def fromString(cls, data, type=None, passphrase=None):
        """
        Return a L{Key} object corresponding to the string data.

        @param data: The data to create the key from.
        @type data: L{bytes}

        @param type: The type of data. Optional. Has to match one of the
            C{_fromString_*} methods. If unspecified,
            L{_guessStringType<Key._guessStringType>} is used to guess a type.
        @type type: L{NoneType<types.NoneType>} or L{bytes}

        @param passphrase: The passphrase to decrypt the key. Optional, only
            if the key is encrypted.
        @type passphrase: L{NoneType<types.NoneType>} or L{bytes}

        @return: A L{Key} object built from the C{data}.
        @rtype: L{Key}
        """
        if type is None:
            type = cls._guessStringType(data)
        if type is None:
            raise BadKeyError('cannot guess the type of {0!r}'.format(data))

        methodName = '_fromString_{0}'.format(type.upper())
        method = getattr(cls, methodName, None)
        if method is None:
            raise BadKeyError('no _fromString method for {0}'.format(type))
        if method.func_code.co_argcount == 2:  # no passphrase
            if passphrase: # XXX: Doesn't he mean "passphrase is not
                # None"? what if the passphrase is empty?
                raise BadKeyError('key not encrypted')
            return method(data)
        else:
            return method(data, passphrase)


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

        @param blob: The public key blob to produce a key from.
        @type blob: L{bytes}

        @return: The public key.
        @rtype: L{Key}

        @raises BadKeyError: if the key type (the first string) is unknown.
        """
        keyType, rest = common.getNS(blob)
        if keyType == 'ssh-rsa':
            e, n, rest = common.getMP(rest, 2)
            return cls(RSA.construct((n, e)))
        elif keyType == 'ssh-dss':
            p, q, g, y, rest = common.getMP(rest, 4)
            return cls(DSA.construct((y, g, p, q)))
        else:
            raise BadKeyError('unknown blob type: {0}'.format(keyType))


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

        @param blob: The private key blob to produce a key from.
        @type blob: L{bytes}

        @return: The private key.
        @rtype: L{Key}

        @raises BadKeyError: if the key type (the first string) is unknown.
        """
        keyType, rest = common.getNS(blob)

        if keyType == 'ssh-rsa':
            n, e, d, u, p, q, rest = common.getMP(rest, 6)
            rsakey = cls(RSA.construct((n, e, d, p, q, u)))
            return rsakey
        elif keyType == 'ssh-dss':
            p, q, g, y, x, rest = common.getMP(rest, 5)
            dsakey = cls(DSA.construct((y, g, p, q, x)))
            return dsakey
        else:
            raise BadKeyError('unknown blob type: {0}'.format(keyType))


    @classmethod
    def _fromString_PUBLIC_OPENSSH(cls, data):
        """
        Return a public key object corresponding to this OpenSSH public key
        string.  The format of an OpenSSH public key string is::
            <key type> <base64-encoded public key blob>

        @param data: The key data.
        @type data: L{bytes}

        @return: The public key represented by this data.
        @rtype: L{Key}

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

        @param data: The key data.
        @type data: L{bytes}

        @param passphrase: The key's passphrase.
        @type passphrase: L{bytes}

        @return: The private key represented by this data.
        @rtype: L{Key}

        @raises BadKeyError: When the ASN.1 encoding the key is incorrect.
            Also when a passphrase was provided, but the key wasn't encrypted.

        @raises EncryptedKeyError: If the key is encrypted, but no passphrase
            was provided.
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
                raise BadKeyError('invalid DEK-info {0!r}'.format(lines[2]))

            if cipher == 'AES-128-CBC':
                CipherClass = AES
                keySize = 16
                if len(ivdata) != 32:
                    raise BadKeyError('AES encrypted key with a bad IV')
            elif cipher == 'DES-EDE3-CBC':
                CipherClass = DES3
                keySize = 24
                if len(ivdata) != 16:
                    raise BadKeyError('DES encrypted key with a bad IV')
            else:
                errorMessage = 'unknown encryption type {0!r}'.format(cipher)
                raise BadKeyError(errorMessage)

            # extract keyData for decoding
            iv = ''.join([chr(int(ivdata[i:i + 2], 16))
                          for i in range(0, len(ivdata), 2)])
            ba = md5(passphrase + iv[:8]).digest()
            bb = md5(ba + passphrase + iv[:8]).digest()
            decKey = (ba + bb)[:keySize]
            b64Data = base64.decodestring(''.join(lines[3:-1]))
            keyData = CipherClass.new(decKey,
                                      CipherClass.MODE_CBC,
                                      iv).decrypt(b64Data)
            removeLen = ord(keyData[-1])
            keyData = keyData[:-removeLen]
        else:
            b64Data = ''.join(lines[1:-1])
            keyData = base64.decodestring(b64Data)

        try:
            decodedKey = berDecoder.decode(keyData)[0]
        except PyAsn1Error, e:
            errorTemplate = 'Failed to decode key (Bad Passphrase?): {0}'
            raise BadKeyError(errorTemplate.format(e))

        if kind == 'RSA':
            if len(decodedKey) == 2:  # alternate RSA key
                decodedKey = decodedKey[0]
            if len(decodedKey) < 6:
                raise BadKeyError('RSA key failed to decode properly')

            n, e, d, p, q = [long(value) for value in decodedKey[1:6]]
            if p > q:  # make p smaller than q
                p, q = q, p
            return cls(RSA.construct((n, e, d, p, q)))
        elif kind == 'DSA':
            p, q, g, y, x = [long(value) for value in decodedKey[1: 6]]
            if len(decodedKey) < 6:
                raise BadKeyError('DSA key failed to decode properly')
            return cls(DSA.construct((y, g, p, q, x)))


    @classmethod
    def _fromString_PUBLIC_LSH(cls, data):
        """
        Return a public key corresponding to this LSH public key string.
        The LSH public key string format is::
            <s-expression: ('public-key', (<key type>, (<name, <value>)+))>

        The names for a RSA (key type 'rsa-pkcs1-sha1') key are: n, e.
        The names for a DSA (key type 'dsa') key are: y, g, p, q.

        @type data: L{bytes}
        @return: a L{twisted.conch.ssh.keys.Key} object
        @raises BadKeyError: if the key type is unknown
        """
        sexp = sexpy.parse(base64.decodestring(data[1:-1]))
        assert sexp[0] == 'public-key'
        kd = {}
        for name, data in sexp[1][1:]:
            kd[name] = common.getMP(common.NS(data))[0]
        if sexp[1][0] == 'dsa':
            return cls(DSA.construct((kd['y'], kd['g'], kd['p'], kd['q'])))
        elif sexp[1][0] == 'rsa-pkcs1-sha1':
            return cls(RSA.construct((kd['n'], kd['e'])))
        else:
            raise BadKeyError('unknown lsh key type {0}'.format(sexp[1][0]))
    _fromString_PUBLIC_LSH = classmethod(_fromString_PUBLIC_LSH)


    @classmethod
    def _fromString_PRIVATE_LSH(cls, data):
        """
        Return a private key corresponding to this LSH private key string.
        The LSH private key string format is::
            <s-expression: ('private-key', (<key type>, (<name>, <value>)+))>

        The names for a RSA (key type 'rsa-pkcs1-sha1') key are: n, e, d, p, q.
        The names for a DSA (key type 'dsa') key are: y, g, p, q, x.

        @type data: L{bytes}
        @return: a L{twisted.conch.ssh.keys.Key} object
        @raises BadKeyError: if the key type is unknown
        """
        sexp = sexpy.parse(data)
        assert sexp[0] == 'private-key'
        kd = {}
        for name, data in sexp[1][1:]:
            kd[name] = common.getMP(common.NS(data))[0]
        if sexp[1][0] == 'dsa':
            assert len(kd) == 5, len(kd)
            return cls(DSA.construct((kd['y'], kd['g'], kd['p'],
                                        kd['q'], kd['x'])))
        elif sexp[1][0] == 'rsa-pkcs1':
            assert len(kd) == 8, len(kd)
            if kd['p'] > kd['q']:  # make p smaller than q
                kd['p'], kd['q'] = kd['q'], kd['p']
            return cls(RSA.construct((kd['n'], kd['e'], kd['d'],
                                        kd['p'], kd['q'])))
        else:
            raise BadKeyError('unknown lsh key type {0}'.format(sexp[1][0]))


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

        @type data: L{bytes}
        @return: a L{twisted.conch.ssh.keys.Key} object
        @raises BadKeyError: if the key type (the first string) is unknown
        """
        keyType, data = common.getNS(data)
        if keyType == 'ssh-dss':
            p, data = common.getMP(data)
            q, data = common.getMP(data)
            g, data = common.getMP(data)
            y, data = common.getMP(data)
            x, data = common.getMP(data)
            return cls(DSA.construct((y, g, p, q, x)))
        elif keyType == 'ssh-rsa':
            e, data = common.getMP(data)
            d, data = common.getMP(data)
            n, data = common.getMP(data)
            u, data = common.getMP(data)
            p, data = common.getMP(data)
            q, data = common.getMP(data)
            return cls(RSA.construct((n, e, d, p, q, u)))
        else:
            raise BadKeyError("unknown key type {0}".format(keyType))


    @classmethod
    def _guessStringType(cls, data):
        """
        Guess the type of key in data.  The types map to C{_fromString_*}
        methods; C{"_fromString_{0}.format(returnValue.upper())"} will be the
        name of the appropriate C{_fromString} method for this key data.

        @param data: The key data to guess the type of.
        @type data: L{bytes}

        @return: The name of a key type.
        @rtype: L{str} (native string)
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


    def __init__(self, keyObject):
        """
        Initialize a Key with a L{Crypto.PublicKey.pubkey.pubkey} object.

        @param keyObject: The key object to initialize with.
        @type keyObject: L{Crypto.PublicKey.pubkey.pubkey}
        """
        self.keyObject = keyObject


    def __eq__(self, other):
        """
        Checks for equality with another object.

        @param other: The object to compare to.
        @type other: Any L{object}, preferably L{Key}.

        @return: L{True} if C{other} is a L{Key} representing the same key.
                 L{False} if it is a L{Key} representing a different key.
                 L{NotImplemented} if C{other} isn't a L{Key}.
        @rtype: L{bool} or L{NotImplementedType<types.NotImplementedType>}
        """
        if type(self) == type(other):
            return self.type() == other.type() and self.data() == other.data()
        else:
            return NotImplemented


    def __ne__(self, other):
        """
        Check for inequality with another object.

        @param other: The object to compare to.
        @type other: Any L{object}, preferably L{Key}.

        @return: L{True} if C{other} is a L{Key} representing a different key.
                 L{False} if it is a L{Key} representing the same key.
                 L{NotImplemented} if C{other} isn't a L{Key}.
        @rtype: L{bool} or L{NotImplementedType<types.NotImplementedType>}
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
                self.keyObject.size())]
        for k, v in sorted(self.data().items()):
            lines.append('attr %s:' % k)
            by = common.MP(v)[4:]
            while by:
                m = by[:15]
                by = by[15:]
                o = ''
                for c in m:
                    o = o + '%02x:' % (ord(c),)
                if len(m) < 15:
                    o = o[:-1]
                lines.append('\t' + o)
        lines[-1] = lines[-1] + '>'
        return '\n'.join(lines)


    def isPublic(self):
        """
        Returns L{True} if this is a public key.

        @returns: L{True} if this L{Key} is public, L{False} otherwise.
        @rtype: L{bool}
        """
        return not self.keyObject.has_private()


    def public(self):
        """
        Returns a version of this key containing only the public key data.
        If this is a public key, this may or may not be the same object
        as self.
        """
        return Key(self.keyObject.publickey())


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

        @rtype: L{bytes}
        """
        return ':'.join([x.encode('hex') for x in md5(self.blob()).digest()])


    def type(self):
        """
        Return the type of the object we wrap.  Currently this can only be
        C{b'RSA'} or C{b'DSA'}.

        @return: The type of the wrapped object.
        @rtype: L{bytes}
        """
        # the class is Crypto.PublicKey.<type>.<stuff we don't care about>
        mod = self.keyObject.__class__.__module__
        if mod.startswith('Crypto.PublicKey'):
            type = mod.split('.')[2]
        else:
            raise RuntimeError('unknown type of object: {0!r}'
                               .format(self.keyObject))
        if type in (b'RSA', b'DSA'):
            return type
        else:
            raise RuntimeError('unknown type of key: {0}'.format(type))


    def sshType(self):
        """
        Return the type of the object we wrap as defined in the ssh protocol.
        Currently this can only be C{b'ssh-rsa'} or C{b'ssh-dss'}.

        @return: The type as defined by the SSH protocol.
        @rtype: L{bytes}
        """
        return {b'RSA': b'ssh-rsa', b'DSA': b'ssh-dss'}[self.type()]


    def data(self):
        """
        Return the values of the public key as a dictionary.

        @return: A dictionary with all of the values in the public key.
        @rtype: L{dict}
        """
        keyData = {}
        for name in self.keyObject.keydata:
            value = getattr(self.keyObject, name, None)
            if value is not None:
                keyData[name] = value
        return keyData


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

        @return: The public key blob for this L{Key}.
        @rtype: L{bytes}
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
        C{key.public().toString()}. C{type} maps to a C{_toString_*} method.

        @param type: The type of string to emit.  Currently supported values
            are C{'OPENSSH'}, C{'LSH'}, and C{'AGENTV3'}.
        @type type: L{bytes}

        @param extra: Any extra data supported by the selected format which
            is not part of the key itself.  For public OpenSSH keys, this is
            a comment.  For private OpenSSH keys, this is a passphrase to
            encrypt with.
        @type extra: L{bytes} or L{NoneType<types.NoneType>}

        @rtype: L{bytes}
        """
        methodName = '_toString_{0}'.format(type.upper())
        method = getattr(self, methodName, None)
        if method is None:
            raise BadKeyError('unknown type: {0}'.format(type))
        if method.func_code.co_argcount == 2:
            return method(extra)
        else:
            return method()


    def _toString_OPENSSH(self, extra):
        """
        Return a public or private OpenSSH string.  See
        L{_fromString_PUBLIC_OPENSSH<Key._fromString_PUBLIC_OPENSSH>} and
        L{_fromString_PRIVATE_OPENSSH<Key._fromString_PRIVATE_OPENSSH>} for the
        string formats.  If extra is present, it represents a comment for a
        public key, or a passphrase for a private key.

        @param extra: Comment if this key is public, passphrase otherwise.
        @type extra: L{bytes}

        @return: The OpenSSH string for this L{Key}.
        @rtype: L{bytes}
        """
        data = self.data()
        if self.isPublic():
            b64Data = base64.encodestring(self.blob()).replace('\n', '')
            if not extra:
                extra = ''
            return ('%s %s %s' % (self.sshType(), b64Data, extra)).strip()
        else:
            lines = ['-----BEGIN {0} PRIVATE KEY-----'.format(self.type())]
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
                hexiv = ''.join(['%02X' % (ord(x),) for x in iv])
                lines.append('Proc-Type: 4,ENCRYPTED')
                lines.append('DEK-Info: DES-EDE3-CBC,%s\n' % (hexiv,))
                ba = md5(extra + iv).digest()
                bb = md5(ba + extra + iv).digest()
                encKey = (ba + bb)[:24]
                padLen = 8 - (len(asn1Data) % 8)
                asn1Data += (chr(padLen) * padLen)
                asn1Data = DES3.new(encKey, DES3.MODE_CBC,
                                    iv).encrypt(asn1Data)
            b64Data = base64.encodestring(asn1Data).replace('\n', '')
            lines += [b64Data[i:i + 64] for i in range(0, len(b64Data), 64)]
            lines.append('-----END {0} PRIVATE KEY-----'.format(self.type()))
            return '\n'.join(lines)


    def _toString_LSH(self):
        """
        Return a public or private LSH key. See
        L{_fromString_PUBLIC_LSH<Key._fromString_PUBLIC_LSH>} and
        L{_fromString_PRIVATE_LSH<Key._fromString_PRIVATE_SH>} for the key
        formats.

        @return: The LSH key.
        @rtype: L{bytes}
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
        L{_fromString_AGENTV3<Key._fromString_AGENTV3>} for the key format.

        @return: The private key.
        @rtype: L{bytes}
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
        Returns a signature with this L{Key}.

        @param data: The data to sign.
        @type data: L{bytes}

        @return: The signature of C{data}.
        @rtype: L{bytes}
        """
        if self.type() == 'RSA':
            digest = pkcs1Digest(data, self.keyObject.size() / 8)
            signature = self.keyObject.sign(digest, '')[0]
            ret = common.NS(Util.number.long_to_bytes(signature))
        elif self.type() == 'DSA':
            digest = sha1(data).digest()
            randomBytes = randbytes.secureRandom(19)
            sig = self.keyObject.sign(digest, randomBytes)
            # SSH insists that the DSS signature blob be two 160-bit integers
            # concatenated together. The sig[0], [1] numbers from obj.sign
            # are just numbers, and could be any length from 0 to 160 bits.
            # Make sure they are padded out to 160 bits (20 bytes each)
            ret = common.NS(Util.number.long_to_bytes(sig[0], 20) +
                            Util.number.long_to_bytes(sig[1], 20))
        return common.NS(self.sshType()) + ret


    def verify(self, signature, data):
        """
        Returns true if the signature for data is valid for this Key.

        @type signature: L{bytes}
        @type data: L{bytes}
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
            numbers = common.getMP(signature)
            digest = pkcs1Digest(data, self.keyObject.size() / 8)
        elif self.type() == 'DSA':
            signature = common.getNS(signature)[0]
            numbers = [Util.number.bytes_to_long(n) for n in signature[:20],
                       signature[20:]]
            digest = sha1(data).digest()
        return self.keyObject.verify(digest, numbers)



def objectType(obj):
    """
    Return the SSH key type corresponding to a
    C{Crypto.PublicKey.pubkey.pubkey} object.

    @type obj:  C{Crypto.PublicKey.pubkey.pubkey}
    @rtype:     L{bytes}
    """
    keyDataMapping = {
        ('n', 'e', 'd', 'p', 'q'): 'ssh-rsa',
        ('n', 'e', 'd', 'p', 'q', 'u'): 'ssh-rsa',
        ('y', 'g', 'p', 'q', 'x'): 'ssh-dss'
    }
    try:
        return keyDataMapping[tuple(obj.keydata)]
    except (KeyError, AttributeError):
        raise BadKeyError("invalid key object", obj)



def pkcs1Pad(data, messageLength):
    """
    Pad out data to messageLength according to the PKCS#1 standard.

    @param data: The data that will be padded.
    @type data: L{bytes}

    @param messageLength: The total length of the message.
    @type messageLength: L{int}

    @return: The message, padded according to PKCS#1.
    @rtype: L{bytes}
    """
    lenPad = messageLength - 2 - len(data)
    return '\x01' + ('\xff' * lenPad) + '\x00' + data



def pkcs1Digest(data, messageLength):
    """
    Create a message digest using the SHA1 hash algorithm according to the
    PKCS#1 standard.

    @param data: The data to produce a message digest of.
    @type data: L{bytes}

    @param messageLength: The length of the message.
    @type messageLength: L{bytes}

    @return: A PKCS#1 message digest, properly padded.
    @rtype: L{bytes}
    """
    digest = sha1(data).digest()
    return pkcs1Pad(ID_SHA1 + digest, messageLength)



def lenSig(obj):
    """
    Return the length of the signature in bytes for a key object.

    @type obj: L{Crypto.PublicKey.pubkey.pubkey}
    @rtype: L{long}
    """
    return obj.size() / 8


ID_SHA1 = '\x30\x21\x30\x09\x06\x05\x2b\x0e\x03\x02\x1a\x05\x00\x04\x14'
