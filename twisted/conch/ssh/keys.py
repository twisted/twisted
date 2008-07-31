# -*- test-case-name: twisted.conch.test.test_keys -*-
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

#

"""
Handling of RSA and DSA keys.

Maintainer: U{Paul Swartz}
"""

# base library imports
import base64
import sha, md5
import warnings

# external library imports
from Crypto.Cipher import DES3
from Crypto.PublicKey import RSA, DSA
from Crypto import Util

# twisted
from twisted.python import randbytes

# sibling imports
from twisted.conch.ssh import asn1, common, sexpy


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

    @ivar keyObject: The C{Crypto.PublicKey.pubkey.pubkey} object that
                  operations are performed with.
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
        if method.func_code.co_argcount == 2: # no passphrase
            if passphrase:
                raise BadKeyError('key not encrypted')
            return method(data)
        else:
            return method(data, passphrase)
    fromString = classmethod(fromString)

    def _fromString_BLOB(Class, blob):
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
        @return: a C{Crypto.PublicKey.pubkey.pubkey} object
        @raises BadKeyError: if the key type (the first string) is unknown.
        """
        keyType, rest = common.getNS(blob)
        if keyType == 'ssh-rsa':
            e, n, rest = common.getMP(rest, 2)
            return Class(RSA.construct((n, e)))
        elif keyType == 'ssh-dss':
            p, q, g, y, rest = common.getMP(rest, 4)
            return Class(DSA.construct((y, g, p, q)))
        else:
            raise BadKeyError('unknown blob type: %s' % keyType)
    _fromString_BLOB = classmethod(_fromString_BLOB)

    def _fromString_PUBLIC_OPENSSH(Class, data):
        """
        Return a public key object corresponding to this OpenSSH public key
        string.  The format of an OpenSSH public key string is::
            <key type> <base64-encoded public key blob>

        @type data: C{str}
        @return: A {Crypto.PublicKey.pubkey.pubkey} object
        @raises BadKeyError: if the blob type is unknown.
        """
        blob = base64.decodestring(data.split()[1])
        return Class._fromString_BLOB(blob)
    _fromString_PUBLIC_OPENSSH = classmethod(_fromString_PUBLIC_OPENSSH)

    def _fromString_PRIVATE_OPENSSH(Class, data, passphrase):
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
        @return: a C{Crypto.PublicKey.pubkey.pubkey} object
        @raises BadKeyError: if
            * a passphrase is provided for an unencrypted key
            * a passphrase is not provided for an encrypted key
            * the ASN.1 encoding is incorrect
        """
        lines = [x + '\n' for x in data.split('\n')]
        kind = lines[0][11:14]
        if lines[1].startswith('Proc-Type: 4,ENCRYPTED'): # encrypted key
            ivdata = lines[2].split(',')[1][:-1]
            iv = ''.join([chr(int(ivdata[i:i + 2], 16)) for i in range(0,
                len(ivdata), 2)])
            if not passphrase:
                raise EncryptedKeyError('encrypted key with no passphrase')
            ba = md5.new(passphrase + iv).digest()
            bb = md5.new(ba + passphrase + iv).digest()
            decKey = (ba + bb)[:24]
            b64Data = base64.decodestring(''.join(lines[3:-1]))
            keyData = DES3.new(decKey, DES3.MODE_CBC, iv).decrypt(b64Data)
            removeLen = ord(keyData[-1])
            keyData = keyData[:-removeLen]
        else:
            keyData = base64.decodestring(''.join(lines[1:-1]))
        try:
            decodedKey = asn1.parse(keyData)
        except Exception, e:
            raise BadKeyError, 'something wrong with decode'
        if kind == 'RSA':
            if len(decodedKey) == 2: # alternate RSA key
                decodedKey = decodedKey[0]
            n, e, d, p, q = decodedKey[1:6]
            if p > q: # make p smaller than q
                p, q = q, p
            return Class(RSA.construct((n, e, d, p, q)))
        elif kind == 'DSA':
            p, q, g, y, x = decodedKey[1: 6]
            return Class(DSA.construct((y, g, p, q, x)))
    _fromString_PRIVATE_OPENSSH = classmethod(_fromString_PRIVATE_OPENSSH)

    def _fromString_PUBLIC_LSH(Class, data):
        """
        Return a public key corresponding to this LSH public key string.
        The LSH public key string format is::
            <s-expression: ('public-key', (<key type>, (<name, <value>)+))>

        The names for a RSA (key type 'rsa-pkcs1-sha1') key are: n, e.
        The names for a DSA (key type 'dsa') key are: y, g, p, q.

        @type data: C{str}
        @return: a C{Crypto.PublicKey.pubkey.pubkey} object
        @raises BadKeyError: if the key type is unknown
        """
        sexp = sexpy.parse(base64.decodestring(data[1:-1]))
        assert sexp[0] == 'public-key'
        kd = {}
        for name, data in sexp[1][1:]:
            kd[name] = common.getMP(common.NS(data))[0]
        if sexp[1][0] == 'dsa':
            return Class(DSA.construct((kd['y'], kd['g'], kd['p'], kd['q'])))
        elif sexp[1][0] == 'rsa-pkcs1-sha1':
            return Class(RSA.construct((kd['n'], kd['e'])))
        else:
            raise BadKeyError('unknown lsh key type %s' % sexp[1][0])
    _fromString_PUBLIC_LSH = classmethod(_fromString_PUBLIC_LSH)

    def _fromString_PRIVATE_LSH(Class, data):
        """
        Return a private key corresponding to this LSH private key string.
        The LSH private key string format is::
            <s-expression: ('private-key', (<key type>, (<name>, <value>)+))>

        The names for a RSA (key type 'rsa-pkcs1-sha1') key are: n, e, d, p, q.
        The names for a DSA (key type 'dsa') key are: y, g, p, q, x.

        @type data: C{str}
        @return: a {Crypto.PublicKey.pubkey.pubkey} object
        @raises BadKeyError: if the key type is unknown
        """
        sexp = sexpy.parse(data)
        assert sexp[0] == 'private-key'
        kd = {}
        for name, data in sexp[1][1:]:
            kd[name] = common.getMP(common.NS(data))[0]
        if sexp[1][0] == 'dsa':
            assert len(kd) == 5, len(kd)
            return Class(DSA.construct((kd['y'], kd['g'], kd['p'],
                kd['q'], kd['x'])))
        elif sexp[1][0] == 'rsa-pkcs1':
            assert len(kd) == 8, len(kd)
            if kd['p'] > kd['q']: # make p smaller than q
                kd['p'], kd['q'] = kd['q'], kd['p']
            return Class(RSA.construct((kd['n'], kd['e'], kd['d'],
                kd['p'], kd['q'])))
        else:
            raise BadKeyError('unknown lsh key type %s' % sexp[1][0])
    _fromString_PRIVATE_LSH = classmethod(_fromString_PRIVATE_LSH)

    def _fromString_AGENTV3(Class, data):
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
        @return: a C{Crypto.PublicKey.pubkey.pubkey} object
        @raises BadKeyError: if the key type (the first string) is unknown
        """
        keyType, data = common.getNS(data)
        if keyType == 'ssh-dss':
            p, data = common.getMP(data)
            q, data = common.getMP(data)
            g, data = common.getMP(data)
            y, data = common.getMP(data)
            x, data = common.getMP(data)
            return Class(DSA.construct((y,g,p,q,x)))
        elif keyType == 'ssh-rsa':
            e, data = common.getMP(data)
            d, data = common.getMP(data)
            n, data = common.getMP(data)
            u, data = common.getMP(data)
            p, data = common.getMP(data)
            q, data = common.getMP(data)
            return Class(RSA.construct((n,e,d,p,q,u)))
        else:
            raise BadKeyError("unknown key type %s" % keyType)
    _fromString_AGENTV3 = classmethod(_fromString_AGENTV3)

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

    def __init__(self, keyObject):
        """
        Initialize a PublicKey with a C{Crypto.PublicKey.pubkey.pubkey}
        object.

        @type keyObject: C{Crypto.PublicKey.pubkey.pubkey}
        """
        self.keyObject = keyObject

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
        lines = ['<%s %s (%s bits)' % (self.type(),
            self.isPublic() and 'Public Key' or 'Private Key',
            self.keyObject.size())]
        for k, v in self.data().items():
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

    def isPublic(self):
        """
        Returns True if this Key is a public key.
        """
        return not self.keyObject.has_private()

    def public(self):
        """
        Returns a version of this key containing only the public key data.
        If this is a public key, this may or may not be the same object
        as self.
        """
        return Key(self.keyObject.publickey())

    def type(self):
        """
        Return the type of the object we wrap.  Currently this can only be
        'RSA' or 'DSA'.
        """
        # the class is Crypto.PublicKey.<type>.<stuff we don't care about>
        klass = str(self.keyObject.__class__)
        if klass.startswith('Crypto.PublicKey'):
            type = klass.split('.')[2]
        else:
            raise RuntimeError('unknown type of object: %r' % self.keyObject)
        if type in ('RSA', 'DSA'):
            return type
        else:
            raise RuntimeError('unknown type of key: %s' % type)

    def sshType(self):
        """
        Return the type of the object we wrap as defined in the ssh protocol.
        Currently this can only be 'ssh-rsa' or 'ssh-dss'.
        """
        return {'RSA':'ssh-rsa', 'DSA':'ssh-dss'}[self.type()]

    def data(self):
        """
        Return the values of the public key as a dictionary.

        @rtype: C{dict}
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

    def toString(self, type, extra=None):
        """
        Create a string representation of this key.  If the key is a
        private key and you want the represenation of its public key,
        use .public().toString().  type maps to a _toString_* method.
        The extra paramater allows passing data to some of the method.
        For public OpenSSH keys, it represents a comment.
        For private OpenSSH keys, it represents a passphrase.

        @type type: C{str}
        @type extra: C{str}
        @rtype: C{str}
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
            if extra:
                iv = randbytes.secureRandom(8)
                hexiv = ''.join(['%02X' % ord(x) for x in iv])
                lines.append('Proc-Type: 4,ENCRYPTED')
                lines.append('DEK-Info: DES-EDE3-CBC,%s\n' % hexiv)
                ba = md5.new(extra + iv).digest()
                bb = md5.new(ba + extra + iv).digest()
                encKey = (ba + bb)[:24]
            asn1Data = asn1.pack([objData])
            if extra:
                padLen = 8 - (len(asn1Data) % 8)
                asn1Data += (chr(padLen) * padLen)
                asn1Data = DES3.new(encKey, DES3.MODE_CBC,
                    iv).encrypt(asn1Data)
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
                keyData = sexpy.pack([['public-key', ['rsa-pkcs1-sha1',
                                    ['n', common.MP(data['n'])[4:]],
                                    ['e', common.MP(data['e'])[4:]]]]])
            elif self.type() == 'DSA':
                keyData = sexpy.pack([['public-key', ['dsa',
                                    ['p', common.MP(data['p'])[4:]],
                                    ['q', common.MP(data['q'])[4:]],
                                    ['g', common.MP(data['g'])[4:]],
                                    ['y', common.MP(data['y'])[4:]]]]])
            return '{' + base64.encodestring(keyData).replace('\n', '') + '}'
        else:
            if self.type() == 'RSA':
                p, q = data['p'], data['q']
                return sexpy.pack([['private-key', ['rsa-pkcs1',
                                ['n', common.MP(data['n'])[4:]],
                                ['e', common.MP(data['e'])[4:]],
                                ['d', common.MP(data['d'])[4:]],
                                ['p', common.MP(q)[4:]],
                                ['q', common.MP(p)[4:]],
                                ['a', common.MP(data['d'] % (q - 1))[4:]],
                                ['b', common.MP(data['d'] % (p - 1))[4:]],
                                ['c', common.MP(data['u'])[4:]]]]])
            elif self.type() == 'DSA':
                return sexpy.pack([['private-key', ['dsa',
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
            digest = pkcs1Digest(data, self.keyObject.size()/8)
            signature = self.keyObject.sign(digest, '')[0]
            ret = common.NS(Util.number.long_to_bytes(signature))
        elif self.type() == 'DSA':
            digest = sha.new(data).digest()
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

        @type signature: C{str}
        @type data: C{str}
        @rtype: C{bool}
        """
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
            digest = sha.new(data).digest()
        return self.keyObject.verify(digest, numbers)

