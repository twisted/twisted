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



def keysFromStrings(keyStrings, keyType="public_openssh"):
    """
    Turns an iterable of strings into a generator of keys.

    @param keyStrings: an iterable of strings containing keys of C{keyType}
    @type filepaths: C{iterable} of C{str}

    @param keyType: The type of key is represented by the keys in C{filepaths}.
        By default, it is "public_openssh".  If C{None} is passed, the type
        will be guessed.
    @type keyType: C{str} or C{None}

    @return: a C{generator} object whose values L{twisted.conch.ssh.keys.Key}
        objects corresponding to the key
    """
    return (keys.Key.fromString(keyString, type=keyType) for
            keyString in keyStrings)



def keysFromFilepaths(filepaths, keyType="public_openssh", ownerIds=None):
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
            return filepath.getContents()
        except IOError as e:
            if ownerIds is not None and e.errno == errno.EACCES:
                return runAsEffectiveUser(ownerIds[0], ownerIds[1],
                                          filepath.getContents)
            else:
                raise

    return keysFromStrings((_tryGetContent(fp) for fp in filepaths
                            if fp.exists()), keyType)



def authenticateAndVerifySSHKey(authorizedKeys, credentials):
    """
    Authenticates the credentials against a bunch of authorized keys,
    and then if the key is valid, verifies the key signature.

    This is important because in the SSH protocol (RFC 4252, Section 7), the
    public key blob is sent along with other info first.  The server then must
    determine whether this blob is a valid authenticator for the user.  If
    no signature is provided, C{SSH_MSG_USERAUTH_PK_OK} is sent back to the
    client to indicate that the key is valid, but not signed.

    The client may then send the signed key again, and if the key is a valid
    authenticator and it is correctly signed, then if this is the end of
    the authentications required by the server then the server must send a
    C{SSH_MSG_USERAUTH_SUCCESS}.

    The intent is for this method to be called for both the initial non-signed
    check and for the signed check.

    If the key is unsigned, then L{error.validPublicKey} is raised, which
    indicates that a C{SSH_MSG_USERAUTH_PK_OK} should be sent.


    @param credentials: The credentials offered by the user.
    @type credentials: L{ISSHPrivateKey} provider

    @param authorizedKeys: a generator of key objects that are valid
        authenticators for the user.  The functions L{keysFromStrings} or
        L{keysFromFilepaths} can be used to generate this parameter.
        A generator is required so that, in the case of files, no more file
        access than necessary needs to occur.
    @type authorizedKeys: C{generator} of L{twisted.conch.ssh.keys.Key}

    @raise UnauthorizedLogin: if the user provides invalid credentials

    @raise ValidPublicKey: if the key is a a valid authenticator for the user
        (matches one of the authorized keys) but the credentials do not
        include a signature. See L{error.ValidPublicKey} for more information.

    @return: the username in the credentials if verification is successful -
        if unsuccessful in any way an exception will be raised
    """
    publicKey = keys.Key.fromString(credentials.blob)
    # because the argument to any is a generator, any only evaluates enough
    # items to get a True and no more
    if not any((key == publicKey for key in authorizedKeys)):
        raise UnauthorizedLogin("invalid key")

    if not credentials.signature:
        raise error.ValidPublicKey()

    verified = False
    try:
        if publicKey.verify(credentials.signature, credentials.sigData):
            return credentials.username
    except Exception as e:  # any error should be treated as a failed login
        log.err(e, 'error while verifying key')
        raise UnauthorizedLogin('error while verifying key')

    if not verified:
        raise UnauthorizedLogin("unable to verify key")



@implementer(ICredentialsChecker)
class SSHPublicKeyDatabase:
    """
    Checker that authenticates SSH public keys, based on public keys listed in
    authorized_keys and authorized_keys2 files in user .ssh/ directories.
    """
    credentialInterfaces = (ISSHPrivateKey,)

    _userdb = pwd

    def requestAvatarId(self, credentials):
        def _getAuthorizedKeys():
            ouid, ogid = self._userdb.getpwnam(credentials.username)[2:4]
            return keysFromFilepaths(self.getAuthorizedKeysFiles(credentials),
                                     ownerIds=(ouid, ogid))

        d = defer.maybeDeferred(_getAuthorizedKeys)
        d.addCallback(authenticateAndVerifySSHKey, credentials)
        d.addErrback(self._ebRequestAvatarId)
        return d


    def getAuthorizedKeysFiles(self, credentials):
        """
        Return a list of L{FilePath} instances for I{authorized_keys} files
        which might contain information about authorized keys for the given
        credentials.

        On OpenSSH servers, the default location of the file containing the
        list of authorized public keys is
        U{$HOME/.ssh/authorized_keys}.
        <http://www.openbsd.org/cgi-bin/man.cgi?query=sshd_config>

        I{$HOME/.ssh/authorized_keys2} is also returned, though it has been
        U{deprecated by OpenSSH since
        2001 <http://marc.info/?m=100508718416162>}.

        @return: A list of L{FilePath} instances to files with the authorized
            keys.
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
            log.err(f, 'normalized error')
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

