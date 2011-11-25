# -*- test-case-name: twisted.conch.test.test_checkers -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Provide L{ICredentialsChecker} implementations to be used in Conch protocols.
"""

import os, base64, binascii, errno
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

from zope.interface import implements, providedBy

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