def getPublicKeyString(filename=None, line=0, data=''):
    """
    Return a public key string suitable for being sent over the wire.
    Takes a filename or data of a public key.  Currently handles OpenSSH
    and LSH keys.

    This function has been deprecated since Twisted Conch 0.9.  Use
    Key.fromString() instead.

    @type filename: C{str}
    @type line:     C{int}
    @type data:     C{str}
    @rtype:         C{str}
    """
    warnings.warn("getPublicKeyString is deprecated since Twisted Conch 0.9."
            "  Use Key.fromString().",
            DeprecationWarning, stacklevel=2)
    if filename and data:
        raise BadKeyError("either filename or data, not both")
    if filename:
        lines = open(filename).readlines()
        data = lines[line]
    return Key.fromString(data).blob()

def makePublicKeyString(obj, comment='', kind='openssh'):
    """
    Return an public key given a C{Crypto.PublicKey.pubkey.pubkey}
    object.
    kind is one of ('openssh', 'lsh')

    This function is deprecated since Twisted Conch 0.9.  Instead use
    Key(obj).toString().

    @type obj:      C{Crypto.PublicKey.pubkey.pubkey}
    @type comment:  C{str}
    @type kind:     C{str}
    @rtype:         C{str}
    """
    warnings.warn("makePublicKeyString is deprecated since Twisted Conch 0.9."
            "  Use Key(obj).toString().",
            DeprecationWarning, stacklevel=2)
    return Key(obj).public().toString(kind, comment)

