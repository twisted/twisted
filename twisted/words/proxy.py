# -*- test-case-name: twisted.words.test.test_proxy -*-

"""
AMP <-> Anything chat proxy

@author: L{Jean-Paul Calderone<exarkun@divmod.com>}
@author: L{Chrisopher Armstrong<radix@twistedmatrix.com>}

@stability: unstable
"""

__metaclass__ = type

from zope.interface import implements, Interface

from twisted.cred.error import UnauthorizedLogin



class IProxyUser(Interface):
    pass



class CertificateChecker:
    def requestAvatarId(self, credentials):
        """
        SSL sucks.

        By this point, the client certificate has already been verified; if
        it's got here, just return an avatar ID.
        """
        return credentials.digest()



class ProxyUser:
    implements(IProxyUser)



class Realm:
    def requestAvatar(self, avatarId, mind, iface):
        return iface, ProxyUser(), lambda: None



class ProxyServer:

    avatar = None


    def login(self):
        return {'tls_started': self._startedTLS}


    def _startedTLS(self):
        pass
