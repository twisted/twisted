
from crypt import crypt

import zope.interface

from twisted.cred import checkers, credentials, portal, error
from twisted.conch.interfaces import IConchUser

from twisted.vfs.adapters import sftp
from twisted.vfs.backends import osfs, adhoc

class WelshChecker:
    zope.interface.implements(checkers.ICredentialsChecker)
    credentialInterfaces = (credentials.IUsernamePassword,)

    def __init__(self, file):
        self.file = file

    def requestAvatarId(self, credentials):
        users = [
            line[:-1].split(':') for
            line in open(self.file, 'r').readlines() ]

        for user, passwd in users:
            if credentials.username == user:
                if crypt(credentials.password, passwd[:2]) == passwd:
                    return credentials.username
                else:
                    raise error.UnauthorizedLogin()

        raise KeyError(credentials.username)


class WelshRealm:
    zope.interface.implements(portal.IRealm)

    def __init__(self, file):
        self.file = file

    def requestAvatar(self, username, mind, *interfaces):
        for interface in interfaces:
            if interface is IConchUser:
                root = adhoc.AdhocDirectory()
                shares = [
                    line[:-1].split(':') for
                    line in open(self.file, 'r').readlines() ]

                for share, uid, gid, dirmode, filemode, path, users in shares:
                    if username in users.split(','):
                        if dirmode == '': dirmode = None
                        if filemode == '': filemode = None
                        node = osfs.OSDirectory(path)
                        node = osfs.ForceCreateModeProxy(node, dirmode, filemode)
                        node = osfs.SetUIDProxy(node, int(uid), int(gid))
                        root.putChild(share, node)

                user = sftp.VFSConchUser(username, root)
                return interface, user, user.logout

        raise NotImplementedError("Can't support that interface.")

