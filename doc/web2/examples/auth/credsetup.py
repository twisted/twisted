from zope.interface import Interface, implements
from twisted.cred import portal

class IHTTPUser(Interface):
    pass

class HTTPUser(object):
    implements(IHTTPUser)

class HTTPAuthRealm(object):
    implements(portal.IRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IHTTPUser in interfaces:
            return IHTTPUser, HTTPUser()

        raise NotImplementedError("Only IHTTPUser interface is supported")

