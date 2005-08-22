
from twisted.application import service, internet

from twisted.cred import portal, checkers, credentials

from twisted.conch.ssh import factory, keys, common
from twisted.conch.interfaces import IConchUser

from twisted.web import server

import twisted.protocols.ftp

from nevow import inevow, rend, tags, guard, loaders, appserver

from twisted.vfs.backends import inmem
from twisted.vfs.adapters import sftp, web, ftp #, dav
from twisted.vfs import ivfs, pathutils

import zope.interface

class NotLoggedIn(rend.Page):
    """The resource that is returned when you are not logged in"""
    addSlash = False
    docFactory = loaders.stan(
    tags.html[
        tags.head[tags.title["Not Logged In"]],
        tags.body[
            tags.form(action=guard.LOGIN_AVATAR, method='post')[
                tags.table[
                    tags.tr[
                        tags.td[ "Username:" ],
                        tags.td[ tags.input(type='text',name='username') ],
                    ],
                    tags.tr[
                        tags.td[ "Password:" ],
                        tags.td[ tags.input(type='password',name='password') ],
                    ]
                ],
                tags.input(type='submit'),
                tags.p,
            ]
        ]
    ]
)


class SiteResource(rend.Page):
    def locateChild(self, ctx, segments):
        ctx.remember(self, inevow.ICanHandleNotFound)
        return self.original.locateChild(ctx, segments)

    def willHandle_notFound(self, request):
        return True

    def renderHTTP_notFound(self, ctx):
        return NotLoggedIn().renderHTTP(ctx)
    

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

            # web user
            elif interface is inevow.IResource:
                if username is checkers.ANONYMOUS:
                    resc = NotLoggedIn()
                    resc.realm = self
                    return (inevow.IResource, resc, lambda : None)
                else:
                    resc = self.vfsRoot
                    resc.realm = self
                    return (inevow.IResource, resc, lambda : None)

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

    pubkey = keys.getPublicKeyString(
        '../sshkeys/ssh_host_dsa_key.pub')
    privkey = keys.getPrivateKeyObject(
        '../sshkeys/ssh_host_dsa_key')

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

    # dav
##     internet.TCPServer(
##         int( 2280 ), server.Site(dav.DavResource(vfsRoot))
##     ).setServiceParent(application)

    # web
    internet.TCPServer(
        8080, appserver.NevowSite(SiteResource(guard.SessionWrapper(p)))
    ).setServiceParent(application)

    return application
