import os, base64, binascii
try:
    import pwd
except ImportError:
    pwd = None
else:
    import crypt

try:
    # get these from http://www.twistedmatrix.com/users/z3p/files/pyshadow-0.1.tar.gz
    import md5_crypt
    import shadow
except:
    md5_crypt = None
    shadow = None

try:
    import pamauth
except ImportError:
    pamauth = None

from twisted.conch import error
from twisted.conch.ssh import keys
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernamePassword
from twisted.cred.error import UnauthorizedLogin, UnhandledCredentials
from twisted.internet import defer
from twisted.python import components, failure, reflect
from credentials import ISSHPrivateKey, IPluggableAuthenticationModules

def verifyCryptedPassword(crypted, pw):
    if crypted[0] == '$': # md5_crypt encrypted
        if not md5_crypt: return 0
        salt = crypted.split('$')[2]
        return md5_crypt.md5_crypt(pw, salt) == crypted
    if not pwd:
        return 0
    return crypt.crypt(pw, crypted[:2]) == crypted

class UNIXPasswordDatabase:
    credentialInterfaces = IUsernamePassword,
    __implements__ = ICredentialsChecker

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
    __implements__ = ICredentialsChecker

    def requestAvatarId(self, credentials):
        if not self.checkKey(credentials):
            return defer.fail(UnauthorizedLogin())
        if not credentials.signature:
            return defer.fail(error.ValidPublicKey())
        else:
            try:
                pubKey = keys.getPublicKeyObject(data = credentials.blob)
                if keys.verifySignature(pubKey, credentials.signature,
                                        credentials.sigData):
                    return defer.succeed(credentials.username)
            except:
                pass
        return defer.fail(UnauthorizedLogin())

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

class PluggableAuthenticationModulesChecker:
    __implements__ = ICredentialsChecker

    credentialInterfaces = IPluggableAuthenticationModules,

    def requestAvatarId(self, credentials):
        if not pamauth:
            return defer.fail(UnauthorizedLogin())
        d = pamauth.pamAuthenticate('ssh', credentials.username,
                                       credentials.pamConversion)
        d.addCallback(lambda x: credentials.username)
        return d

class SSHProtocolChecker:
    __implements__ = ICredentialsChecker

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
        ifac = components.getInterfaces(credentials)
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
