
"""newcred support for twisted.manhole."""

from twisted.application.service import Service
from twisted.spread import pb
from twisted.cred import portal
from twisted.cred import error as credError
from twisted.python import components

from twisted.manhole.service import Perspective

class Realm(components.Adapter):
    __implements__ = portal.IRealm,
    perspectiveClass = Perspective

    def __init__(self, original):
        components.Adapter.__init__(self, original)
        self.perspectives = {}

    def requestAvatar(self, avatarId, mind, *interfaces):
        if pb.IPerspective not in interfaces:
            raise credError.InterfaceNotSupported

        # TODO: Should this do getAdapter before returning?
        if avatarId in self.perspectives:
            p = self.perspectives[avatarId]
            p.setService(self.original)
        else:
            p = self.perspectiveClass()
            self.perspectives[avatarId] = p
        p.attached(mind, avatarId)
        logout = lambda : p.detached(mind, avatarId)
        return (pb.IPerspective, p, logout)

class Service(Service):
    name = "twisted.manhole"

    welcomeMessage = (
        "\nHello %(you)s, welcome to %(serviceName)s "
        "in %(app)s on %(host)s.\n"
        "%(longversion)s.\n\n")

    def __init__(self):
        import sys
        self.namespace = {
            # Specify __name__ so we don't inherit it from __builtins__.
            # It seems to have the potential for breaking imports, but if we
            # put enough __s around it things seem to work.
            '__name__': '__manhole%x__' % (id(self),),
            # sys, so sys.modules will be readily available
            'sys': sys
            }

    def __getstate__(self):
        """This returns the persistent state of this shell factory.
        """
        dict = pb.Service.__getstate__(self)
        ns = dict['namespace'].copy()
        dict['namespace'] = ns
        if ns.has_key('__builtins__'):
            del ns['__builtins__']
        return dict

    def __str__(self):
        s = "<%s %r at 0x%x with parent %s>" % (self.__class__, self.name,
                                                id(self), self.parent)
        return s


components.registerAdapter(Realm, Service, portal.IRealm)
