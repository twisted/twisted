# -*- test-case-name: twisted.conch.test.test_knownhosts -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An implementation of the OpenSSH known_hosts database.

@since: 8.2
"""

from binascii import Error as DecodeError, b2a_base64
import hmac
import sys

from zope.interface import implements

from twisted.python.randbytes import secureRandom
if sys.version_info >= (2, 5):
    from twisted.python.hashlib import sha1
else:
    # We need to have an object with a method named 'new'.
    import sha as sha1

from twisted.internet import defer

from twisted.python import log
from twisted.conch.interfaces import IKnownHostEntry
from twisted.conch.error import HostKeyChanged, UserRejectedKey, InvalidEntry
from twisted.conch.ssh.keys import Key, BadKeyError


def _b64encode(s):
    """
    Encode a binary string as base64 with no trailing newline.
    """
    return b2a_base64(s).strip()



def _extractCommon(string):
    """
    Extract common elements of base64 keys from an entry in a hosts file.

    @return: a 4-tuple of hostname data (L{str}), ssh key type (L{str}), key
    (L{Key}), and comment (L{str} or L{None}).  The hostname data is simply the
    beginning of the line up to the first occurrence of whitespace.
    """
    elements = string.split(None, 2)
    if len(elements) != 3:
        raise InvalidEntry()
    hostnames, keyType, keyAndComment = elements
    splitkey = keyAndComment.split(None, 1)
    if len(splitkey) == 2:
        keyString, comment = splitkey
        comment = comment.rstrip("\n")
    else:
        keyString = splitkey[0]
        comment = None
    key = Key.fromString(keyString.decode('base64'))
    return hostnames, keyType, key, comment



class _BaseEntry(object):
    """
    Abstract base of both hashed and non-hashed entry objects, since they
    represent keys and key types the same way.

    @ivar keyType: The type of the key; either ssh-dss or ssh-rsa.
    @type keyType: L{str}

    @ivar publicKey: The server public key indicated by this line.
    @type publicKey: L{twisted.conch.ssh.keys.Key}

    @ivar comment: Trailing garbage after the key line.
    @type comment: L{str}
    """

    def __init__(self, keyType, publicKey, comment):
        self.keyType = keyType
        self.publicKey = publicKey
        self.comment = comment


    def matchesKey(self, keyObject):
        """
        Check to see if this entry matches a given key object.

        @type keyObject: L{Key}

        @rtype: bool
        """
        return self.publicKey == keyObject



class PlainEntry(_BaseEntry):
    """
    A L{PlainEntry} is a representation of a plain-text entry in a known_hosts
    file.

    @ivar _hostnames: the list of all host-names associated with this entry.
    @type _hostnames: L{list} of L{str}
    """

    implements(IKnownHostEntry)

    def __init__(self, hostnames, keyType, publicKey, comment):
        self._hostnames = hostnames
        super(PlainEntry, self).__init__(keyType, publicKey, comment)


    def fromString(cls, string):
        """
        Parse a plain-text entry in a known_hosts file, and return a
        corresponding L{PlainEntry}.

        @param string: a space-separated string formatted like "hostname
        key-type base64-key-data comment".

        @type string: L{str}

        @raise DecodeError: if the key is not valid encoded as valid base64.

        @raise InvalidEntry: if the entry does not have the right number of
        elements and is therefore invalid.

        @raise BadKeyError: if the key, once decoded from base64, is not
        actually an SSH key.

        @return: an IKnownHostEntry representing the hostname and key in the
        input line.

        @rtype: L{PlainEntry}
        """
        hostnames, keyType, key, comment = _extractCommon(string)
        self = cls(hostnames.split(","), keyType, key, comment)
        return self

    fromString = classmethod(fromString)


    def matchesHost(self, hostname):
        """
        Check to see if this entry matches a given hostname.

        @type hostname: L{str}

        @rtype: bool
        """
        return hostname in self._hostnames


    def toString(self):
        """
        Implement L{IKnownHostEntry.toString} by recording the comma-separated
        hostnames, key type, and base-64 encoded key.
        """
        fields = [','.join(self._hostnames),
                  self.keyType,
                  _b64encode(self.publicKey.blob())]
        if self.comment is not None:
            fields.append(self.comment)
        return ' '.join(fields)


class UnparsedEntry(object):
    """
    L{UnparsedEntry} is an entry in a L{KnownHostsFile} which can't actually be
    parsed; therefore it matches no keys and no hosts.
    """

    implements(IKnownHostEntry)

    def __init__(self, string):
        """
        Create an unparsed entry from a line in a known_hosts file which cannot
        otherwise be parsed.
        """
        self._string = string


    def matchesHost(self, hostname):
        """
        Always returns False.
        """
        return False


    def matchesKey(self, key):
        """
        Always returns False.
        """
        return False


    def toString(self):
        """
        Returns the input line, without its newline if one was given.
        """
        return self._string.rstrip("\n")



def _hmacedString(key, string):
    """
    Return the SHA-1 HMAC hash of the given key and string.
    """
    hash = hmac.HMAC(key, digestmod=sha1)
    hash.update(string)
    return hash.digest()



class HashedEntry(_BaseEntry):
    """
    A L{HashedEntry} is a representation of an entry in a known_hosts file
    where the hostname has been hashed and salted.

    @ivar _hostSalt: the salt to combine with a hostname for hashing.

    @ivar _hostHash: the hashed representation of the hostname.

    @cvar MAGIC: the 'hash magic' string used to identify a hashed line in a
    known_hosts file as opposed to a plaintext one.
    """

    implements(IKnownHostEntry)

    MAGIC = '|1|'

    def __init__(self, hostSalt, hostHash, keyType, publicKey, comment):
        self._hostSalt = hostSalt
        self._hostHash = hostHash
        super(HashedEntry, self).__init__(keyType, publicKey, comment)


    def fromString(cls, string):
        """
        Load a hashed entry from a string representing a line in a known_hosts
        file.

        @raise DecodeError: if the key, the hostname, or the is not valid
        encoded as valid base64

        @raise InvalidEntry: if the entry does not have the right number of
        elements and is therefore invalid, or the host/hash portion contains
        more items than just the host and hash.

        @raise BadKeyError: if the key, once decoded from base64, is not
        actually an SSH key.
        """
        stuff, keyType, key, comment = _extractCommon(string)
        saltAndHash = stuff[len(cls.MAGIC):].split("|")
        if len(saltAndHash) != 2:
            raise InvalidEntry()
        hostSalt, hostHash = saltAndHash
        self = cls(hostSalt.decode("base64"), hostHash.decode("base64"),
                   keyType, key, comment)
        return self

    fromString = classmethod(fromString)


    def matchesHost(self, hostname):
        """
        Implement L{IKnownHostEntry.matchesHost} to compare the hash of the
        input to the stored hash.
        """
        return (_hmacedString(self._hostSalt, hostname) == self._hostHash)


    def toString(self):
        """
        Implement L{IKnownHostEntry.toString} by base64-encoding the salt, host
        hash, and key.
        """
        fields = [self.MAGIC + '|'.join([_b64encode(self._hostSalt),
                                         _b64encode(self._hostHash)]),
                  self.keyType,
                  _b64encode(self.publicKey.blob())]
        if self.comment is not None:
            fields.append(self.comment)
        return ' '.join(fields)



class KnownHostsFile(object):
    """
    A structured representation of an OpenSSH-format ~/.ssh/known_hosts file.

    @ivar _entries: a list of L{IKnownHostEntry} providers.

    @ivar _savePath: the L{FilePath} to save new entries to.
    """

    def __init__(self, savePath):
        """
        Create a new, empty KnownHostsFile.

        You want to use L{KnownHostsFile.fromPath} to parse one of these.
        """
        self._entries = []
        self._savePath = savePath


    def hasHostKey(self, hostname, key):
        """
        @return: True if the given hostname and key are present in this file,
        False if they are not.

        @rtype: L{bool}

        @raise HostKeyChanged: if the host key found for the given hostname
        does not match the given key.
        """
        for lineidx, entry in enumerate(self._entries):
            if entry.matchesHost(hostname):
                if entry.matchesKey(key):
                    return True
                else:
                    raise HostKeyChanged(entry, self._savePath, lineidx + 1)
        return False


    def verifyHostKey(self, ui, hostname, ip, key):
        """
        Verify the given host key for the given IP and host, asking for
        confirmation from, and notifying, the given UI about changes to this
        file.

        @param ui: The user interface to request an IP address from.

        @param hostname: The hostname that the user requested to connect to.

        @param ip: The string representation of the IP address that is actually
        being connected to.

        @param key: The public key of the server.

        @return: a L{Deferred} that fires with True when the key has been
        verified, or fires with an errback when the key either cannot be
        verified or has changed.

        @rtype: L{Deferred}
        """
        hhk = defer.maybeDeferred(self.hasHostKey, hostname, key)
        def gotHasKey(result):
            if result:
                if not self.hasHostKey(ip, key):
                    ui.warn("Warning: Permanently added the %s host key for "
                            "IP address '%s' to the list of known hosts." %
                            (key.type(), ip))
                    self.addHostKey(ip, key)
                    self.save()
                return result
            else:
                def promptResponse(response):
                    if response:
                        self.addHostKey(hostname, key)
                        self.addHostKey(ip, key)
                        self.save()
                        return response
                    else:
                        raise UserRejectedKey()
                return ui.prompt(
                    "The authenticity of host '%s (%s)' "
                    "can't be established.\n"
                    "RSA key fingerprint is %s.\n"
                    "Are you sure you want to continue connecting (yes/no)? " %
                    (hostname, ip, key.fingerprint())).addCallback(promptResponse)
        return hhk.addCallback(gotHasKey)


    def addHostKey(self, hostname, key):
        """
        Add a new L{HashedEntry} to the key database.

        Note that you still need to call L{KnownHostsFile.save} if you wish
        these changes to be persisted.

        @return: the L{HashedEntry} that was added.
        """
        salt = secureRandom(20)
        keyType = "ssh-" + key.type().lower()
        entry = HashedEntry(salt, _hmacedString(salt, hostname),
                            keyType, key, None)
        self._entries.append(entry)
        return entry


    def save(self):
        """
        Save this L{KnownHostsFile} to the path it was loaded from.
        """
        p = self._savePath.parent()
        if not p.isdir():
            p.makedirs()
        self._savePath.setContent('\n'.join(
                [entry.toString() for entry in self._entries]) + "\n")


    def fromPath(cls, path):
        """
        @param path: A path object to use for both reading contents from and
        later saving to.

        @type path: L{FilePath}
        """
        self = cls(path)
        try:
            fp = path.open()
        except IOError:
            return self
        for line in fp:
            if line.startswith(HashedEntry.MAGIC):
                entry = HashedEntry.fromString(line)
            else:
                try:
                    entry = PlainEntry.fromString(line)
                except (DecodeError, InvalidEntry, BadKeyError):
                    entry = UnparsedEntry(line)
            self._entries.append(entry)
        return self

    fromPath = classmethod(fromPath)


class ConsoleUI(object):
    """
    A UI object that can ask true/false questions and post notifications on the
    console, to be used during key verification.

    @ivar opener: a no-argument callable which should open a console file-like
    object to be used for reading and writing.
    """

    def __init__(self, opener):
        self.opener = opener


    def prompt(self, text):
        """
        Write the given text as a prompt to the console output, then read a
        result from the console input.

        @return: a L{Deferred} which fires with L{True} when the user answers
        'yes' and L{False} when the user answers 'no'.  It may errback if there
        were any I/O errors.
        """
        d = defer.succeed(None)
        def body(ignored):
            f = self.opener()
            f.write(text)
            while True:
                answer = f.readline().strip().lower()
                if answer == 'yes':
                    f.close()
                    return True
                elif answer == 'no':
                    f.close()
                    return False
                else:
                    f.write("Please type 'yes' or 'no': ")
        return d.addCallback(body)


    def warn(self, text):
        """
        Notify the user (non-interactively) of the provided text, by writing it
        to the console.
        """
        try:
            f = self.opener()
            f.write(text)
            f.close()
        except:
            log.err()
