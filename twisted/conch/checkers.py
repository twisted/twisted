# -*- test-case-name: twisted.conch.test.test_checkers -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Provide L{ICredentialsChecker} implementations to be used in Conch protocols.
"""

import base64
import binascii
import errno
import os
try:
    import pwd
except ImportError:
    pwd = None
else:
    import crypt

try:
    # Python 2.5 got spwd to interface with shadow passwords
    import spwd
except ImportError:
    spwd = None
    try:
        import shadow
    except ImportError:
        shadow = None
else:
    shadow = None

try:
    from twisted.cred import pamauth
except ImportError:
    pamauth = None

from zope.interface import implements, implementer, providedBy

from twisted.conch import error
from twisted.conch.ssh import keys
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernamePassword, ISSHPrivateKey
from twisted.cred.error import UnauthorizedLogin, UnhandledCredentials
from twisted.internet import defer
from twisted.python import failure, reflect, log
from twisted.python.util import runAsEffectiveUser
from twisted.python.filepath import FilePath



def verifyCryptedPassword(crypted, pw):
    return crypt.crypt(pw, crypted) == crypted



def _pwdGetByName(username):
    """
    Look up a user in the /etc/passwd database using the pwd module.  If the
    pwd module is not available, return None.

    @param username: the username of the user to return the passwd database
        information for.
    """
    if pwd is None:
        return None
    return pwd.getpwnam(username)



def _shadowGetByName(username):
    """
    Look up a user in the /etc/shadow database using the spwd or shadow
    modules.  If neither module is available, return None.

    @param username: the username of the user to return the shadow database
        information for.
    """
    if spwd is not None:
        f = spwd.getspnam
    elif shadow is not None:
        f = shadow.getspnam
    else:
        return None
    return runAsEffectiveUser(0, 0, f, username)



class UNIXPasswordDatabase:
    """
    A checker which validates users out of the UNIX password databases, or
    databases of a compatible format.

    @ivar _getByNameFunctions: a C{list} of functions which are called in order
        to valid a user.  The default value is such that the /etc/passwd
        database will be tried first, followed by the /etc/shadow database.
    """
    credentialInterfaces = IUsernamePassword,
    implements(ICredentialsChecker)


    def __init__(self, getByNameFunctions=None):
        if getByNameFunctions is None:
            getByNameFunctions = [_pwdGetByName, _shadowGetByName]
        self._getByNameFunctions = getByNameFunctions


    def requestAvatarId(self, credentials):
        for func in self._getByNameFunctions:
            try:
                pwnam = func(credentials.username)
            except KeyError:
                return defer.fail(UnauthorizedLogin("invalid username"))
            else:
                if pwnam is not None:
                    crypted = pwnam[1]
                    if crypted == '':
                        continue
                    if verifyCryptedPassword(crypted, credentials.password):
                        return defer.succeed(credentials.username)
        # fallback
        return defer.fail(UnauthorizedLogin("unable to verify password"))



def publicKeysFromStrings(keyStrings, keyType="public_openssh"):
    """
    Turns an iterable of strings into a generator of keys.  Each string may
    contain more than one key, but each key should be on a separate line.

    @param keyStrings: an iterable of strings containing keys of C{keyType}
    @type filepaths: C{iterable} of C{str}

    @param keyType: The type of key is represented by the keys in C{filepaths}.
        By default, it is "public_openssh".  If C{None} is passed, the type
        will be guessed.
    @type keyType: C{str} or C{None}

    @return: a C{generator} object whose values L{twisted.conch.ssh.keys.Key}
        objects corresponding to the key
    """
    for keyString in keyStrings:
        allKeys = [line for line in keyString.split('\n') if line.strip()]
        for oneKey in allKeys:
            yield keys.Key.fromString(oneKey, type=keyType)



def publicKeysFromFilepaths(filepaths, keyType="public_openssh",
                            ownerIds=None):
    """
    Turns an iterable of absolute filenames (the full path) into a generator
    of keys.

    @param filenames: an iterable of C{FilePaths} corresponding to files
        containing keys of C{keyType}
    @type filenames: C{iterable} of L{twisted.python.filepath.FilePath}

    @param keyType: The type of key is represented by the keys in C{filepaths}.
        By default, it is "public_openssh".  If C{None} is passed, the type
        will be guessed.
    @type keyType: C{str} or C{None}

    @param ownerIds: The uid and gid of the user to attempt to read the
        filepaths as, there is a permissions error attempting to access the
        contents of the files.  If not provided, no attempt to re-read the
        content is made.
    @type ownerIds: C{tuple} of C{(uid, gid)}

    @return: a C{generator} object whose values L{twisted.conch.ssh.keys.Key}
        objects corresponding to the key
    """
    def _tryGetContent(filepath):
        try:
            return filepath.getContent()
        except IOError as e:
            if ownerIds is not None and e.errno == errno.EACCES:
                return runAsEffectiveUser(ownerIds[0], ownerIds[1],
                                          filepath.getContent)
            else:
                raise

    return publicKeysFromStrings((_tryGetContent(fp) for fp in filepaths
                                  if fp.exists()), keyType)



@implementer(ICredentialsChecker)
class SSHPublicKeyChecker(object):
    """
    Checker that authenticates the credentials against a bunch of authorized
    keys.  The order of operations is that it authenticates, and then, if the
    key is valid, it verifies the key signature, and if the signature is valid
    it returns the avatar Id.

    In the SSH protocol (RFC 4252, Section 7), the public key blob is sent
    along with other info first.  The server then must determine whether this
    blob is a valid authenticator for the user.  If no signature is provided,
    C{SSH_MSG_USERAUTH_PK_OK} is sent back to the client to indicate that the
    key is valid, but not signed.

    The client may then send the signed key again, and if the key is a valid
    authenticator and it is correctly signed, then if this is the end of
    the authentications required by the server then the server must send a
    C{SSH_MSG_USERAUTH_SUCCESS}.

    The intent is for L{requestAvatarId} to be called for both the initial
    non-signed check and for the signed check.

    @ivar authorizedKeyProducer: a callable that returns a C{iterable}
        (preferably a C{generator}) of L{twisted.conch.ssh.keys.Key} objects
        that are valid authenticators for the user.

        The functions L{publicKeysFromStrings} or L{publicKeysFromFilepaths}
        can be used to produce said iterable.

        A generator is preferred so that, in the case of files, no more file
        access than necessary needs to occur.

    @type authorizedKeys: C{callable} that takes the credentials (a
        C{ISSHPrivateKey}) as an argument.
    """
    credentialInterfaces = (ISSHPrivateKey,)


    def __init__(self, authorizedKeyProducer):
        self.authorizedKeyProducer = authorizedKeyProducer


    def requestAvatarId(self, credentials):
        """
        Authenticates and verifies the signature of the credentials

        @param credentials: The credentials offered by the user.
        @type credentials: L{ISSHPrivateKey} provider

        @raise UnauthorizedLogin: if the user provides invalid credentials

        @raise ValidPublicKey: if the key is a a valid authenticator for the
            user (matches one of the authorized keys) but the credentials do
            not include a signature. Indicates that a
            C{SSH_MSG_USERAUTH_PK_OK} should be sent.  See
            L{error.ValidPublicKey} for more information.

        @return: the username in the credentials if verification is successful.
            If unsuccessful in any way an exception will be raised
        """
        d = defer.maybeDeferred(self.authorizedKeyProducer, credentials)
        d.addCallback(self._authenticateAndVerifySSHKey, credentials)
        d.addErrback(self._normalizeErrors)
        return d


    def _authenticateAndVerifySSHKey(self, authorizedKeys, credentials):
        """
        What actually authenticates and verifies the signature.
        """
        publicKey = keys.Key.fromString(credentials.blob)

        if not any((publicKey == key for key in authorizedKeys)):
            raise UnauthorizedLogin("invalid key")

        if not credentials.signature:
            raise error.ValidPublicKey()

        if publicKey.verify(credentials.signature, credentials.sigData):
            return credentials.username

        raise UnauthorizedLogin("unable to verify key")


    def _normalizeErrors(self, f):
        """
        Obscure non-UnauthorizedLogin errors (of which L{error.ValidPublicKey}
        is a subclass).
        """
        if not f.check(UnauthorizedLogin):
            log.err(f, 'unknown/unexpected error')
            raise UnauthorizedLogin("unable to get avatar id")
        return f


def getDotSSHAuthorizedKeys(credentials):
    """
    On OpenSSH servers, the default location of the file containing the
    list of authorized public keys is
    U{$HOME/.ssh/authorized_keys<http://www.openbsd.org/cgi-bin/man.cgi?query=sshd_config>}.

    I{$HOME/.ssh/authorized_keys2} is also returned, though it has been
    U{deprecated by OpenSSH since
    2001<http://marc.info/?m=100508718416162>}.

    @return: a C{generator}) of L{twisted.conch.ssh.keys.Key} corresponding to
        authorized keys in U{$HOME/.ssh/authorized_keys} and
        U{$HOME/.ssh/authorized_keys}
    """



class SSHPublicKeyDatabase:
    """
    Checker that authenticates SSH public keys, based on public keys listed in
    authorized_keys and authorized_keys2 files in user .ssh/ directories.
    """
    implements(ICredentialsChecker)

    credentialInterfaces = (ISSHPrivateKey,)

    _userdb = pwd

    def requestAvatarId(self, credentials):
        d = defer.maybeDeferred(self.checkKey, credentials)
        d.addCallback(self._cbRequestAvatarId, credentials)
        d.addErrback(self._ebRequestAvatarId)
        return d

    def _cbRequestAvatarId(self, validKey, credentials):
        """
        Check whether the credentials themselves are valid, now that we know
        if the key matches the user.

        @param validKey: A boolean indicating whether or not the public key
            matches a key in the user's authorized_keys file.

        @param credentials: The credentials offered by the user.
        @type credentials: L{ISSHPrivateKey} provider

        @raise UnauthorizedLogin: (as a failure) if the key does not match the
            user in C{credentials}. Also raised if the user provides an invalid
            signature.

        @raise ValidPublicKey: (as a failure) if the key matches the user but
            the credentials do not include a signature. See
            L{error.ValidPublicKey} for more information.

        @return: The user's username, if authentication was successful.
        """
        if not validKey:
            return failure.Failure(UnauthorizedLogin("invalid key"))
        if not credentials.signature:
            return failure.Failure(error.ValidPublicKey())
        else:
            try:
                pubKey = keys.Key.fromString(credentials.blob)
                if pubKey.verify(credentials.signature, credentials.sigData):
                    return credentials.username
            except: # any error should be treated as a failed login
                log.err()
                return failure.Failure(UnauthorizedLogin('error while verifying key'))
        return failure.Failure(UnauthorizedLogin("unable to verify key"))


    def getAuthorizedKeysFiles(self, credentials):
        """
        Return a list of L{FilePath} instances for I{authorized_keys} files
        which might contain information about authorized keys for the given
        credentials.

        On OpenSSH servers, the default location of the file containing the
        list of authorized public keys is
        U{$HOME/.ssh/authorized_keys<http://www.openbsd.org/cgi-bin/man.cgi?query=sshd_config>}.

        I{$HOME/.ssh/authorized_keys2} is also returned, though it has been
        U{deprecated by OpenSSH since
        2001<http://marc.info/?m=100508718416162>}.

        @return: A list of L{FilePath} instances to files with the authorized keys.
        """
        pwent = self._userdb.getpwnam(credentials.username)
        root = FilePath(pwent.pw_dir).child('.ssh')
        files = ['authorized_keys', 'authorized_keys2']
        return [root.child(f) for f in files]


    def checkKey(self, credentials):
        """
        Retrieve files containing authorized keys and check against user
        credentials.
        """
        uid, gid = os.geteuid(), os.getegid()
        ouid, ogid = self._userdb.getpwnam(credentials.username)[2:4]
        for filepath in self.getAuthorizedKeysFiles(credentials):
            if not filepath.exists():
                continue
            try:
                lines = filepath.open()
            except IOError, e:
                if e.errno == errno.EACCES:
                    lines = runAsEffectiveUser(ouid, ogid, filepath.open)
                else:
                    raise
            for l in lines:
                l2 = l.split()
                if len(l2) < 2:
                    continue
                try:
                    if base64.decodestring(l2[1]) == credentials.blob:
                        return True
                except binascii.Error:
                    continue
        return False


    def _ebRequestAvatarId(self, f):
        if not f.check(UnauthorizedLogin):
            log.msg(f)
            return failure.Failure(UnauthorizedLogin("unable to get avatar id"))
        return f



class SSHProtocolChecker:
    """
    SSHProtocolChecker is a checker that requires multiple authentications
    to succeed.  To add a checker, call my registerChecker method with
    the checker and the interface.

    After each successful authenticate, I call my areDone method with the
    avatar id.  To get a list of the successful credentials for an avatar id,
    use C{SSHProcotolChecker.successfulCredentials[avatarId]}.  If L{areDone}
    returns True, the authentication has succeeded.
    """

    implements(ICredentialsChecker)

    def __init__(self):
        self.checkers = {}
        self.successfulCredentials = {}

    def get_credentialInterfaces(self):
        return self.checkers.keys()

    credentialInterfaces = property(get_credentialInterfaces)

    def registerChecker(self, checker, *credentialInterfaces):
        if not credentialInterfaces:
            credentialInterfaces = checker.credentialInterfaces
        for credentialInterface in credentialInterfaces:
            self.checkers[credentialInterface] = checker

    def requestAvatarId(self, credentials):
        """
        Part of the L{ICredentialsChecker} interface.  Called by a portal with
        some credentials to check if they'll authenticate a user.  We check the
        interfaces that the credentials provide against our list of acceptable
        checkers.  If one of them matches, we ask that checker to verify the
        credentials.  If they're valid, we call our L{_cbGoodAuthentication}
        method to continue.

        @param credentials: the credentials the L{Portal} wants us to verify
        """
        ifac = providedBy(credentials)
        for i in ifac:
            c = self.checkers.get(i)
            if c is not None:
                d = defer.maybeDeferred(c.requestAvatarId, credentials)
                return d.addCallback(self._cbGoodAuthentication,
                        credentials)
        return defer.fail(UnhandledCredentials("No checker for %s" % \
            ', '.join(map(reflect.qual, ifac))))

    def _cbGoodAuthentication(self, avatarId, credentials):
        """
        Called if a checker has verified the credentials.  We call our
        L{areDone} method to see if the whole of the successful authentications
        are enough.  If they are, we return the avatar ID returned by the first
        checker.
        """
        if avatarId not in self.successfulCredentials:
            self.successfulCredentials[avatarId] = []
        self.successfulCredentials[avatarId].append(credentials)
        if self.areDone(avatarId):
            del self.successfulCredentials[avatarId]
            return avatarId
        else:
            raise error.NotEnoughAuthentication()

    def areDone(self, avatarId):
        """
        Override to determine if the authentication is finished for a given
        avatarId.

        @param avatarId: the avatar returned by the first checker.  For
            this checker to function correctly, all the checkers must
            return the same avatar ID.
        """
        return True