def getPublicKeyObject(data):
    """
    Return a C{Crypto.PublicKey.pubkey.pubkey} corresponding to the SSHv2
    public key data.  data is in the over-the-wire public key format.

    This function is deprecated since Twisted Conch 0.9. Instead, use
    Key.fromString().

    @type data:     C{str}
    @rtype:         C{Crypto.PublicKey.pubkey.pubkey}
    """
    warnings.warn("getPublicKeyObject is deprecated since Twisted Conch 0.9."
            "  Use Key.fromString().",
            DeprecationWarning, stacklevel=2)
    return Key.fromString(data).keyObject

def getPrivateKeyObject(filename=None, data='', passphrase=''):
    """
    Return a C{Crypto.PublicKey.pubkey.pubkey} object corresponding to the
    private key file/data.  If the private key is encrypted, passphrase B{must}
    be specified, other wise a L{BadKeyError} will be raised.

    This method is deprecated since Twisted Conch 0.9.  Instead, use
    the fromString or fromFile classmethods of Key.

    @type filename:     C{str}
    @type data:         C{str}
    @type passphrase:   C{str}
    @rtype: C{Crypto.PublicKey.pubkey.pubkey}
    @raises BadKeyError: if the key is invalid or a passphrase is not specified
    """
    warnings.warn("getPrivateKeyObject is deprecated since Twisted Conch 0.9."
            "  Use Key.fromString().",
            DeprecationWarning, stacklevel=2)
    if filename and data:
        raise BadKeyError("either filename or data, not both")
    if filename:
        return Key.fromFile(filename, passphrase=passphrase).keyObject
    else:
        return Key.fromString(data, passphrase=passphrase).keyObject

