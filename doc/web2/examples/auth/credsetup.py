from zope.interface import Interface, implements
from twisted.cred import portal
from twisted.web2.auth.interfaces import IHTTPUser

class HTTPUser(object):
    """
    A user that authenticated over HTTP Auth.
    """
    implements(IHTTPUser)

    username = None

    def __init__(self, username):
        """
        @param username: The str username sent as part of the HTTP auth
            response.
        """
        self.username = username


class HTTPAuthRealm(object):
    implements(portal.IRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IHTTPUser in interfaces:
            return IHTTPUser, HTTPUser(avatarId)

        raise NotImplementedError("Only IHTTPUser interface is supported")

