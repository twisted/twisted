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
    # get this from http://www.twistedmatrix.com/users/z3p/files/pyshadow-0.2.tar.gz
    import shadow
except:
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
    if crypted[0] == '$': # md5_crypt encrypted
        salt = '$1$' + crypted.split('$')[2]
    else:
        salt = crypted[:2]
    return crypt.crypt(pw, salt) == crypted

class UNIXPasswordDatabase:
    credentialInterfaces = IUsernamePassword,
    implements(ICredentialsChecker)

    def requestAvatarId(self, credentials):
        if pwd:
            try:
                cryptedPass = pwd.getpwnam(credentials.username)[1]
            except KeyError:
                return defer.fail(UnauthorizedLogin("invalid username"))
            else:
                if cryptedPass not in ['*', 'x'] and \
                    verifyCryptedPassword(cryptedPass, credentials.password):
                    return defer.succeed(credentials.username)
        if shadow:
            gid = os.getegid()
            uid = os.geteuid()
            os.setegid(0)
            os.seteuid(0)
            try:
                shadowPass = shadow.getspnam(credentials.username)[1]
            except KeyError:
                os.setegid(gid)
                os.seteuid(uid)
                return defer.fail(UnauthorizedLogin("invalid username"))
            os.setegid(gid)
            os.seteuid(uid)
            if verifyCryptedPassword(shadowPass, credentials.password):
                return defer.succeed(credentials.username)
            return defer.fail(UnauthorizedLogin("invalid password"))

        return defer.fail(UnauthorizedLogin("unable to verify password"))


class SSHPublicKeyDatabase:
    """
    Checker that authenticates SSH public keys, based on public keys listed in
    authorized_keys and authorized_keys2 files in user .ssh/ directories.
    """

    credentialInterfaces = ISSHPrivateKey,
    implements(ICredentialsChecker)

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
        pwent = pwd.getpwnam(credentials.username)
        root = FilePath(pwent.pw_dir).child('.ssh')
        files = ['authorized_keys', 'authorized_keys2']
        return [root.child(f) for f in files]


    def checkKey(self, credentials):
        """
        Retrieve files containing authorized keys and check against user
        credentials.
        """
        uid, gid = os.geteuid(), os.getegid()
        ouid, ogid = pwd.getpwnam(credentials.username)[2:4]
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

