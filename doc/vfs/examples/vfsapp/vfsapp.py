
from twisted.application import service, internet

from twisted.cred import portal, checkers, credentials

from twisted.conch.ssh import factory, keys, common
from twisted.conch.interfaces import IConchUser

import twisted.protocols.ftp

from twisted.vfs.backends import inmem
from twisted.vfs.adapters import sftp, ftp
from twisted.vfs import ivfs, pathutils

import zope.interface


class Realm:
    zope.interface.implements(portal.IRealm)

    def __init__(self, vfsRoot):
        self.vfsRoot = vfsRoot

    def requestAvatar(self, username, mind, *interfaces):

        for interface in interfaces:

            # sftp user
            if interface is IConchUser:
                user = sftp.VFSConchUser(username, self.vfsRoot)
                return interface, user, user.logout

            # ftp user
            elif interface is twisted.protocols.ftp.IFTPShell:
                return (
                    interface,
                    twisted.protocols.ftp.IFTPShell(pathutils.FileSystem(self.vfsRoot)),
                    None
                )

        raise NotImplementedError("Can't support that interface.")


def createVFSApplication(vfsRoot):

    application = service.Application('FAKESFTP')

    p = portal.Portal(Realm(vfsRoot))
    p.registerChecker(
        checkers.InMemoryUsernamePasswordDatabaseDontUse(admin='admin'))
    p.registerChecker(checkers.AllowAnonymousAccess(), credentials.IAnonymous)

    # sftp
    # http://igloo.its.unimelb.edu.au/Webmail/tips/msg00495.html
    # ssh-keygen -q -b 1024 -t dsa -f ssh_host_dsa_key
    pubkey = keys.Key.fromFile(
        '../sshkeys/ssh_host_dsa_key.pub').blob()
    privkey = keys.Key.fromFile(
        '../sshkeys/ssh_host_dsa_key').keyObject

    class SSHFactory(factory.SSHFactory):
        publicKeys = {common.getNS(pubkey)[0]: pubkey}
        privateKeys = {keys.objectType(privkey): privkey}

    sftpf = SSHFactory()
    sftpf.portal = p

    internet.TCPServer(
        int( 2222 ), sftpf,
    ).setServiceParent(application)

    # ftp
    f = twisted.protocols.ftp.FTPFactory()
    f.portal = p
    f.protocol = twisted.protocols.ftp.FTP
    internet.TCPServer(
        2221, f
    ).setServiceParent(application)

    return application
