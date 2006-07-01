import os, base64, binascii
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
    import pamauth
except ImportError:
    pamauth = None

from twisted.conch import error
from twisted.conch.ssh import keys
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernamePassword, ISSHPrivateKey, IPluggableAuthenticationModules
from twisted.cred.error import UnauthorizedLogin, UnhandledCredentials
from twisted.internet import defer
from twisted.python import failure, reflect, log
from zope import interface

def verifyCryptedPassword(crypted, pw):
    if crypted[0] == '$': # md5_crypt encrypted
        salt = '$1$' + crypted.split('$')[2]
    else:
        salt = crypted[:2]
    return crypt.crypt(pw, salt) == crypted

class UNIXPasswordDatabase:
    credentialInterfaces = IUsernamePassword,
    interface.implements(ICredentialsChecker)

    def requestAvatarId(self, credentials):
        if pwd:
            try:
                cryptedPass = pwd.getpwnam(credentials.username)[1]
            except KeyError:
                return defer.fail(UnauthorizedLogin())
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
                return defer.fail(UnauthorizedLogin())
            os.setegid(gid)
            os.seteuid(uid)
            if verifyCryptedPassword(shadowPass, credentials.password):
                return defer.succeed(credentials.username)
            return defer.fail(UnauthorizedLogin())
        
        return defer.fail(UnauthorizedLogin())


class SSHPublicKeyDatabase:
    credentialInterfaces = ISSHPrivateKey,
    interface.implements(ICredentialsChecker)

    def requestAvatarId(self, credentials):
        d = defer.maybeDeferred(self.checkKey, credentials)
        d.addCallback(self._cbRequestAvatarId, credentials)
        d.addErrback(self._ebRequestAvatarId)
        return d

    def _cbRequestAvatarId(self, validKey, credentials):
        if not validKey:
            return failure.Failure(UnauthorizedLogin())
        if not credentials.signature:
            return failure.Failure(error.ValidPublicKey())
        else:
            try:
                pubKey = keys.getPublicKeyObject(data = credentials.blob)
                if keys.verifySignature(pubKey, credentials.signature,
                                        credentials.sigData):
                    return credentials.username
            except: # any error should be treated as a failed login
                f = failure.Failure()
                log.err()
                return f
        return failure.Failure(UnauthorizedLogin())

    def checkKey(self, credentials):
        sshDir = os.path.expanduser('~%s/.ssh/' % credentials.username)
        if sshDir.startswith('~'): # didn't expand
            return 0
        uid, gid = os.geteuid(), os.getegid()
        ouid, ogid = pwd.getpwnam(credentials.username)[2:4]
        os.setegid(0)
        os.seteuid(0)
        os.setegid(ogid)
        os.seteuid(ouid)
        for name in ['authorized_keys2', 'authorized_keys']:
            if not os.path.exists(sshDir+name):
                continue
            lines = open(sshDir+name).xreadlines()
            os.setegid(0)
            os.seteuid(0)
            os.setegid(gid)
            os.seteuid(uid)
            for l in lines:
                l2 = l.split()
                if len(l2) < 2:
                    continue
                try:
                    if base64.decodestring(l2[1]) == credentials.blob:
                        return 1
                except binascii.Error:
                    continue
        return 0

    def _ebRequestAvatarId(self, f):
        if not f.check(UnauthorizedLogin, error.ValidPublicKey):
            log.msg(f)
            return failure.Failure(UnauthorizedLogin())
        return f


class SSHProtocolChecker:
    interface.implements(ICredentialsChecker)

    checkers = {}

    successfulCredentials = {}

    def get_credentialInterfaces(self):
        return self.checkers.keys()

    credentialInterfaces = property(get_credentialInterfaces)

    def registerChecker(self, checker, *credentialInterfaces):
        if not credentialInterfaces:
            credentialInterfaces = checker.credentialInterfaces
        for credentialInterface in credentialInterfaces:
            self.checkers[credentialInterface] = checker

    def requestAvatarId(self, credentials):
        ifac = interface.providedBy(credentials)
        for i in ifac:
            c = self.checkers.get(i)
            if c is not None:
                return c.requestAvatarId(credentials).addCallback(
                    self._cbGoodAuthentication, credentials)
        return defer.fail(UnhandledCredentials("No checker for %s" % \
            ', '.join(map(reflect.qal, ifac))))
    
    def _cbGoodAuthentication(self, avatarId, credentials):
        if avatarId not in self.successfulCredentials:
            self.successfulCredentials[avatarId] = []
        self.successfulCredentials[avatarId].append(credentials)
        if self.areDone(avatarId):
            del self.successfulCredentials[avatarId]
            return avatarId
        else:
            raise error.NotEnoughAuthentication()

    def areDone(self, avatarId):
        """Override to determine if the authentication is finished for a given
        avatarId.
        """
        return 1