def makePrivateKeyString(obj, passphrase=None, kind='openssh'):
    """
    Return an OpenSSH-style private key for a
    C{Crypto.PublicKey.pubkey.pubkey} object.  If passphrase is given, encrypt
    the private key with it.
    kind is one of ('openssh', 'lsh', 'agentv3')

    This function is deprecated since Twisted Conch 0.9. Instead use
    Key(obj).toString().

    @type obj:          C{Crypto.PublicKey.pubkey.pubkey}
    @type passphrase:   C{str}/C{None}
    @type kind:         C{str}
    @rtype:             C{str}
    """
    warnings.warn("makePrivateKeyString is deprecated since Twisted Conch 0.9."
            "  Use Key(obj).toString().",
            DeprecationWarning, stacklevel=2)
    return Key(obj).toString(kind, passphrase)

def makePublicKeyBlob(obj):
    """
    Make a public key blob from a C{Crypto.PublicKey.pubkey.pubkey}.

    This function is deprecated since Twisted Conch 0.9.  Use
    Key().blob() instead.
    """
    warnings.warn("makePublicKeyBlob is deprecated since Twisted Conch 0.9."
            "  Use Key(obj).blob().",
            DeprecationWarning, stacklevel=2)
    return Key(obj).blob()

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
    try:
        return keyDataMapping[tuple(obj.keydata)]
    except (KeyError, AttributeError):
        raise BadKeyError("invalid key object", obj)

def pkcs1Pad(data, messageLength):
    """
    Pad out data to messageLength according to the PKCS#1 standard.
    @type data: C{str}
    @type messageLength: C{int}
    """
    lenPad = messageLength - 2 - len(data)
    return '\x01' + ('\xff' * lenPad) + '\x00' + data

def pkcs1Digest(data, messageLength):
    """
    Create a message digest using the SHA1 hash algorithm according to the
    PKCS#1 standard.
    @type data: C{str}
    @type messageLength: C{str}
    """
    digest = sha.new(data).digest()
    return pkcs1Pad(ID_SHA1+digest, messageLength)

def lenSig(obj):
    """
    Return the length of the signature in bytes for a key object.

    @type obj: C{Crypto.PublicKey.pubkey.pubkey}
    @rtype: C{long}
    """
    return obj.size()/8

def signData(obj, data):
    """
    Sign the data with the given C{Crypto.PublicKey.pubkey.pubkey} object.

    This method is deprecated since Twisted Conch 0.9.  Instead use
    Key().sign().

    @type obj:  C{Crypto.PublicKey.pubkey.pubkey}
    @type data: C{str}
    @rtype:     C{str}
    """
    warnings.warn("signData is deprecated since Twisted Conch 0.9."
            "  Use Key(obj).sign(data).",
            DeprecationWarning, stacklevel=2)
    return Key(obj).sign(data)

def verifySignature(obj, sig, data):
    """
    Verify that the signature for the data is valid.

    This method is deprecated since Twisted Conch 0.9.  Use
    Key().verify().

    @type obj:  C{Crypto.PublicKey.pubkey.pubkey}
    @type sig:  C{str}
    @type data: C{str}
    @rtype:     C{bool}
    """
    warnings.warn("verifySignature is deprecated since Twisted Conch 0.9."
            "  Use Key(obj).verify(signature, data).",
            DeprecationWarning, stacklevel=2)
    return Key(obj).verify(sig, data)

def printKey(obj):
    """
    Pretty print a C{Crypto.PublicKey.pubkey.pubkey} object.

    This function is deprecated since Twisted Conch 0.9.  Use
    repr(Key()).

    @type obj: C{Crypto.PublicKey.pubkey.pubkey}
    """
    warnings.warn("printKey is deprecated since Twisted Conch 0.9."
            "  Use repr(Key(obj)).",
            DeprecationWarning, stacklevel=2)
    return repr(Key(obj))[1:-1]

ID_SHA1 = '\x30\x21\x30\x09\x06\x05\x2b\x0e\x03\x02\x1a\x05\x00\x04\x14'
